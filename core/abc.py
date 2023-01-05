from abc import ABC, abstractmethod
import asyncio
from typing import TYPE_CHECKING, Any

from core.entry import Entry

if TYPE_CHECKING:
    from core.client import Venus

class Transport(ABC):
    """Abstract base class for all transports"""

    def __init__(self, wiki, url, client: "Venus"):
        self.url = url
        self.client = client
        self.session = client.session
        self.wiki = wiki
        self.loop = asyncio.get_event_loop()

    @abstractmethod
    def prepare(self, data):
        """Prepares the message to send. This function must be called from `execute` method."""
        pass

    @abstractmethod
    async def send(self, message):
        """Sends the message. This function must be called from `execute` method."""
        pass

    async def execute(self, data):
        """Executes the transport"""
        messages = [self.prepare(entry) for entry in data]

        for message in messages:
            await self.send(message)

class Handler(ABC):
    """Abstract base class for all handlers"""

    @abstractmethod
    def handle(self, data: Any) -> list[Entry]:
        """Handles the data and returns it in standard JSON format. Subclasses must override this."""
        pass
