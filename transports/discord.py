from core.abc import Transport

class DiscordTransport(Transport):

    def prepare(self, data):
        pass
    
    async def send(self, data):
        pass