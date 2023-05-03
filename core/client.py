import asyncio
import logging
import signal
import datetime
from collections import namedtuple
import typing
from typing import List, TYPE_CHECKING, Optional

import aiohttp
import asyncpg
import fluent.runtime
from core.abc import has_flag
from core.entry import ActionType

from fandom.wiki import Wiki 
from handlers.discussions import DiscussionsHandler
from handlers.rc import RCHandler

if TYPE_CHECKING:
    from core.entry import Entry

__version__ = "0.0.1"


class RCData(typing.NamedTuple):
    wiki: Wiki
    rc: dict | BaseException
    activity: list | BaseException
    posts: dict | BaseException | None

class Venus:
    """Recent changes logger."""

    def __init__(self, *, username: str = "Unkhown Fandom User", log_level: int = logging.INFO):
        self.loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(headers={
            "User-Agent": f"Venus v{__version__} written by Black Spaceship, running by {username}"
        })
        self.pool: asyncpg.Pool = self.loop.run_until_complete(asyncpg.create_pool())  # type: ignore
        self.wikis = []
        self.tasks = []

        loader = fluent.runtime.FluentResourceLoader("strings/{locale}")
        self.l10n = fluent.runtime.FluentLocalization(["ru"], ["main.ftl"], loader)

        self.logger = logging.getLogger('venus')
        self.logger.setLevel(log_level)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
        self.logger.addHandler(handler)

    async def load(self):
        """Loads list of wikis and transports from database"""
        async with self.pool.acquire() as conn:
            wikis = await conn.fetch("""SELECT wikis.id, wikis.url, wikis.last_check_time, array_agg(transports.type) as ttypes, array_agg(transports.url) as turls, array_agg(transports.actions) as tactions
                                        FROM wikis, transports
                                        WHERE wikis.id = transports.wiki_id
                                        GROUP BY id;""")
            self.logger.debug("Wiki list was sucsessfully fetched. Handling...")
            for row in wikis:
                wiki = Wiki(row["id"], row["url"], row["last_check_time"], self)
                for transport_type, transport_url, transport_action in zip(row["ttypes"], row["turls"], row["tactions"]):
                    wiki.add_transport(transport_type, transport_url, transport_action)
                self.logger.debug(f"{row['id']} was processed")
                self.wikis.append(wiki)
            else:
                self.logger.warn("There weren't any wikis in db. Please add one with 'python -m venus add-wiki'.")
    
    async def fetch_data(self, wiki: Wiki) -> RCData:
        """Fetches RC data for a given wiki"""
        
        # TODO: Make this fetch only required data
        last_check_time = wiki.last_check_time
        wiki.last_check_time = datetime.datetime.utcnow()
        
        self.logger.debug(f"Making query for wiki {wiki.url} with last_check_time={last_check_time}")
        rc_data, activity_data, posts_data = await asyncio.gather(
            wiki.fetch_rc(
                types=["edit", "new", "categorze"],
                recent_changes_props=["user", "userid", "ids", "sizes", "flags", "title", "timestamp", "comment"],
                logevents_props=["user", "userid", "ids", "type", "title", "timestamp", "comment", "details"],
                limit="max",
                after=last_check_time,
                before=wiki.last_check_time
            ),
            wiki.fetch_social_activity(
                after=last_check_time
            ),
            wiki.fetch_recent_posts(),
            return_exceptions=True
        )
        return RCData(wiki=wiki, rc=rc_data, activity=activity_data, posts=posts_data)

    async def populate_ids(self, wiki: Wiki, entries: List["Entry"]):
        authors_and_ids = {}
        for entry in entries:
            authors_and_ids[entry.user.name] = entry.user.id
        
        to_query = [k.replace(" ", "_") for k, v in authors_and_ids.items() if v == 0]
        if not to_query:
            return

        result = await wiki.query_mw(
            params=dict(
                action="query",
                list="users",
                ususers="|".join(to_query),
                format="json"
            )
        )

        for user in result["query"]["users"]:
            authors_and_ids[user["name"]] = user["userid"]
        for entry in entries:
            entry.user.id = authors_and_ids[entry.user.name]

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
                    now = data.wiki.last_check_time
                    
                    if isinstance(data.rc, Exception):
                        self.logger.error(f"Exception occured while requesting data for recent changes in {data.wiki.url}: {data.rc!r}")
                        rc_data = None
                    else:
                        rc_data = data.rc

                    if isinstance(data.activity, Exception):
                        self.logger.error(f"Exception occured while requesting social activity in {data.wiki.url}: {data.activity!r}")
                        activity_data = None
                    else:
                        activity_data = data.activity

                    if isinstance(data.posts, Exception):
                        self.logger.error(f"Exception occured while requesting data for posts in {data.wiki.url}: {data.activity!r}")
                        posts_data = None
                    else:
                        posts_data = data.posts

                    if rc_data or activity_data:
                        self.logger.info(f"Ready for {data.wiki.url}, now handling...")
                        self.loop.create_task(self.handle(data.wiki, rc_data, activity_data, posts_data, time=now))
                    else:
                        self.logger.error(f"Both requests returned an exception, skipping wiki {data.wiki.url}.")

            await asyncio.sleep(10)

    async def handle(self, wiki: Wiki, rc_data, activity_data, posts_data, time):
        handled_data: List[Entry] = []
        if rc_data:
            self.logger.info(f"Processing RC for wiki {wiki.url}...")
            self.logger.debug(f"Recieved {rc_data}")
            
            rc_handler = RCHandler(self, wiki)
            handled_data.extend(rc_handler.handle(rc_data))

        if activity_data:
            self.logger.info(f"Processing posts for wiki {wiki.url}...")
            self.logger.debug(f"Recieved {activity_data}")

            discussions_handler = DiscussionsHandler(self, wiki)
            handled_data.extend(discussions_handler.handle(activity_data, posts_data))
        
        await self.populate_ids(wiki, handled_data)
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

        