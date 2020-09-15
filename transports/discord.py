import textwrap

from discord import Embed, Webhook, AsyncWebhookAdapter

from core.abc import Transport # pylint: disable = no-name-in-module

def chunks(lst, n):
    """Yield successive n-sized chunks from list. Was taken from https://stackoverflow.com/a/1751478/11393726"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

class DiscordTransport(Transport):

    def prepare(self, data):
        if data["type"] in ("discussions", "wall", "comment"):
            return self._prepare_post(data)
        elif data["type"] == "log":
            return self._prepare_log(data)
        else:
            return self._prepare_edit(data)
    
    def _prepare_post(self, data):
        if data["type"] == "discussions":
            if data["data"]["is_reply"]:
                header = (":incoming_envelope: Оставлено [сообщение]({message_url}) в теме «**[{thread_title}]({thread_url})**»\n"
                          ":dividers: В категории «**[{category_name}]({wiki_url}/f?catId={category_id})**»"
                         ).format(
                            message_url=self.wiki.discussions_url(data['data']['thread_id'], data['id']), 
                            thread_url=self.wiki.discussions_url(data['data']['thread_id']), 
                            thread_title=data['data']['title'],
                            wiki_url=self.wiki.url,
                            category_id=data['data']['forum_id'],
                            category_name=data['data']['forum_name']
                         )
            else:
                header = ("incoming_envelope: Создана тема «**[{thread_title}]({thread_url})**»\n"
                          ":dividers: В категории «**[{category_name}]({wiki_url}/f?catId={category_id})**»"
                         ).format(
                            thread_url=self.wiki.discussions_url(data['id']), 
                            thread_title=data['data']['title'],
                            wiki_url=self.wiki.url,
                            category_id=data['data']['forum_id'],
                            category_name=data['data']['forum_name']
                         )
        elif data["type"] == "wall":
            if data["data"]["is_reply"]:
                header = (":incoming_envelope: Оставлено [сообщение]({thread_url}#{message_id}) в теме «**[{thread_title}]({thread_url})**»\n"
                          ":dividers: На стене участника **[{username}]({wall_url})**"
                         ).format(
                            message_id=data['id'], 
                            thread_url=self.wiki.url_to(data['author']['name'], namespace='Message Wall', thread_id=data['data']['thread_id']), 
                            thread_title=data['data']['title'],
                            wall_url=self.wiki.url_to(data['author']['name'], namespace='Message Wall'),
                            username=data['author']['name']
                         )
            else:
                header = (":incoming_envelope: Создана тема «**[{thread_title}]({thread_url})**»\n"
                          ":dividers: На стене участника **[{username}]({wall_url})**"
                         ).format(
                            thread_url=self.wiki.url_to(data['author']['name'], namespace='Message Wall', thread_id=data['id']), 
                            thread_title=data['data']['title'],
                            wall_url=self.wiki.url_to(data['author']['name'], namespace='Message Wall'),
                            username=data['author']['name']
                         )
        elif data["type"] == "comment":
            if data["data"]["is_reply"]:
                header = f":incoming_envelope: Оставлен ответ на комментарий к статье."
            else:
                header = f"incoming_envelope: Добавлен комментарий к статье."
        em = Embed(description=header, timesatmp=data["datetime"])
        em.add_field(name="Текст сообщения",
                     value=textwrap.shorten(data["data"]["content"], width=500, placeholder="..."))
        em.set_author(name=data["author"]["name"],
                      url=self.wiki.url_to("User:" + data["author"]["name"].replace(" ", "_")),
                      icon_url=data["author"]["avatar"])
        em.set_footer(text=self.wiki.url, icon_url=self.wiki.url_to("Special:FilePath/favicon.ico"))

        return em

    def _prepare_log(self, data):
        pass

    def _prepare_edit(self, data):
        pass
    
    async def send(self, data):
        data = [entry for entry in data if isinstance(entry, Embed)]
        webhook = Webhook.from_url(self.url, adapter=AsyncWebhookAdapter(self.session))
        await webhook.send(embeds=data)

    async def execute(self, data):
        messages = [self.prepare(entry) for entry in data]

        for chunk in chunks(messages, 10):
            await self.send(chunk)
