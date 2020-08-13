import asyncio
import logging
import signal

import aiohttp
import asyncpg

from .wiki import Wiki # pylint: disable=relative-beyond-top-level

__version__ = "0.0.1"

class Venus:
    """Recent changes logger."""

    def __init__(self, *, username="Unkhown Fandom User", log_level=logging.INFO):
        self.loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(headers={
            "User-Agent": f"Venus v{__version__} written by Blask Spaceship, running by {username}"
        })
        self.pool = self.loop.run_until_complete(asyncpg.create_pool())
        self.wikis = []
        self.tasks = []

        self.logger = logging.getLogger('venus')
        self.logger.setLevel(log_level)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
        self.logger.addHandler(handler)

    async def load(self):
        """Loads list of wikis and transports from database"""
        async with self.pool.acquire() as conn:
            wikis = await conn.fetch("""SELECT wikis.id, wikis.url, wikis.last_check_time, array_agg(transports.type) as ttypes, array_agg(transports.url) as turls
                                        FROM wikis, transports
                                        WHERE wikis.id = transports.wiki_id
                                        GROUP BY id;""")
            self.logger.debug("Wiki list was sucsessfully fetched. Handling...")
            for row in wikis:
                wiki = Wiki(row["id"], row["url"], row["last_check_time"], self.session)
                for transport_type, transport_url in zip(row["ttypes"], row["turls"]):
                    wiki.add_transport(transport_type, transport_url)
                self.logger.debug(f"{row['id']} was processed")
                self.wikis.append(wiki)
            else:
                self.logger.warn("There weren't any wikis in db. Please add one with 'python -m venus add-wiki'.")
    
    async def main(self):
        """Main loop function. Polls and processes recent changes every n minutes"""
        while True:
            if not self.wikis:
                self.logger.warn("There aren't any wikis in db so we're skipping this iteration. We'll retry again in 10 seconds...")
            else:
                self.logger.info("Polling...")
                tasks = [asyncio.gather(
                    wiki.fetch_rc(),
                    wiki.fetch_posts(),
                    return_exceptions=True
                ) for wiki in self.wikis]
                for wiki_index, task in enumerate(asyncio.as_completed(tasks)):
                    rc_data, posts_data = await task
                    wiki = self.wikis[wiki_index]

                    if isinstance(rc_data, Exception):
                        self.logger.error(f"Exception occured while requesting data for recent changes in {wiki.url}: {rc_data!r}")
                        rc_data = None
                    if isinstance(posts_data, Exception):
                        self.logger.error(f"Exception occured while requesting data for posts in {wiki.url}: {posts_data!r}")
                        posts_data = None
                    
                    if rc_data or posts_data:
                        self.logger.info(f"Ready for {wiki.url}, now handling...")
                        handled_data = self.handle(wiki, rc_data, posts_data)
                        self.tasks.append(self.loop.create_task(wiki.execute_transports(*handled_data)))
                    else:
                        self.logger.error(f"Both requests returned an exception, skipping wiki {wiki.url}.")

            await asyncio.sleep(10)

    def handle(self, wiki, rc_data, posts_data):
        return None, None

    async def cleanup(self, signal):
        """Cleans up all tasks after logger shutdown"""
        self.logger.info(f"Receivied exit signal {signal}. Exiting...")
        self.logger.info("Closing connection pool...")
        await self.pool.close()
        self.logger.info("Closing client session...")
        await self.session.close()

        self.logger.info("Cleaning up all tasks...")
        tasks = [t for t in self.tasks if not t.done()]
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        self.loop.stop()

    def run(self):
        """Runs the logger"""
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            self.loop.add_signal_handler(s, lambda s=s: asyncio.create_task(self.cleanup(s)))
        
        self.loop.run_until_complete(self.load())
        try:
            self.tasks.append(self.loop.create_task(self.main()))
            self.loop.run_forever()
        finally:
            self.loop.close()
            self.logger.info("Sucsessfully shutdown the logger.")

        