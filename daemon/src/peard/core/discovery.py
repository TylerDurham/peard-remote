import asyncio

import pyatv
from pyatv.const import DeviceModel, PairingRequirement, Protocol
from pyatv.interface import BaseConfig

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
    """Check whether a device is an Apple TV, and not a HomePod, Mac, Roku or the like.

    Args:
        c: The device found by a scan.

    Returns:
        True if the device is an Apple TV, False if not.
    """
    info = c.device_info
    # The raw model catches Apple TVs that are too new for pyatv to know about.
    return info.model in APPLE_TV_MODELS or (info.raw_model or "").startswith("AppleTV")


def is_pairable(c: BaseConfig) -> bool:
    """Check whether a device can be paired over the Companion protocol.

    Args:
        c: The device found by a scan.

    Returns:
        True if the device offers Companion and allows pairing with it, False if not.
    """
    svc = c.get_service(Protocol.Companion)
    return svc is not None and svc.pairing not in {
        PairingRequirement.Unsupported,
        PairingRequirement.Disabled,
    }


async def scan(
    timeout: int = 5,
    identifier: str | None = None,
    hosts: list[str] | None = None,
    pairable: bool = False,
) -> list[BaseConfig]:
    """Scan the network for Apple TVs over AirPlay, Companion and MRP.

    Args:
        timeout: How many seconds to scan for.
        identifier: Only find the TV with this unique identifier.
        hosts: Ask these IP addresses directly instead of using mDNS.
        pairable: Only find TVs that can be paired.

    Returns:
        The Apple TVs that were found, which may be empty.
    """
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
