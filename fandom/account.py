from dataclasses import dataclass
from typing import TYPE_CHECKING

from .wiki import Wiki

@dataclass
class Account:
    """
    Represents an account on Fandom.
    """
    name: str
    id: int
    wiki: Wiki

    @property
    def avatar_url(self):
        return f"https://services.fandom.com/user-avatar/user/{self.id}/avatar"

    @property
    def page_url(self):
        return self.wiki.url_to(f"User:{self.name}")