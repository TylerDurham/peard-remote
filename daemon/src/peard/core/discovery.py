import asyncio
from typing import List
import pyatv
from pyatv.interface import BaseConfig
from pyatv.const import DeviceModel, PairingRequirement, Protocol

APPLE_TV_MODELS = {
    DeviceModel.AppleTVGen1,
    DeviceModel.Gen2,
    DeviceModel.Gen3,
    DeviceModel.Gen4,
    DeviceModel.Gen4K,
    DeviceModel.AppleTV4KGen2,
    DeviceModel.AppleTV4KGen3,
}


def is_apple_tv(c: BaseConfig) -> bool:
    """Return `True` if the device is an Apple TV (not a HomePod, Mac, Roku, etc.)."""
    info = c.device_info
    # The raw model catches Apple TVs that are too new for pyatv to know about.
    return info.model in APPLE_TV_MODELS or (info.raw_model or "").startswith("AppleTV")


def is_pairable(c: BaseConfig):
    """Simple function that returns `True` if the device can be paired, `False` if not."""
    svc = c.get_service(Protocol.Companion)
    return svc is not None and svc.pairing not in {
        PairingRequirement.Unsupported,
        PairingRequirement.Disabled,
    }


async def scan(
    timeout: int = 5,
    identifier: str | None = None,
    hosts: List[str] | None = None,
    pairable: bool = False,
) -> list[BaseConfig]:
    """Scan the network for Apple TVs."""

    loop = asyncio.get_running_loop()
    devices: list[BaseConfig] = list(
        await pyatv.scan(
            loop=loop,
            hosts=hosts,
            timeout=timeout,
            identifier=identifier,
            protocol={Protocol.AirPlay, Protocol.Companion, Protocol.MRP},
        )
    )

    devices = [device for device in devices if is_apple_tv(device)]

    if pairable:
        devices = [device for device in devices if is_pairable(device)]

    return devices
