import asyncio
import logging
import signal
import datetime

import aiohttp
import asyncpg

# pylint: disable=relative-beyond-top-level
from .wiki import Wiki 
from .handlers import DiscussionsHandler, RCHandler

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
                    wiki.fetch_rc(
                        types=["edit", "new", "categorze"],
                        recent_changes_props=["user", "userid", "ids", "sizes", "flags", "title", "timestamp", "comment"],
                        logevents_props=["user", "userid", "ids", "type", "title", "timestamp", "comment", "details"],
                        limit="max",
                        after=wiki.last_check_time
                    ),
                    wiki.fetch_posts(
                        after=wiki.last_check_time
                    ),
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
                        self.tasks.append(self.loop.create_task(self.handle(wiki, rc_data, posts_data)))
                    else:
                        self.logger.error(f"Both requests returned an exception, skipping wiki {wiki.url}.")

            await asyncio.sleep(10)

    async def handle(self, wiki, rc_data, posts_data):
        now = datetime.datetime.utcnow()
        wiki.last_check_time = now
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE wikis SET last_check_time = $1 WHERE id = $2", now, wiki.id)
        self.logger.info(f"Updated last_check_time for wiki {wiki.url}.")

        handled_data = []
        if rc_data:
            self.logger.info(f"Processing RC for wiki {wiki.url}...")
            rc_handler = RCHandler(self)
            for entry in rc_data["query"]["recentchanges"] + rc_data["query"]["logevents"]:
                handled_data.append(rc_handler.handle(entry))

        if posts_data:
            self.logger.info(f"Processing posts for wiki {wiki.url}...")
            discussions_handler = DiscussionsHandler(self)
            for entry in posts_data["_embedded"]["doc:posts"]:
                handled_data.append(discussions_handler.handle(entry))
        handled_data.sort(key=lambda e: e["datetime"])
        self.logger.info(f"Done processing for wiki {wiki.url}.")
        self.logger.info(f"Data after processing: {handled_data!r}.")
        
        await wiki.execute_transports(handled_data)


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

        