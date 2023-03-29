from contextlib import suppress
from datetime import datetime
import re
import typing
from typing import List, Optional

from core.abc import Handler
from core.entry import Action, ActionType, BlockParams, Diff, Entry, Group, ProtectionData, ProtectionLevel, ProtectionParams, RenameParams
from fandom.account import Account
from fandom.page import Page, PageVersion, File
from fandom.wiki import Wiki


WIKILINK_REGEX = re.compile(r"\[\[(.+?)(?:\|(.*?))?\]\]([^ `\n]+)?")

def from_mw_timestamp(timestamp) -> datetime:
    return datetime.fromisoformat(timestamp[:-1])


class RCHandler(Handler):
    def __init__(self, client, wiki: Wiki):
        self.client = client
        self.wiki = wiki

    def handle_edit(self, data) -> Entry:
        author = Account(
            name=data["user"],
            id=data["userid"],
            wiki=self.wiki
        )

        page = Page(
            name=data["title"],
            id=data["pageid"],
            namespace=data["ns"],
            wiki=self.wiki
        )

        old_version = PageVersion(
            id=data["old_revid"],
            size=data["oldlen"],
            wiki=self.wiki
        )
        new_version = PageVersion(
            id=data["revid"],
            size=data["newlen"],
            wiki=self.wiki
        )
        diff = Diff(
            old=old_version,
            new=new_version
        )
        
        if data["type"] == "new":
            action = Action.create_page
        else:
            action = Action.edit_page

        return Entry(
            type=ActionType.edit,
            action=action,
            target=page,
            wiki=self.wiki,
            user=author,
            summary=self.render_summary(data["comment"]),
            details=diff,
            timestamp=from_mw_timestamp(data["timestamp"])
        )

    def handle_log(self, data) -> Entry:
        author = Account(
            name=data["user"],
            id=data["userid"],
            wiki=self.wiki
        )

        if data["type"] == "move":
            action = Action.rename_page
            old_page = Page(
                id=data["pageid"],
                name=data["title"],
                namespace=data["ns"],
                wiki=self.wiki
            )
            new_page = Page(
                id=data["pageid"],
                name=data["params"]["target_title"],
                namespace=data["params"]["target_ns"],
                wiki=self.wiki
            )
            target = old_page
            details = RenameParams(
                diff=Diff(old=old_page, new=new_page),
                suppress_redirect=data["params"].get("suppressredirect") is not None
            )
        elif data["type"] == "delete":
            if data["action"] == "delete":
                action = Action.delete_page
            else:
                action = Action.undelete_page
            
            target = Page(
                id=data["pageid"],
                name=data["title"],
                namespace=data["ns"],
                wiki=self.wiki
            )
            details = None
        elif data["type"] == "upload":
            if data["action"] == "upload":
                action = Action.upload_file
            elif data["action"] == "overwrite":
                action = Action.reupload_file
            else:
                action = Action.revert_file
            
            page = Page(
                id=data["pageid"],
                name=data["title"],
                namespace=data["ns"],
                wiki=self.wiki
            )
            target = File.from_page(page)
            details = None
        elif data["type"] == "protect":
            if data["action"] == "protect":
                action = Action.protect_page
            elif data["action"] == "modify":
                action = Action.change_protection_settings
            else:
                action = Action.unprotect_page

            details = ProtectionParams(cascade=data["params"].get("cascade") is not None)
            for detail in data["params"].get("details", []):
                if detail["expiry"] == "infinite":
                    expiry = None
                else:
                    expiry = from_mw_timestamp(detail["expiry"])

                protection_data = ProtectionData(
                    level=ProtectionLevel(detail["level"]),
                    expiry=expiry
                )
                setattr(details, detail["type"], protection_data)
            
            target = Page(
                id=data["pageid"],
                name=data["title"],
                namespace=data["ns"],
                wiki=self.wiki
            )
        elif data["type"] == "block":
            if data["action"] == "block":
                action = Action.block_user
            elif data["action"] == "reblock":
                action = Action.change_block_settings
            else:
                action = Action.unblock_user
            
            if data["action"] == "unblock":
                details = None
            else:
                params = data["params"]
                if params.get("expiry") is None:
                    expiry = None
                else:
                    expiry = from_mw_timestamp(params["expiry"])
                    
                details = BlockParams(
                    expiry=expiry,
                    autoblock_disabled="noautoblock" in params["flags"],
                    cannot_edit_talkpage="nousertalk" in params["flags"],
                    cannot_create_accounts="nocreate" in params["flags"]
                )

            target = Account(
                name=data["title"].split(":", 1)[1],
                id=0,
                wiki=self.wiki
            )
        elif data["type"] == "rights":
            action = Action.change_user_rights
            target = Account(
                name=data["title"].split(":", 1)[1],
                id=0,
                wiki=self.wiki
            )

            old: List[Group] = []
            new: List[Group] = []
            for index, metadata in enumerate([
                data["params"]["oldmetadata"],
                data["params"]["newmetadata"]
            ]):
                for group in metadata:
                    if group["expiry"] == "infinity":
                        expiry = None
                    else:
                        expiry = from_mw_timestamp(group["expiry"])
                    
                    if index == 0:
                        groups = old
                    else:
                        groups = new
                    groups.append(Group(
                        name=group["group"],
                        expiry=expiry
                    ))
            details = Diff(
                old=old,
                new=new
            )
        else:
            raise NotImplementedError("Other log types are not supported at this time")

        return Entry(
            type=ActionType.log,
            action=action,
            target=target,
            wiki=self.wiki,
            user=author,
            summary=self.render_summary(data["comment"]),
            details=details,
            timestamp=from_mw_timestamp(data["timestamp"])
        )
    
    def link_to_hyperlink(self, match: typing.Match) -> str:
        target: str = match.group(1)
        title: Optional[str] = match.group(2)

        if title == "":
            title = target.split(":")[-1]
        if title is None:
            title = target
        
        url = self.wiki.url_to(target)
        return f"[{title}](<{url}>)"

    def render_summary(self, text: Optional[str]) -> Optional[str]:
        self.client.logger.debug("Rendering summary: " + str(text))
        if text is None:
            return None

        for match in WIKILINK_REGEX.finditer(text):
            self.client.logger.debug("Match found: " + match.group(0))
            text = text.replace(match.group(0), self.link_to_hyperlink(match), 1)
        
        return text
    
    def handle(self, data):
        handled_data: List[Entry] = []

        for entry in data["query"]["recentchanges"]:
            handled_data.append(self.handle_edit(entry))

        for entry in data["query"]["logevents"]:
            with suppress(NotImplementedError):
                handled_data.append(self.handle_log(entry))
        
        return handled_data
