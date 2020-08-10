import asyncio

class Wiki:
    def __init__(self, id, url, session):
        self.url = url
        self.id = id
        self.session = session
        self.transports = []
    
    def add_transport(self, type, url):
        """Adds a new transport to the list of wiki transports"""
        pass

    async def execute_transports(self, rc_data, posts_data):
        """Executes all transports that belongs to this wiki"""
        pass

    def url_to(self, page):
        """Returns URL to the given page"""
        pass

    async def api(self, params):
        """Performs request to MediaWiki api with given params"""
        pass

    async def fetch_rc(self, *, limit=None, props=None, before=None, after=None):
        """Fetches recent changes data from MediaWiki api"""
        pass

    async def fetch_posts(self, *, limit=None, props=None, before=None, after=None):
        """Fetches data about latest posts in discussions"""
        pass