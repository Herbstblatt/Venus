from bs4 import BeautifulSoup, Tag
import datetime
from typing import TYPE_CHECKING, List, Union, cast
from urllib.parse import ParseResult, parse_qs, urlparse

from fandom.account import Account
from fandom.discussions import Category, Post, Thread
from fandom.page import PartialPage
from fandom.wiki import Wiki
from core.abc import Handler
from core.entry import Entry, Action, ActionType

if TYPE_CHECKING:
    from core.client import Venus

action_lookup = {
    "create": {
        "post": Action.create_post,
        "message": Action.create_post,
        "post-reply": Action.create_reply,
        "message-reply": Action.create_reply,
        "comment": Action.create_comment,
        "comment-reply": Action.create_comment
    },
    "update": {
        "post": Action.edit_post,
        "message": Action.edit_post,
        "post-reply": Action.edit_reply,
        "message-reply": Action.edit_reply,
        "comment": Action.edit_comment,
        "comment-reply": Action.edit_comment
    },
}

def extract_query_param(url: Union[str, ParseResult], param: str) -> str:
    if isinstance(url, str):
        url = urlparse(url)
    return parse_qs(url.query)[param][0]

class DiscussionsHandler(Handler):
    def __init__(self, client: "Venus", wiki: Wiki):
        self.client = client
        self.wiki = wiki
        

    def handle_entry(self, data, date: datetime.date) -> Entry:
        time = datetime.datetime.strptime(data["time"], "%H:%M").time()
        timestamp = datetime.datetime.combine(date, time, tzinfo=datetime.timezone.utc)
        content_type = data["contentType"]
        action = action_lookup[data["actionType"]][content_type]

        soup = BeautifulSoup(data["label"])
        author = cast(Tag, soup.find(attrs={"data-tracking": "action-username__" + content_type})).text
        author_account = Account(name=author, id=0, wiki=self.wiki)
        
        posts: List[Post]
        if content_type in ("post", "post-reply"):
            if content_type == "post":
                category_class = "action-category__post"
            else:
                category_class = "action-post-reply-category__post-reply"

            category_element = cast(Tag, soup.find(attrs={"data-tracking": category_class}))
            category = Category(
                title=category_element.text,
                id=int(extract_query_param(cast(str, category_element.get("href")), "catId")),
                wiki=self.wiki
            )

            thread_element = cast(Tag, soup.find(attrs={"data-tracking": f"action-{content_type}__{content_type}"}))
            thread = Thread(
                id=int(cast(str, thread_element.get("href")).split("/")[-1]),
                title=thread_element.text,
                parent=category,
                posts=[],
                first_post=None
            )

            post_link = cast(Tag, soup.find(attrs={"data-tracking": f"action-view__{content_type}"})).get("href")
            post = Post(
                id=int(cast(str, post_link).split("/")[-1]),
                text=cast(Tag, soup.find("em")).text,
                parent=thread,
                author=author_account,
                timestamp=timestamp,
            )

            if content_type == "post":
                first_post = post
            else:
                first_post = None
            posts = [post]

        elif content_type in ("message", "message-reply"):
            if content_type == "message":
                thread_class = "action-wall-message__message"
            else:
                thread_class = "action-reply-message-wall-parent__message-reply"
            
            # this is guaranteed to be ParseResult until the api breaks
            url: ParseResult = urlparse(soup.find(attrs={"data-tracking": f"action-view__{content_type}"}).get("href")) # type: ignore
            target_account = Account(
                name=url.path.split(":")[-1].replace("_", " "),
                id=0,
                wiki=self.wiki
            )

            thread_element = cast(Tag, soup.find(attrs={"data-tracking": thread_class}))
            thread = Thread(
                id=int(extract_query_param(cast(str, thread_element.get("href")), "threadId")),
                title=thread_element.text,
                parent=target_account,
                posts=[],
                first_post=None
            )
            
            try:
                post_id = int(url.fragment)
            except ValueError:
                post_id = thread.id
            post = Post(
                id=post_id,
                text=cast(Tag, soup.find("em")).text,
                parent=thread,
                author=author_account,
                timestamp=timestamp,
            )

            if content_type == "message":
                first_post = post
            else:
                first_post = None
            posts = [post]

        elif content_type in ("comment", "comment_reply"):
            if content_type == "comment":
                page_class = "action-comment-article-name__comment"
            else:
                page_class = "action-reply-article-name__comment-reply"

            page_name = cast(Tag, soup.find(attrs={"data-tracking": page_class}))
            page = PartialPage(
                name=page_name.text,
                wiki=self.wiki
            )

            # this is guaranteed to be ParseResult until the api breaks
            url: ParseResult = urlparse(soup.find(attrs={"data-tracking": f"action-view__{content_type}"}).get("href")) # type: ignore
            thread = Thread(
                id=int(extract_query_param(url, "commentId")),
                title=None,
                parent=page,
                posts=[],
                first_post=None
            )
            
            if content_type == "comment":
                first_post = Post(
                    id=thread.id,
                    text=cast(Tag, soup.find("em")).text,
                    parent=thread,
                    author=author_account,
                    timestamp=timestamp,
                )
                posts = [first_post]
            else:
                first_post = Post(
                    id=thread.id,
                    text=cast(Tag, soup.find(
                        attrs={"data-tracking": f"action-reply-parent__comment-reply"}
                    )).text,
                    parent=thread,
                    author=None,
                    timestamp=None,
                )
                last_post = Post(
                    id=int(url.fragment),
                    text=cast(Tag, soup.find("em")).text,
                    parent=thread,
                    author=author_account,
                    timestamp=timestamp,
                )
                posts = [first_post, last_post]
        else:
            raise RuntimeError("Invalid data recieved")


        thread.posts = posts            
        thread.first_post = first_post  

        if content_type in ("post", "message", "comment"):
            target = thread
        else:
            target = posts[-1]
        
        return Entry(
            type=ActionType.post,
            action=action,
            target=target,
            wiki=self.wiki,
            user=author_account,
            summary=None,
            details=None,
            timestamp=timestamp
        )


    def handle(self, data) -> List[Entry]:
        result = []
        for day in data:
            date = datetime.datetime.strptime(day["date"], "%d %B %Y").date()
            for action in day["actions"]:
                try:
                    entry = self.handle_entry(action, date=date)
                except RuntimeError:
                    pass
                else:
                    result.append(entry)

        return result
    
    def get_text(self, data):
        text = ""
        content = data.get("content")
        if content:
            for node in content:
                text += self.get_text(node)
        else:
            if data["type"] == "text":
                text += data["text"]
        return text.strip()
