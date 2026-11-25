"""The peard HTTP API, which lets the Noctalia plugin control paired Apple TVs."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pyatv import exceptions
from pyatv.const import InputAction, PowerState
from pyatv.interface import AppleTV
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from peard.core.config import Config, Device
from peard.core.controller import Controller
from peard.core.monitor import Monitor

# Keys that can also be held or double-pressed.
ACTION_KEYS = {"up", "down", "left", "right", "select", "menu", "home"}

# Every key that can be sent. Remote commands that need a value are left out.
KEYS = ACTION_KEYS | {
    "channel_down",
    "channel_up",
    "control_center",
    "guide",
    "next",
    "pause",
    "play",
    "play_pause",
    "previous",
    "screensaver",
    "skip_backward",
    "skip_forward",
    "stop",
    "top_menu",
    "volume_down",
    "volume_up",
}

# Errors that mean the TV couldn't be reached, or that the connection has died.
CONNECTION_ERRORS = (
    exceptions.BlockedStateError,
    exceptions.ConnectionFailedError,
    exceptions.ConnectionLostError,
    exceptions.OperationTimeoutError,
    asyncio.TimeoutError,
    OSError,
)


# Seconds between pings on an idle event stream.
PING_INTERVAL = 15


class Action(StrEnum):
    tap = "tap"
    double = "double"
    hold = "hold"


class PowerCommand(StrEnum):
    on = "on"
    off = "off"
    toggle = "toggle"


INPUT_ACTIONS = {
    Action.tap: InputAction.SingleTap,
    Action.double: InputAction.DoubleTap,
    Action.hold: InputAction.Hold,
}


class DeviceRequest(BaseModel):
    id: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The controller's connections belong to the server's event loop, so it is created
    # and closed in here.
    app.state.controller = Controller()
    app.state.monitor = Monitor(app.state.controller)
    try:
        yield
    finally:
        await app.state.controller.close()


async def require_pear_header(x_pear: Annotated[str | None, Header()] = None) -> None:
    """Reject requests without `X-Pear`, which other websites can't send to us."""
    if x_pear is None:
        raise HTTPException(403, "Missing X-Pear header")


def find_device(config: Config, key: str) -> Device:
    """Find a paired TV by its identifier, or by the start of its name."""
    for device in config.devices:
        if device.identifier == key:
            return device

    name = key.casefold()
    matches = [d for d in config.devices if name and d.name.casefold().startswith(name)]
    if len(matches) != 1:
        raise HTTPException(404, f"No single paired Apple TV matches {key!r}")
    return matches[0]


async def connect_active(request: Request) -> tuple[str, AppleTV]:
    """Get the identifier of the active TV, and a connection to it."""
    identifier = Config.load().active
    if identifier is None:
        raise HTTPException(409, "No active Apple TV. Run `peard set active` first.")

    controller: Controller = request.app.state.controller
    try:
        return identifier, await controller.get(identifier)
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    except LookupError as e:
        raise HTTPException(503, str(e)) from e
    except (
        exceptions.AuthenticationError,
        exceptions.InvalidCredentialsError,
        exceptions.NoCredentialsError,
    ) as e:
        raise HTTPException(
            502, f"{identifier} rejected its saved credentials: {e}"
        ) from e
    except CONNECTION_ERRORS as e:
        raise HTTPException(503, f"Could not connect to {identifier}: {e}") from e


@asynccontextmanager
async def command_errors(
    request: Request, identifier: str, name: str
) -> AsyncIterator[None]:
    """Turn errors from sending a command to a TV into HTTP errors."""
    try:
        yield
    except exceptions.NotSupportedError as e:
        raise HTTPException(501, f"{identifier} does not support {name!r}") from e
    except CONNECTION_ERRORS as e:
        # Drop the dead connection so that the next request reconnects.
        await request.app.state.controller.drop(identifier)
        raise HTTPException(503, f"Lost connection to {identifier}: {e}") from e
    except (
        exceptions.CommandError,
        exceptions.InvalidStateError,
        exceptions.ProtocolError,
    ) as e:
        raise HTTPException(502, f"{identifier} could not run {name!r}: {e}") from e


app = FastAPI(title="peard", lifespan=lifespan)

# Only answer to local names, so a website can't reach us through DNS rebinding.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


# The plugin shows the `error` field of a failed response to the user.
@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, e: StarletteHTTPException) -> JSONResponse:
    return JSONResponse({"error": e.detail}, e.status_code, headers=e.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, e: RequestValidationError) -> JSONResponse:
    message = "; ".join(f"{err['loc'][-1]}: {err['msg']}" for err in e.errors())
    return JSONResponse({"error": message}, 422)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/events")
async def events(request: Request) -> StreamingResponse:
    """Stream snapshots of the active TV, as one `data:` line of JSON each."""
    monitor: Monitor = request.app.state.monitor

    async def stream() -> AsyncIterator[str]:
        with monitor.subscribe() as snapshots:
            while True:
                try:
                    snapshot = await asyncio.wait_for(snapshots.get(), PING_INTERVAL)
                except TimeoutError:
                    # Keeps the connection alive, and ignored by clients.
                    yield ": ping\n\n"
                else:
                    if snapshot is None:
                        return
                    yield f"data: {json.dumps(snapshot)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/devices")
async def devices() -> dict[str, Any]:
    """List the paired TVs. Never include their credentials."""
    config = Config.load()
    return {
        "active": config.active,
        "devices": [
            {"id": d.identifier, "name": d.name, "description": d.description}
            for d in config.devices
        ],
    }


@app.post("/device", dependencies=[Depends(require_pear_header)])
async def set_device(request: Request, body: DeviceRequest) -> dict[str, str]:
    """Set the active TV."""
    config = Config.load()
    device = find_device(config, body.id)
    config.active = device.identifier
    config.save()
    request.app.state.monitor.wake()
    return {"active": device.identifier}


@app.post("/key/{name}", dependencies=[Depends(require_pear_header)])
async def key(
    request: Request, name: str, action: Action = Action.tap
) -> dict[str, str]:
    """Send a key to the active TV."""
    if name not in KEYS:
        raise HTTPException(404, f"Unknown key {name!r}")
    if action is not Action.tap and name not in ACTION_KEYS:
        raise HTTPException(400, f"Key {name!r} does not support {action.value!r}")

    identifier, atv = await connect_active(request)
    args = [INPUT_ACTIONS[action]] if name in ACTION_KEYS else []
    async with command_errors(request, identifier, name):
        await getattr(atv.remote_control, name)(*args)

    return {"key": name, "action": action.value}


@app.post("/power/{command}", dependencies=[Depends(require_pear_header)])
async def power(request: Request, command: PowerCommand) -> dict[str, str]:
    """Wake the active TV or put it to sleep."""
    identifier, atv = await connect_active(request)
    async with command_errors(request, identifier, f"power {command.value}"):
        state = atv.power.power_state
        if command is PowerCommand.toggle:
            turn_on = state is not PowerState.On
        else:
            turn_on = command is PowerCommand.on

        if turn_on:
            await atv.power.turn_on()
        elif state is not PowerState.Off:
            # pyatv turns a TV off by holding Home and pressing Select, which would wake
            # one that is already asleep.
            await atv.power.turn_off()

    return {"power": "on" if turn_on else "off"}
