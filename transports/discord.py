import textwrap

from discord import Embed, Webhook

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
                header = ("➤ **Действие**: [сообщение]({message_url}) в обсуждениях\n"
                          "➤ **Тема**: [{thread_title}]({thread_url})\n"
                          "➤ **Категория**: [{category_name}]({wiki_url}/f?catId={category_id})"
                         ).format(
                            message_url=self.wiki.discussions_url(data["data"]["thread_id"], data["id"]), 
                            thread_url=self.wiki.discussions_url(data["data"]["thread_id"]), 
                            thread_title=data["data"]["title"],
                            wiki_url=self.wiki.url,
                            category_id=data["data"]["forum_id"],
                            category_name=data["data"]["forum_name"]
                         )
            else:
                header = ("➤ **Действие**: новая тема в обсуждениях\n"
                          "➤ **Название**: [{thread_title}]({thread_url})\n"
                          "➤ **Категория**: [{category_name}]({wiki_url}/f?catId={category_id})\n"
                          "➤ **Теги**: {tags}"
                         ).format(
                            thread_url=self.wiki.discussions_url(data["id"]), 
                            thread_title=data["data"]["title"],
                            wiki_url=self.wiki.url,
                            category_id=data["data"]["forum_id"],
                            category_name=data["data"]["forum_name"],
                            tags=", ".join([f"[{tag}]({self.wiki.tag_url(tag)})" for tag in data["data"]["tags"]]) if data["data"]["tags"] else "—"
                         )
        elif data["type"] == "wall":
            if data["data"]["is_reply"]:
                header = ("➤ **Действие**: [сообщение]({thread_url}#{message_id}) на стене\n"
                          "➤ **Тема**: [{thread_title}]({thread_url})"
                          "➤ **Стена участника**: [{username}]({wall_url})"
                         ).format(
                            message_id=data["id"], 
                            thread_url=self.wiki.url_to(data["author"]["name"], namespace="Message Wall", thread_id=data["data"]["thread_id"]), 
                            thread_title=data["data"]["title"],
                            wall_url=self.wiki.url_to(data["author"]["name"], namespace="Message Wall"),
                            username=data["author"]["name"]
                         )
            else:
                header = ("➤ **Действие**: новая тема на стене\n"
                          "➤ **Название**: [{thread_title}]({thread_url})\n"
                          "➤ **Стена участника**: [{username}]({wall_url})"
                         ).format(
                            thread_url=self.wiki.url_to(data["author"]["name"], namespace="Message Wall", thread_id=data["id"]), 
                            thread_title=data["data"]["title"],
                            wall_url=self.wiki.url_to(data["author"]["name"], namespace="Message Wall"),
                            username=data["author"]["name"]
                         )
        elif data["type"] == "comment":
            if data["data"]["is_reply"]:
                header = f"➤ **Действие**: ответ на комментарий к статье."
            else:
                header = f"➤ **Действие**: комментарий к статье."
        em = Embed(description=header, timesatmp=data["datetime"], color=0x2f3136)
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
        webhook = Webhook.from_url(self.url, session=self.session)
        await webhook.send(embeds=data)

    async def execute(self, data):
        messages = [self.prepare(entry) for entry in data]

        for chunk in chunks(messages, 10):
            await self.send(chunk)
