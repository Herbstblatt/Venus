from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .wiki import Wiki

@dataclass
class PartialPage:
    name: str
    wiki: "Wiki"

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
    wiki: "Wiki"
    content: Optional[str] = None

    @property
    def diff_url(self):
        return self.wiki.url_to(f"Special:Diff/{self.id}")