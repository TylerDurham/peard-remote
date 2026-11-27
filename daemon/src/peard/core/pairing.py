import asyncio
from collections.abc import Awaitable, Callable

import pyatv
from pyatv.const import Protocol

from peard.core import discovery
from peard.core.config import Config, Device


async def pair(
    identifier: str,
    protocol: Protocol,
    ask_pin: Callable[[], Awaitable[int]],
    show_pin: Callable[[int], None],
    default_pin: int = 1234,
):
    """Pair with a TV and save it to the config as the active TV.

    Either the TV shows a PIN for the user to enter, or the user enters `default_pin`
    on the TV, depending on the protocol.

    Args:
        identifier: The unique identifier of the TV.
        protocol: The protocol to pair with.
        ask_pin: Called to ask the user for the PIN the TV shows.
        show_pin: Called with the PIN the user must enter on the TV.
        default_pin: The PIN to use when the TV doesn't provide one.

    Raises:
        LookupError: If the TV couldn't be found on the network.
        RuntimeError: If pairing failed, for example because the PIN was wrong.
    """
    loop = asyncio.get_running_loop()

    tvs = await discovery.scan(identifier=identifier)

    if len(tvs) == 0:
        raise LookupError(f"Device {identifier} not found")

    tv = tvs[0]
    config = Config.load()

    handler = await pyatv.pair(config=tv, protocol=protocol, loop=loop)
    try:
        await handler.begin()

        if handler.device_provides_pin:
            handler.pin(await ask_pin())
        else:
            handler.pin(default_pin)
            show_pin(default_pin)

        await handler.finish()

        if not handler.has_paired:
            raise RuntimeError("Pairing failed")

        # Replace any earlier pairing with this TV, whose credentials are now stale.
        config.devices = [
            d for d in config.devices if d.identifier != str(tv.identifier)
        ]
        config.devices.append(
            Device(
                credentials=str(handler.service.credentials),
                name=tv.name,
                description=tv.device_info.model_str,
                identifier=str(tv.identifier),
                protocol=handler.service.protocol.name,
            )
        )

        config.active = tv.identifier
        config.save()

    finally:
        await handler.close()
