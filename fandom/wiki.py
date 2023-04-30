import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from transports import discord

if TYPE_CHECKING:
    from core.client import Venus

class InvalidTransportType(Exception):
    pass

class Wiki:
    def __init__(self, wiki_id: int, url: str, last_check_time: datetime.datetime, client: "Venus"):
        self.url = url
        self.id = wiki_id
        self.last_check_time = last_check_time
        self.client = client
        self.session = client.session
        self.transports = []
    
    def add_transport(self, type, url):
        """Adds a new transport to the list of wiki transports."""
        if type == "discord":
            self.transports.append(discord.DiscordTransport(wiki=self, url=url, client=self.client))
        else:
            raise InvalidTransportType

    def url_to(self, page, namespace=None, **params):
        """Returns URL to the given page"""
        page = page.replace(' ', '_')
        if namespace:
            namespace = namespace.replace(' ', '_')
            url = f"{self.url}/wiki/{namespace}:{page}"
        else:
            url = f"{self.url}/wiki/{page}"

        if params:
            url += ("?" + urlencode(params))

        return url

    def discussions_url(self, thread_id, reply_id=None):
        """Returns URL to the given post in discussions"""
        url = f"{self.url}/f/p/{thread_id}"
        if reply_id:
            url += f"/r/{reply_id}"
        return url
    
    def tag_url(self, article_name):
        """Returns URL to the given tag discussions"""
        return f"{self.url}/f/t/{article_name.replace(' ', '_')}"

    async def query_mw(self, params=None):
        """Performs request to MediaWiki api with given params"""
        self.client.logger.debug(f"Requesting api for wiki {self.url} with params: {params!r}")
        async with self.session.get(self.url + "/api.php", params=params) as resp:
            res = await resp.json()
            self.client.logger.debug(f"For request for wiki {self.url}, recieved {res}")
            return res

    async def query_nirvana(self, **params):
        """Queries Nirvana with given params"""

        if not self.url:
            raise RuntimeError("Wiki url is required to do this")

        params["format"] = "json"
        async with self.session.get(self.url + "/wikia.php", params=params) as resp:
            if resp.status != 204:
                return await resp.json()

    async def fetch_rc(self, *, limit=None, types=None, show=None, recent_changes_props=None, logevents_props=None, before=None, after=None, namespaces=None):
        """Fetches recent changes data from MediaWiki api"""
        
        params = {
            "action": "query",
            "list": "recentchanges|logevents",
            "format": "json"
        }
        if limit:
            params["rclimit"] = limit
            params["lelimit"] = limit
        if types:
            params["rctype"] = "|".join(types)
        if show:
            params["rcshow"] = "|".join(show)
        if recent_changes_props:
            params["rcprop"] = "|".join(recent_changes_props)
        if logevents_props:
            params["leprop"] = "|".join(logevents_props)
        if after:
            params["rcend"] = after.replace(microsecond=0).isoformat() + "Z"
            params["leend"] = after.replace(microsecond=0).isoformat() + "Z"
        if before:
            params["rcstart"] = before.replace(microsecond=0).isoformat() + "Z"
            params["lestart"] = before.replace(microsecond=0).isoformat() + "Z"
        if namespaces:
            params["namespaces"] = "|".join([str(ns) for ns in namespaces])
        
        return await self.query_mw(params)
        
    async def fetch_social_activity(self, *, after=None):
        """Fetches data about latest social activity"""
        params = {
            "uselang": "en"
        }
        if after:
            params["lastUpdateTime"] = after.timestamp()
            
        data = await self.query_nirvana(controller="ActivityApiController", method="getSocialActivity", **params) or []

        return data
    
    async def fetch_recent_posts(self):
        """Fetches the list of recent posts."""
        return await self.query_nirvana(controller="DiscussionPost", method="getPosts")
    