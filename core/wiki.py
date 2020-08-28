import asyncio
import aiohttp

from ..transports import discord # pylint: disable = relative-beyond-top-level

class InvalidTransportType(Exception):
    pass

class Wiki:
    def __init__(self, wiki_id, url, last_check_time, session):
        self.url = url
        self.id = wiki_id
        self.last_check_time = last_check_time
        self.session = session
        self.transports = []
    
    def add_transport(self, type, url):
        """Adds a new transport to the list of wiki transports."""
        if type == "discord":
            self.transports.append(discord.DiscordTransport(url=url, session=self.session))
        else:
            raise InvalidTransportType

    def url_to(self, page):
        """Returns URL to the given page"""
        return self.url + "/wiki/" + page.replace(" ", "_")

    async def api(self, params=None):
        """Performs request to MediaWiki api with given params"""
        async with self.session.get(self.url + "/api.php", params=params) as resp:
            return await resp.json()

    async def services(self, service, url, params=None):
        """Performs request to Fandom services api with given params"""
        async with self.session.get(f"https://services.fandom.com/{service}/{self.id}/{url}", params=params) as resp:
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
            params["rcend"] = after.isoformat() + "Z"
            params["leend"] = after.isoformat() + "Z"
        if before:
            params["rcstart"] = before.isoformat() + "Z"
            params["lestart"] = before.isoformat() + "Z"
        if namespaces:
            params["namespaces"] = "|".join([str(ns) for ns in namespaces])
        
        return await self.api(params)
        
    async def fetch_posts(self, *, limit=None, containers=["ARTICLE_COMMENT", "FORUM", "WALL"], before=None, after=None):
        """Fetches data about latest posts in discussions"""
        params = {}
        if limit:
            params["limit"] = limit
        if before:
            params["until"] = before.isoformat()[:-3] + "Z" # fandom doesn't accepting timestamps with six-digit milliseconds
        if after:
            params["since"] = after.isoformat()[:-3] + "Z" # same
            
        # we have three containers, but fandom supports filtering only by one of them
        if len(containers) != 2:
            # we can request data from all containers or from one specific
            if len(containers) == 1:
                params["containerType"] = params[0]
            data = await self.services("discussion", "posts", params)
        else:
            # we need to do two requests
            tasks = [self.services("discussion", "posts", {"containerType": t, **params}) for t in containers]
            data = await asyncio.gather(*tasks)
            data[0]["_embedded"]["doc:posts"].extend(data[1]["_embedded"]["doc:posts"])

        return data