from typing import TYPE_CHECKING, cast

import discord
from discord import Embed, Webhook

from core.abc import Transport
from core.entry import Action, BlockParams, Diff, Entry, ActionType, ProtectionParams, RenameParams, RightsParams
from fandom.account import Account
from fandom.discussions import Category, Post, Thread
from fandom.page import File, Page, PageVersion, PartialPage

ICONS = {
    "create": "<:venus_edit:941018307421679666>",
    "edit": "<:venus_edit:941018307421679666>",
    "move": "<:venus_update:957216367470329876>",
    "comment": "<:venus_post:941048824426790944>",
    "upload": "<:venus_upload:941050114896691271>",
    "arrow": "<:venus_arrow:1073621942617251890>",
    "info": "<:venus_info:1073623049666039870>",
    "expiry": "<:venus_expiry:1073628893422026872>",
    "category": "<:venus_post_category:966008360103202956>",
    "user": "<:user:966009692117667882>"
}

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
        
        match data.target:
            case (
                Thread(parent=PartialPage(name=title))
                | Thread(title=title)
                | Post(parent=Thread(parent=PartialPage(name=title)))
                | Post(parent=Thread(title=title))
            ):
                target_name = title
            case _:
                target_name = data.target.name
        embed.title = self.client.l10n.format_value(
            str(data.action)[7:].replace("_", "-"),
            dict(target=target_name)
        )
        
        if isinstance(data.target, Account):
            embed.url = data.target.page_url
        else:
            embed.url = data.target.url
        
        if data.summary:
            embed.add_field(name="Причина", value=data.summary, inline=False)
        
        embed.set_author(name=data.user.name, url=data.user.page_url, icon_url=data.user.avatar_url)
        embed.timestamp = data.timestamp
        return embed
    
    def _prepare_edit(self, data: "Entry") -> Embed:
        assert isinstance(data.target, Page)
        assert isinstance(data.details, Diff) and isinstance(data.details.old, PageVersion) and isinstance(data.details.new, PageVersion)
        
        diff = data.details.new.size - data.details.old.size
        if diff >= 0:
            diff_msg = "diff-added"
        else:
            diff_msg = "diff-removed"

        em = Embed(
            title=self.client.l10n.format_value("edit-page", dict(target=data.target.name)),
            url=data.target.url,
            description="{icon} {message} ([{diff_message}]({url}))".format(
                icon="<:venus_edit:941018307421679666> ",
                message=self.client.l10n.format_value(diff_msg, dict(diff=diff)),
                diff_message=self.client.l10n.format_value("changes"),
                url=data.details.new.diff_url
            ),
            color=discord.Color.green()
        )
        return em

    def _prepare_log(self, data: "Entry") -> Embed:
        em = Embed()
        description = ""
        match data.action:
            case Action.protect_page | Action.change_protection_settings:
                assert isinstance(data.details, ProtectionParams)
                for name, param in iter(data.details):
                    if param.expiry:
                        expiry = " ({string} {date})".format(
                            string=self.client.l10n.format_value("expiry").lower(), 
                            date=discord.utils.format_dt(param.expiry)
                        )
                    else:
                        expiry = ""
                        
                    description += "{icon} {name}: {level}{expiry}\n".format(
                        icon=ICONS[name],
                        name=self.client.l10n.format_value(name + "-protection"),
                        level=self.client.l10n.format_value("protection-level-" + str(param.level)[16:]),
                        expiry=expiry
                    )
            
            case Action.rename_page:
                assert isinstance(data.details, RenameParams)
                description += "*{old_name}* {arrow} **[{new_name}]({link})**".format(
                    arrow=ICONS["arrow"],
                    old_name=data.details.diff.old.name,
                    new_name=data.details.diff.new.name,
                    link=data.details.diff.new.url
                )
                if data.details.suppress_redirect:
                    description += "\n{icon} {message}".format(
                        icon=ICONS["info"],
                        message=self.client.l10n.format_value("suppress-redirect")
                    )
            
            case Action.upload_file | Action.reupload_file | Action.revert_file:
                assert isinstance(data.target, File)
                em.set_image(url=data.target.url)

            case Action.block_user | Action.change_block_settings:
                assert isinstance(data.details, BlockParams)
                
                if data.details.expiry:
                    date = "{date} ({relative})".format(
                        date=discord.utils.format_dt(data.details.expiry),
                        relative=discord.utils.format_dt(data.details.expiry, "R")
                    )
                else:
                    date = "*{message}*".format(
                        message=self.client.l10n.format_value("infinite-block")
                    )
                description += "{icon} {message}: {date}".format(
                    icon=ICONS["expiry"],
                    message=self.client.l10n.format_value("expiry"),
                    date=date
                )

                for name, value in data.details:
                    if value:   
                        description += "\n{icon} {message}".format(
                            icon=ICONS["info"],
                            message=self.client.l10n.format_value(name.replace("_", "-"))
                        )

            case Action.change_user_rights:
                data.details = cast(RightsParams, data.details)
                
                added_groups = []
                for group in data.details.new:
                    if group in data.details.old:
                        continue
                    
                    if group.expiry:
                        expiry = " ({string} {date})".format(
                            string=self.client.l10n.format_value("expiry").lower(), 
                            date=discord.utils.format_dt(group.expiry)
                        )
                    else:
                        expiry = ""
                    
                    added_groups.append("`{name}`{expiry}".format(
                        name=group.name,
                        expiry=expiry
                    ))
                
                removed_groups = []
                for group in data.details.old:
                    if group in data.details.new:
                        continue
                    removed_groups.append(f"`{group.name}`")
                
                if added_groups:
                    em.add_field(
                        name=self.client.l10n.format_value("added-groups"),
                        value="\n".join(added_groups)
                    )
                if removed_groups:
                    em.add_field(
                        name=self.client.l10n.format_value("removed-groups"),
                        value="\n".join(removed_groups)
                    )

        match data.action:
            case Action.delete_page:
                em.color = discord.Color.red()
            case (
                Action.undelete_page 
                | Action.protect_page
                | Action.change_protection_settings
                | Action.unprotect_page
                | Action.rename_page
            ):
                em.color = discord.Color.gold()
            case (
                Action.upload_file
                | Action.reupload_file
                | Action.revert_file
            ):
                em.color = discord.Color.blue()
            case _:
                em.color = discord.Color.orange()

        
        em.description = description
        return em

    def _prepare_post(self, data: "Entry")-> Embed:
        if isinstance(data.target, Thread):
            text = data.target.first_post.text  # type: ignore
        elif isinstance(data.target, Post):
            text = data.target.text
        else:
            raise RuntimeError("invalid data recieved")
        
        em = discord.Embed(color=discord.Color.purple())
        em.add_field(
            name=self.client.l10n.format_value("text"),
            value=text
        )

        match data.target.parent:
            case Account(name=name, page_url=page_url) | Thread(parent=Account(name=name, page_url=page_url)):
                em.description = "{icon} {message}".format(
                    icon=ICONS["user"],
                    message=self.client.l10n.format_value(
                        "talkpage", 
                        dict(title=f"**[{name}]({page_url})**")
                    )
                )
            case Category(title=title, url=url) | Thread(parent=Category(title=title, url=url)):
                em.description = "{icon} {message}".format(
                    icon=ICONS["category"],
                    message=self.client.l10n.format_value(
                        "category", 
                        dict(title=f"**[{title}]({url})**")
                    )
                )

        return em
    
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
