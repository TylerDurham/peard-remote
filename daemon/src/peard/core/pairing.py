import asyncio
from collections.abc import Awaitable, Callable

import pyatv
from pyatv.const import Protocol
from pyatv.interface import AppleTV

from peard.core import discovery
from peard.core.config import Config, Device


async def pair(
    identifier: str,
    protocol: Protocol,
    ask_pin: Callable[[], Awaitable[int]],
    show_pin: Callable[[int], None],
    default_pin: int = 1234,
):

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
