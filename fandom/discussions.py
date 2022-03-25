from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Union

from .wiki import Wiki
from .account import Account

@dataclass
class Category:
    id: int
    title: str
    wiki: Wiki

    @property
    def url(self):
        return f"{self.wiki.url}/f?catId={self.id}"

@dataclass
class Thread:
    id: int
    title: Optional[str]
    parent: Union[Account, Category]
    first_post: Optional["Post"]
    posts: List["Post"]

    @property
    def url(self):
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
        return self.parent.parent.wiki.discussions_url(self.parent.id, self.id)