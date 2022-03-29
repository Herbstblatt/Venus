from contextlib import suppress
from typing import List

from datetime import datetime, timezone
from core.abc import Handler
from core.entry import Action, ActionType, Diff, Entry, RenameParams
from fandom.account import Account
from fandom.page import Page, PageVersion

def from_mw_timestamp(timestamp) -> datetime:
    return datetime.fromisoformat(timestamp[:-1]).replace(tzinfo=timezone.utc)

class RCHandler(Handler):
    def __init__(self, client, wiki):
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
        )
        new_version = PageVersion(
            id=data["revid"],
            size=data["newlen"]
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
            summary=data["comment"],
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
        else:
            raise NotImplementedError("Other log types are not supported at this time")

        return Entry(
            type=ActionType.log,
            action=action,
            target=target,
            wiki=self.wiki,
            user=author,
            summary=data["comment"],
            details=details,
            timestamp=from_mw_timestamp(data["timestamp"])
        )

    def handle(self, data):
        handled_data: List[Entry] = []

        for entry in data["query"]["recentchanges"]:
            handled_data.append(self.handle_edit(entry))

        for entry in data["query"]["logevents"]:
            with suppress(NotImplementedError):
                handled_data.append(self.handle_log(entry))
        
        return handled_data
