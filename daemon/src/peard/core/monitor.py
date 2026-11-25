"""Watches the active Apple TV and tells subscribers about what it is doing."""

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from pyatv import exceptions
from pyatv.const import FeatureName, FeatureState, PowerState
from pyatv.interface import (
    AppleTV,
    AudioListener,
    Playing,
    PowerListener,
    PushListener,
)

from peard.core.config import Config, cache_dir
from peard.core.controller import Controller

log = logging.getLogger(__name__)

# Seconds to wait before trying to connect again. Doubles on every failure.
MIN_RETRY = 2
MAX_RETRY = 30

Snapshot = dict[str, Any]


def _blank_playing() -> Snapshot:
    return {
        "state": "idle",
        "title": None,
        "artist": None,
        "album": None,
        "series": None,
        "season": None,
        "episode": None,
        "mediaType": None,
        "position": None,
        "total": None,
        "positionAt": None,
        "app": None,
        "appId": None,
        "artwork": None,
    }


def _blank_connection() -> Snapshot:
    return {
        "connected": False,
        "error": None,
        "power": "unknown",
        "volume": None,
        "keyboard": "unknown",
        # The plugin hides or disables controls that are False. These stay False until
        # the API has endpoints for them, whatever the TV supports.
        "features": {
            "power": False,
            "volume": False,
            "setVolume": False,
            "keyboard": False,
            "apps": False,
        },
        **_blank_playing(),
    }


def _blank() -> Snapshot:
    return {"device": None, "deviceId": None, **_blank_connection()}


def _safe[T](fn: Callable[[], T], default: T) -> T:
    """Read a value from the TV, which may not support it or may be disconnected."""
    try:
        return fn()
    except (exceptions.NotSupportedError, exceptions.BlockedStateError):
        return default


