from typing import List

from datetime import datetime, timezone
from core.abc import Handler
from core.entry import Action, ActionType, Diff, Entry
from fandom.account import Account
from fandom.page import Page, PageVersion

def from_mw_timestamp(timestamp) -> datetime:
    return datetime.fromisoformat(timestamp[:-1]).replace(tzinfo=timezone.utc)

class RCHandler(Handler):
    def __init__(self, client, wiki):
        self.client = client
        self.wiki = wiki

    def handle_edit(self, data):
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

    def handle_log(self, entry):
        pass
    
    def handle(self, data):
        handled_data: List[Entry] = []

        for entry in data["query"]["recentchanges"]:
            handled_data.append(self.handle_edit(entry))

        for entry in data["query"]["logevents"]:
            if entry["type"] == "create":
                continue
            handled_data.append(self.handle_log(entry))
        
        return handled_data
