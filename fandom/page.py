from dataclasses import dataclass
from typing import Optional

from .wiki import Wiki

@dataclass
class PartialPage:
    name: str
    wiki: Wiki

    @property
    def url(self):
        return self.wiki.url_to(self.name)
    
@dataclass
class Page(PartialPage):
    id: int
    namespace: int

@dataclass
class PageVersion:
    id: int
    size: int
    content: Optional[str] = None