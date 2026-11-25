import asyncio

import pyatv
from pyatv.const import Protocol
from pyatv.interface import AppleTV, DeviceListener

from peard.core import discovery
from peard.core.config import Config


class _ConnectionListener(DeviceListener):
    """Forgets a connection once it is lost or closed."""

    def __init__(self, controller: "Controller", identifier: str, atv: AppleTV) -> None:
        self._controller = controller
        self._identifier = identifier
        self._atv = atv

    def connection_lost(self, exception: Exception) -> None:
        self._controller._forget(self._identifier, self._atv)

    def connection_closed(self) -> None:
        self._controller._forget(self._identifier, self._atv)


class Controller:
    def __init__(self) -> None:
        self._connections: dict[str, AppleTV] = {}
        # pyatv only keeps weak references to listeners, so hold on to them here.
        self._listeners: dict[str, _ConnectionListener] = {}
        self._lock = asyncio.Lock()

    async def get(self, identifier: str) -> AppleTV:
        """Return a connection to a paired TV, connecting if needed."""
        async with self._lock:
            if identifier in self._connections:
                return self._connections[identifier]

            try:
                # Load the config each time, to pick up TVs paired since we started.
                saved = Config.load().get_by_id(identifier)
            except KeyError:
                raise PermissionError(f"Device {identifier} is not paired") from None

            results = await discovery.scan(identifier=identifier)

            if not results:
                raise LookupError(f"Device {identifier} not found")

            tv = results[0]
            tv.set_credentials(Protocol.AirPlay, saved.credentials)

            atv = await pyatv.connect(config=tv, loop=asyncio.get_running_loop())
            listener = _ConnectionListener(self, identifier, atv)
            atv.listener = listener
            self._connections[identifier] = atv
            self._listeners[identifier] = listener
            return atv

    def current(self, identifier: str) -> AppleTV | None:
        """Return the open connection to a TV, if there is one."""
        return self._connections.get(identifier)

    def _forget(self, identifier: str, atv: AppleTV) -> None:
        # The TV may have been reconnected already, so only forget this connection.
        if self._connections.get(identifier) is atv:
            del self._connections[identifier]
            del self._listeners[identifier]

    async def drop(self, identifier: str) -> None:
        """Close the connection to a TV, if there is one."""
        async with self._lock:
            atv = self._connections.get(identifier)
            if atv is not None:
                self._forget(identifier, atv)
                await asyncio.gather(*atv.close())

    async def close(self) -> None:
        """Close all open connections."""
        async with self._lock:
            # Closing calls the listeners, so empty the dicts before that happens.
            connections = list(self._connections.values())
            self._connections.clear()
            self._listeners.clear()
            tasks = [t for atv in connections for t in atv.close()]
            await asyncio.gather(*tasks)
