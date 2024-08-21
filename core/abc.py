from abc import ABC, abstractmethod
import asyncio
from typing import TYPE_CHECKING, Any

from core.entry import Entry
from core.utils import has_flag

if TYPE_CHECKING:
    from core.client import Venus


class Transport(ABC):
    """Abstract base class for all transports"""

    def __init__(self, wiki, url, actions, client: "Venus"):
        self.url = url
        self.client = client
        self.session = client.session
        self.wiki = wiki
        self.actions = actions
        self.loop = asyncio.get_event_loop()

    @abstractmethod
    def prepare(self, data):
        """Prepares the message to send. This function must be called from `execute` method."""
        pass

    def can_send(self, entry: Entry) -> bool:
        """Checks if the entry can be sent."""
        return has_flag(self.actions, entry.type.value)
    
    @abstractmethod
    async def send(self, message):
        """Sends the message. This function must be called from `execute` method."""
        pass

    async def execute(self, data: list[Entry]):
        """Executes the transport"""
        messages = [self.prepare(entry) for entry in data if self.can_send(entry)]

        for message in messages:
            await self.send(message)

class Handler(ABC):
    """Abstract base class for all handlers"""

    @abstractmethod
    def handle(self, data: Any) -> list[Entry]:
        """Handles the data and returns it in standard JSON format. Subclasses must override this."""
        pass
