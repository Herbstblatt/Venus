import asyncio

import aiohttp
import asyncpg

from .wiki import Wiki # pylint: disable=relative-beyond-top-level

__version__ = "0.0.1"

class Venus:
    """Recent changes logger."""

    def __init__(self, username="Unkhown Fandom User"):
        self.loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(headers={
            "User-Agent": f"Venus v{__version__} written by Blask Spaceship, running by {username}"
        })
        self.pool = self.loop.run_until_complete(asyncpg.create_pool())
        self.wikis = []

    async def load(self):
        """Loads list of wikis and transports from database"""
        pass
    
    async def main(self):
        """Main loop function. Polls and processes recent changes every n minutes"""
        pass

    async def cleanup(self):
        """Cleans up all tasks after logger shutdown"""
        pass

    async def run(self):
        """Runs the logger"""
        pass
        