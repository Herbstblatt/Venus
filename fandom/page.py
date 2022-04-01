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
class File:
    page: Page
    name: str

    @property
    def url(self):
        return self.page.wiki.url_to("Special:FilePath/" + self.name)

    @classmethod
    def from_page(cls, page: Page):
        return cls(
            page=page,
            name=page.name
        )

@dataclass
class PageVersion:
    id: int
    size: int
    content: Optional[str] = None