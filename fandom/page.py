from dataclasses import dataclass

from .wiki import Wiki

@dataclass
class PartialPage:
    name: str
    wiki: Wiki

    @property
    def url(self):
        return self.wiki.url_to(self.name)
    
class Page(PartialPage):
    id: int
    description: str