class Monitor(PushListener, PowerListener, AudioListener):
    """Follows the active TV for as long as there is at least one subscriber."""

    def __init__(self, controller: Controller) -> None:
        self._controller = controller
        self._state = _blank()
        self._subscribers: set[asyncio.Queue[Snapshot | None]] = set()
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._atv: AppleTV | None = None
        self._artwork_id: str | None = None
        self._artwork_task: asyncio.Task[None] | None = None

    @contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue[Snapshot | None]]:
        """Get a queue that starts with the current snapshot and receives new ones.

        It receives `None` once there won't be any more.
        """
        # Only the latest snapshot matters, so a slow subscriber skips older ones.
        queue: asyncio.Queue[Snapshot | None] = asyncio.Queue(maxsize=1)
        queue.put_nowait(self._state)
        self._subscribers.add(queue)
        if self._task is None:
            self._task = asyncio.create_task(self._run())
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
            if not self._subscribers:
                self._stop()

    def _stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
            self._state = _blank()

    def close(self) -> None:
        """Stop watching, and tell the subscribers that there is nothing more."""
        for queue in self._subscribers:
            self._put(queue, None)
        self._subscribers.clear()
        self._stop()

    @staticmethod
    def _put(queue: asyncio.Queue[Snapshot | None], item: Snapshot | None) -> None:
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(item)

    def wake(self) -> None:
        """Check for a change of active TV right away."""
        self._wake.set()

    def _set(self, **changes: Any) -> None:
        state = {**self._state, **changes}
        if state == self._state:
            return
        # Queued snapshots are never modified; each change makes a new one.
        self._state = state
        for queue in self._subscribers:
            self._put(queue, state)

    # Connecting

    async def _run(self) -> None:
        while True:
            try:
                await self._follow()
            except Exception:
                log.exception("Monitor failed; restarting")
                await asyncio.sleep(MAX_RETRY)

    async def _follow(self) -> None:
        retry = MIN_RETRY
        while True:
            config = Config.load()
            identifier = config.active

            if identifier is None:
                self._set(**{**_blank(), "error": "No active Apple TV"})
                await self._wait_while(lambda: Config.load().active is None)
                continue

            if identifier != self._state["deviceId"]:
                names = {d.identifier: d.name for d in config.devices}
                self._set(
                    **_blank_connection(),
                    device=names.get(identifier),
                    deviceId=identifier,
                )
                retry = MIN_RETRY

            def is_active(identifier: str = identifier) -> bool:
                return Config.load().active == identifier

            try:
                atv = await self._controller.get(identifier)
            except Exception as e:
                log.warning("Could not connect to %s: %r", identifier, e)
                self._set(connected=False, error=str(e) or type(e).__name__)
                await self._wait_while(is_active, timeout=retry)
                retry = min(retry * 2, MAX_RETRY)
                continue

            retry = MIN_RETRY

            def is_connected(identifier: str = identifier, atv: AppleTV = atv) -> bool:
                return self._controller.current(identifier) is atv

            try:
                self._attach(atv)
                await self._wait_while(lambda: is_active() and is_connected())
            finally:
                self._detach(atv)

            if is_connected():
                # Another TV is active now, so this connection is no longer needed.
                await self._controller.drop(identifier)
            else:
                self._set(**{**_blank_connection(), "error": "Connection lost"})
                await self._wait_while(is_active, timeout=MIN_RETRY)

    async def _wait_while(
        self, condition: Callable[[], bool], timeout: float | None = None
    ) -> None:
        """Wait until the condition is false. Checks every second, or on `wake()`.

        The config has to be polled because the CLI can change the active TV too.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while condition() and (deadline is None or time.monotonic() < deadline):
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=1)
            except TimeoutError:
                pass
            self._wake.clear()

    def _attach(self, atv: AppleTV) -> None:
        self._atv = atv
        self._set(
            **{
                **_blank_connection(),
                "connected": True,
                "power": self._power_name(
                    _safe(lambda: atv.power.power_state, PowerState.Unknown)
                ),
            }
        )
        self._update_audio()

        # pyatv only keeps weak references to listeners, but the server keeps us alive.
        atv.push_updater.listener = self
        atv.power.listener = self
        atv.audio.listener = self
        _safe(lambda: atv.push_updater.start(), None)

    def _detach(self, atv: AppleTV) -> None:
        if self._artwork_task is not None:
            self._artwork_task.cancel()
            self._artwork_task = None
        self._artwork_id = None
        self._atv = None

        def stop() -> None:
            atv.push_updater.stop()
            atv.push_updater.listener = None
            atv.power.listener = None
            atv.audio.listener = None

        _safe(stop, None)

    # Updates from the TV

    def playstatus_update(self, updater: Any, playstatus: Playing) -> None:
        atv = self._atv
        if atv is None:
            return

        app = _safe(lambda: atv.metadata.app, None)
        self._set(
            state=playstatus.device_state.name.lower(),
            title=playstatus.title,
            artist=playstatus.artist,
            album=playstatus.album,
            series=playstatus.series_name,
            season=playstatus.season_number,
            episode=playstatus.episode_number,
            mediaType=playstatus.media_type.name.lower(),
            position=playstatus.position,
            total=playstatus.total_time,
            # The plugin works out the current position from this Unix time (in ms).
            positionAt=int(time.time() * 1000),
            app=app.name if app else None,
            appId=app.identifier if app else None,
        )
        self._update_audio()
        self._update_artwork(atv)

    def playstatus_error(self, updater: Any, exception: Exception) -> None:
        log.warning("Push updates failed: %r", exception)
        # Updates stop after an error, so start them again in a while.
        _safe(lambda: updater.start(initial_delay=MAX_RETRY), None)

    def powerstate_update(self, old_state: PowerState, new_state: PowerState) -> None:
        self._set(power=self._power_name(new_state))

    def volume_update(self, old_level: float, new_level: float) -> None:
        self._update_audio()

    def volume_device_update(
        self, output_device: Any, old_level: float, new_level: float
    ) -> None:
        self._update_audio()

    def outputdevices_update(self, old_devices: Any, new_devices: Any) -> None:
        self._update_audio()

    @staticmethod
    def _power_name(state: PowerState) -> str:
        return state.name.lower()

    def _update_audio(self) -> None:
        atv = self._atv
        if atv is None:
            return

        def available(feature: FeatureName) -> bool:
            return _safe(
                lambda: atv.features.in_state(FeatureState.Available, feature), False
            )

        volume = None
        if available(FeatureName.Volume):
            volume = _safe(lambda: round(atv.audio.volume), None)

        self._set(
            volume=volume,
            features={
                **self._state["features"],
                "volume": available(FeatureName.VolumeUp),
            },
        )

    # Artwork

    def _update_artwork(self, atv: AppleTV) -> None:
        artwork_id = _safe(lambda: atv.metadata.artwork_id, None)
        if artwork_id == self._artwork_id:
            return

        self._artwork_id = artwork_id
        if self._artwork_task is not None:
            self._artwork_task.cancel()
        self._artwork_task = asyncio.create_task(self._fetch_artwork(atv, artwork_id))

    async def _fetch_artwork(self, atv: AppleTV, artwork_id: str | None) -> None:
        path = None
        try:
            artwork = await atv.metadata.artwork(width=256) if artwork_id else None
            if artwork is not None:
                path = self._save_artwork(artwork.bytes, artwork.mimetype)
        except Exception as e:
            log.warning("Could not get artwork: %r", e)
        self._set(artwork=path)

    @staticmethod
    def _save_artwork(data: bytes, mimetype: str) -> str:
        directory = cache_dir()
        directory.mkdir(parents=True, exist_ok=True)

        # A new name for each image, so the plugin doesn't show a cached one.
        digest = hashlib.sha256(data).hexdigest()[:16]
        extension = "png" if mimetype == "image/png" else "jpg"
        path = directory / f"artwork-{digest}.{extension}"
        path.write_bytes(data)

        for old in directory.glob("artwork-*"):
            if old != path:
                old.unlink(missing_ok=True)
        return str(path)
