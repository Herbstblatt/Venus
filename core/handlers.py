from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Union
from urllib.parse import ParseResult, parse_qs, urlparse

from bs4 import BeautifulSoup

from fandom.account import Account
from fandom.discussions import Category, Post, Thread
from fandom.page import PartialPage
from fandom.wiki import Wiki
from .abc import Handler
from .entry import Entry, Action, ActionType
if TYPE_CHECKING:
    from .client import Venus

action_lookup = {
    "create": Action.create_post,
    "update": Action.edit_post
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
        time = datetime.strptime(data["time"], "%H:%M").time()
        timestamp = datetime.combine(date, time, tzinfo=timezone.utc)
        action = action_lookup[data["actionType"]]
        content_type = data["contentType"]

        soup = BeautifulSoup(data["label"])
        author = soup.find(attrs={"data-tracking": "action-username__" + content_type}).text
        author_account = Account(name=author, id=0, wiki=self.wiki)
        
        if content_type in ("post", "post-reply"):
            if content_type == "post":
                category_class = "action-category__post"
            else:
                category_class = "action-post-reply-category__post-reply"

            category_element = soup.find(attrs={"data-tracking": category_class})
            self.client.logger.debug(category_element.get("href"))
            category = Category(
                title=category_element.text,
                id=int(extract_query_param(category_element.get("href"), "catId")),
                wiki=self.wiki
            )

            thread_element = soup.find(attrs={"data-tracking": f"action-{content_type}__{content_type}"})
            thread = Thread(
                id=thread_element.get("href").split("/")[-1],
                title=thread_element.text,
                parent=category,
                posts=[],
                first_post=None
            )

            post_link = soup.find(attrs={"data-tracking": f"action-view__{content_type}"}).get("href")
            post = Post(
                id=int(post_link.split("/")[-1]),
                text=soup.find("em").text,
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
            
            url: ParseResult = urlparse(soup.find(attrs={"data-tracking": f"action-view__{content_type}"}).get("href"))
            target_account = Account(
                name=url.path.split(":")[-1],
                id=0,
                wiki=self.wiki
            )

            thread_element = soup.find(attrs={"data-tracking": thread_class})
            thread = Thread(
                id=int(extract_query_param(thread_element.get("href"), "threadId")),
                title=thread_element.text,
                parent=target_account,
                posts=[],
                first_post=None
            )
            post = Post(
                id=int(url.fragment),
                text=soup.find("em").text,
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

            page_name = soup.find(attrs={"data-tracking": page_class})
            page = PartialPage(
                name=page_name,
                wiki=self.wiki
            )

            url: ParseResult = urlparse(soup.find(attrs={"data-tracking": f"action-view__{content_type}"}).get("href"))
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
                    text=soup.find("em").text,
                    parent=thread,
                    author=author_account,
                    timestamp=timestamp,
                )
                posts = [first_post]
            else:
                first_post = Post(
                    id=thread.id,
                    text=soup.find(
                        attrs={"data-tracking": f"action-reply-parent__comment-reply"}
                    ).text,
                    parent=thread,
                    author=None,
                    timestamp=None,
                )
                last_post = Post(
                    id=int(url.fragment),
                    text=soup.find("em").text,
                    parent=thread,
                    author=author_account,
                    timestamp=timestamp,
                )
                posts = [first_post, last_post]


        thread.posts = posts
        thread.first_post = first_post

        if content_type in ("post", "message", "comment"):
            target = thread
        else:
            target = post
        
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
            date = datetime.strptime(day["date"], "%d %B %Y").date()
            for action in day["actions"]:
                result.append(self.handle_entry(action, date=date))

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


class RCHandler(Handler):
    def __init__(self, client, wiki):
        self.client = client
        self.wiki = wiki

    def handle(self, data):
        """handled = {
            "type": data["type"],
            "datetime": datetime.fromisoformat(data["timestamp"][:-1]),
            "author": {
                "name": data["user"],
                "id": data["userid"],
                "avatar": f"https://services.fandom.com/user-avatar/user/{data['userid']}/avatar"
            },
            "data": {
                "title": data["title"],
                "comment": data["comment"]
            }
        }
        if data["type"] in ("edit", "new", "categorize"):
            handled["data"].update({
                "revid": data["revid"],
                "old_revid": data["old_revid"],
                "oldlen": data["oldlen"],
                "newlen": data["newlen"]
            })
        else:
            handled["type"] = "log"
            handled["data"]["logparams"] = {
                "type": data["type"],
                "action": data["action"],
                **data["params"]
            }

        return handled"""
        return []