from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Union

from fandom.page import PartialPage
from .account import Account
if TYPE_CHECKING:
    from .wiki import Wiki

@dataclass
class Category:
    id: int
    title: str
    wiki: "Wiki"

    @property
    def url(self):
        return f"{self.wiki.url}/f?catId={self.id}"

@dataclass
class Thread:
    id: int
    title: Optional[str]
    parent: Union[Account, Category, PartialPage]
    first_post: Optional["Post"]
    posts: List["Post"]

    @property
    def url(self):
        if isinstance(self.parent, Account):
            return f"{self.parent.wall_url}?threadId={self.id}"
        elif isinstance(self.parent, PartialPage):
            return f"{self.parent.url}?commentId={self.id}"
        return self.parent.wiki.discussions_url(self.id)

@dataclass
class Post:
    id: int
    text: str
    parent: Thread
    author: Optional[Account]
    timestamp: Optional[datetime]

    @property
    def url(self):
        if isinstance(self.parent.parent, Account):
            return f"{self.parent.url}#{self.id}"
        elif isinstance(self.parent.parent, PartialPage):
            return f"{self.parent.url}&replyId={self.id}"
        return self.parent.parent.wiki.discussions_url(self.parent.id, self.id)