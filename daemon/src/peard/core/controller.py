import asyncio

import pyatv
from pyatv.const import Protocol
from pyatv.interface import AppleTV

from peard.core import discovery
from peard.core.config import Config


class Controller:

    def __init__(self) -> None:
        self._config = Config.load()
        self._connections: dict[str, AppleTV] = {}
        self._lock = asyncio.Lock()

    async def get(self, identifier: str) -> AppleTV:
        """Return a connection to a paired TV, connecting if needed."""
        async with self._lock:
            if identifier in self._connections:
                return self._connections[identifier]

            try:
                saved = self._config.get_by_id(identifier)
            except KeyError:
                raise PermissionError(f"Device {identifier} is not paired") from None

            results = await discovery.scan(identifier=identifier)

            if not results:
                raise LookupError(f"Device {identifier} not found")

            tv = results[0]
            tv.set_credentials(Protocol.AirPlay, saved.credentials)

            atv = await pyatv.connect(config=tv, loop=asyncio.get_running_loop())
            self._connections[identifier] = atv
            return atv

    async def close(self) -> None:
        """Close all open connections."""
        async with self._lock:
            tasks = [t for atv in self._connections.values() for t in atv.close()]
            self._connections.clear()
            await asyncio.gather(*tasks)
