import asyncio
import logging
import signal
import datetime
from collections import namedtuple
from typing import List

import aiohttp
import asyncpg
from core.entry import Entry

from fandom.wiki import Wiki 
from handlers.discussions import DiscussionsHandler
from handlers.rc import RCHandler

__version__ = "0.0.1"

RCData = namedtuple("data", "wiki rc posts")

class Venus:
    """Recent changes logger."""

    def __init__(self, *, username="Unkhown Fandom User", log_level=logging.INFO):
        self.loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(headers={
            "User-Agent": f"Venus v{__version__} written by Black Spaceship, running by {username}"
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
    
    async def fetch_data(self, wiki: Wiki) -> RCData:
        """Fetches RC data for a given wiki"""
        rc_data, posts_data = await asyncio.gather(
            wiki.fetch_rc(
                types=["edit", "new", "categorze"],
                recent_changes_props=["user", "userid", "ids", "sizes", "flags", "title", "timestamp", "comment"],
                logevents_props=["user", "userid", "ids", "type", "title", "timestamp", "comment", "details"],
                limit="max",
                after=wiki.last_check_time
            ),
            wiki.fetch_social_activity(
                after=wiki.last_check_time
            ),
            return_exceptions=True
        )
        return RCData(wiki=wiki, rc=rc_data, posts=posts_data)
    
    async def main(self):
        """Main loop function. Polls and processes recent changes every n minutes"""
        while True:
            if not self.wikis:
                self.logger.warn("There aren't any wikis in db so we're skipping this iteration. We'll retry again in 10 seconds...")
            else:
                self.logger.info("Polling...")
                tasks = [self.fetch_data(wiki) for wiki in self.wikis]
                for task in asyncio.as_completed(tasks):
                    data = await task
                    now = datetime.datetime.utcnow()
                    data.wiki.last_check_time = now

                    if isinstance(data.rc, Exception):
                        self.logger.error(f"Exception occured while requesting data for recent changes in {data.wiki.url}: {data.rc!r}")
                        rc_data = None
                    else:
                        rc_data = data.rc

                    if isinstance(data.posts, Exception):
                        self.logger.error(f"Exception occured while requesting data for posts in {data.wiki.url}: {data.posts!r}")
                        posts_data = None
                    else:
                        posts_data = data.posts

                    if rc_data or posts_data:
                        self.logger.info(f"Ready for {data.wiki.url}, now handling...")
                        self.loop.create_task(self.handle(data.wiki, rc_data, posts_data, time=now))
                    else:
                        self.logger.error(f"Both requests returned an exception, skipping wiki {data.wiki.url}.")

            await asyncio.sleep(10)

    async def handle(self, wiki, rc_data, posts_data, time):
        handled_data: List[Entry] = []
        if rc_data:
            self.logger.info(f"Processing RC for wiki {wiki.url}...")
            self.logger.debug(f"Recieved {rc_data}")
            
            rc_handler = RCHandler(self, wiki)
            handled_data.extend(rc_handler.handle(rc_data))

        if posts_data:
            self.logger.info(f"Processing posts for wiki {wiki.url}...")
            self.logger.debug(f"Recieved {posts_data}")

            discussions_handler = DiscussionsHandler(self, wiki)
            handled_data.extend(discussions_handler.handle(posts_data))
        
        handled_data.sort(key=lambda e: e.timestamp)
        self.logger.info(f"Done processing for wiki {wiki.url}.")
        self.logger.info(f"Data after processing: {handled_data!r}.")
        
        self.logger.info(f"Sending data for wiki {wiki.url}...")
        self.logger.debug(wiki.transports)
        tasks = [transport.execute(handled_data) for transport in wiki.transports]
        
        await asyncio.gather(*tasks)
        
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE wikis SET last_check_time = $1 WHERE id = $2", time, wiki.id)
            self.logger.info(f"Updated last_check_time for wiki {wiki.url}.")

    async def cleanup(self, signal):
        """Cleans up all tasks after logger shutdown"""
        self.logger.info(f"Receivied exit signal {signal}. Exiting...")
        self.logger.info("Closing connection pool...")
        await self.pool.close()
        self.logger.info("Closing client session...")
        await self.session.close()

        self.logger.info("Cleaning up all tasks...")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
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
            self.loop.create_task(self.main())
            self.loop.run_forever()
        finally:
            self.loop.close()
            self.logger.info("Sucsessfully shutdown the logger.")

        