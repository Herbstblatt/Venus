from abc import ABC, abstractmethod
import asyncio

class Transport(ABC):
    """Abstract base class for all transports"""

    def __init__(self, wiki, url, session):
        self.url = url
        self.session = session
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
    def handle(self, data):
        """Handles the data and returns it in standard JSON format. Subclasses must override this."""
        pass
