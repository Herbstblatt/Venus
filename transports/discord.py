from typing import TYPE_CHECKING, cast

import discord
from discord import Embed, Webhook

from core.abc import Transport # pylint: disable = no-name-in-module
from core.entry import Diff, Entry, ActionType
from fandom.page import Page, PageVersion

def chunks(lst, n):
    """Yield successive n-sized chunks from list. Was taken from https://stackoverflow.com/a/1751478/11393726"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

class DiscordTransport(Transport):

    def __init__(self, wiki, url, client):
        super().__init__(wiki, url, client)
        self.webhook = Webhook.from_url(self.url, session=self.session)  

    def prepare(self, data: "Entry") -> Embed:
        if data.type is ActionType.post:
            embed = self._prepare_post(data)
        elif data.type is ActionType.log:
            embed = self._prepare_log(data)
        else:
            embed = self._prepare_edit(data)
        
        if data.summary:
            embed.add_field(name="Причина", value=data.summary)
        embed.set_author(name=data.user.name, url=data.user.page_url, icon_url=data.user.avatar_url)
        embed.timestamp = data.timestamp
        return embed
    
    def _prepare_edit(self, data: "Entry") -> Embed:
        assert isinstance(data.target, Page)
        assert isinstance(data.details, Diff) and isinstance(data.details.old, PageVersion)
        
        diff = data.details.new.size - data.details.old.size
        if diff >= 0:
            diff_msg = "diff-added"
        else:
            diff_msg = "diff-removed"

        em = Embed(
            title=self.client.l10n.format_value("edit-page", dict(target=data.target.name)),
            url=data.target.url,
            description=(
                "<:venus_edit:941018307421679666> " +
                self.client.l10n.format_value(diff_msg, dict(diff=diff))
            ),
            color=discord.Color.green()
        )
        return em

    def _prepare_log(self, data: "Entry") -> Embed:
        pass

    def _prepare_post(self, data: "Entry")-> Embed:
        pass
    
    async def send(self, data: Embed):
        await self.webhook.send(embed=data)

    async def execute(self, data: list["Entry"]):
        for entry in data:
            try:
                embed = self.prepare(entry)
            except:
                self.client.logger.exception("Error while processing entry")
            else:
                await self.send(embed)
