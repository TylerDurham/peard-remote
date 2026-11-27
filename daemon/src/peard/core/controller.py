import asyncio

import pyatv
from pyatv.const import Protocol
from pyatv.interface import AppleTV, DeviceListener

from peard.core import discovery
from peard.core.config import Config


class _ConnectionListener(DeviceListener):
    """Tells a Controller to forget a connection once it is lost or closed, so the next
    request connects again.

    Attributes:
        _controller: The Controller that holds the connection.
        _identifier: The unique identifier of the TV.
        _atv: The connection this listener watches.
    """

    def __init__(self, controller: "Controller", identifier: str, atv: AppleTV) -> None:
        """Create a listener for one connection.

        Args:
            controller: The Controller that holds the connection.
            identifier: The unique identifier of the TV.
            atv: The connection to watch.
        """
        self._controller = controller
        self._identifier = identifier
        self._atv = atv

    def connection_lost(self, exception: Exception) -> None:
        """Forget the connection after pyatv reports that it was lost.

        Args:
            exception: The error that caused the connection to be lost.
        """
        self._controller._forget(self._identifier, self._atv)

    def connection_closed(self) -> None:
        """Forget the connection after pyatv reports that it was closed."""
        self._controller._forget(self._identifier, self._atv)


class Controller:
    """Keeps connections to paired TVs open so commands can reuse them. A connection is
    opened the first time a TV is asked for and forgotten when it is lost or closed.

    Attributes:
        _connections: The open connections, keyed by TV identifier.
        _listeners: The listener for each open connection, keyed by TV identifier.
        _lock: Serializes connecting and closing, so a TV is never connected twice.
    """

    def __init__(self) -> None:
        self._connections: dict[str, AppleTV] = {}
        # pyatv only keeps weak references to listeners, so hold on to them here.
        self._listeners: dict[str, _ConnectionListener] = {}
        self._lock = asyncio.Lock()

    async def get(self, identifier: str) -> AppleTV:
        """Get a connection to a paired TV, connecting to it if there isn't one open.

        Args:
            identifier: The unique identifier of the TV.

        Returns:
            The open connection to the TV.

        Raises:
            PermissionError: If the TV hasn't been paired.
            LookupError: If the TV couldn't be found on the network.
        """
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
        """Get the open connection to a TV without connecting to it.

        Args:
            identifier: The unique identifier of the TV.

        Returns:
            The open connection to the TV, or None if there isn't one.
        """
        return self._connections.get(identifier)

    def _forget(self, identifier: str, atv: AppleTV) -> None:
        """Remove a connection from the open connections without closing it.

        Args:
            identifier: The unique identifier of the TV.
            atv: The connection to forget.
        """
        # The TV may have been reconnected already, so only forget this connection.
        if self._connections.get(identifier) is atv:
            del self._connections[identifier]
            del self._listeners[identifier]

    async def drop(self, identifier: str) -> None:
        """Close the connection to a TV, if there is one.

        Args:
            identifier: The unique identifier of the TV.
        """
        async with self._lock:
            atv = self._connections.get(identifier)
            if atv is not None:
                self._forget(identifier, atv)
                await asyncio.gather(*atv.close())

    async def close(self) -> None:
        """Close all open connections. Call this when you are done with the controller."""
        async with self._lock:
            # Closing calls the listeners, so empty the dicts before that happens.
            connections = list(self._connections.values())
            self._connections.clear()
            self._listeners.clear()
            tasks = [t for atv in connections for t in atv.close()]
            await asyncio.gather(*tasks)
