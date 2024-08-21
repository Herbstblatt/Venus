import json
from bs4 import BeautifulSoup, Tag
import datetime
from typing import TYPE_CHECKING, List, Literal, cast
from urllib.parse import ParseResult, urlparse

from fandom.account import Account
from fandom.discussions import Category, Post, Thread
from fandom.page import PartialPage
from fandom.wiki import Wiki
from core.abc import Handler
from core.entry import Entry, Action, ActionType
from core.utils import extract_query_param

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


class DiscussionsHandler(Handler):
    def __init__(self, client: "Venus", wiki: Wiki):
        self.client = client
        self.wiki = wiki
        
    def get_action(self, data) -> Action:
        return action_lookup[data["actionType"]][data["contentType"]]


    def parse_text_from_json(self, data) -> str:
        text = ""
        
        match data["type"]:
            case "code_block":
                placeholder = "```{}```"
            case "paragraph":
                placeholder = "{}\n"
            case _:
                placeholder = "{}"
        
        content = data.get("content")
        if content:
            for node in content:
                if data["type"] == "bulletList":
                    text += "* "
                elif data["type"] == "orderedList":
                    text += "1. "
                
                text += self.parse_text_from_json(node)
        
        else:
            if data["type"] == "text":
                text = data["text"]
                for mark in data.get("marks", []):
                    match mark:
                        case {'type': 'strong'}:
                            text = f"**{text}**"
                        case {'type': 'em'}:
                            text = f"*{text}*"
                        case {'type': 'link', 'attrs': {'href': url}}:
                            text = f"[{text}]({url})"
                    
        return placeholder.format(text)
    

    def get_text(self, action_type: Literal["create", "update"], soup: BeautifulSoup, post_data: dict | None) -> str:
        if post_data is None or action_type == "update":
            return cast(Tag, soup.find("em")).text
        return self.parse_text_from_json(json.loads(post_data["jsonModel"])).strip()


    def handle_entry(self, social_activity_data, post_data, date: datetime.date) -> Entry:
        time = datetime.datetime.strptime(social_activity_data["time"], "%H:%M").time()
        timestamp = datetime.datetime.combine(date, time)
        content_type = social_activity_data["contentType"]
        action_type = social_activity_data["actionType"]
        action = self.get_action(social_activity_data)

        soup = BeautifulSoup(social_activity_data["label"])
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
                id=int(extract_query_param(cast(str, category_element.get("href")), "catId")),  # type: ignore
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
                text=self.get_text(action_type, soup, post_data),
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
                id=int(extract_query_param(cast(str, thread_element.get("href")), "threadId")),  # type: ignore
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
                text=self.get_text(action_type, soup, post_data),
                parent=thread,
                author=author_account,
                timestamp=timestamp,
            )

            if content_type == "message":
                first_post = post
            else:
                first_post = None
            posts = [post]

        elif content_type in ("comment", "comment-reply"):
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
                id=int(extract_query_param(url, "commentId")),  # type: ignore
                title=None,
                parent=page,
                posts=[],
                first_post=None
            )
            
            if content_type == "comment":
                first_post = Post(
                    id=thread.id,
                    text=self.get_text(action_type, soup, post_data),
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
                    id=int(extract_query_param(url, "replyId")),  # type: ignore
                    text=self.get_text(action_type, soup, post_data),
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


    def handle(self, data, posts) -> List[Entry]:
        result = []
        curr_post_idx = 0
        posts = posts["_embedded"]["doc:posts"]
        for day in data:
            date = datetime.datetime.strptime(day["date"], "%d %B %Y").date()
            for action in day["actions"]:
                entry_action = self.get_action(action)
                
                try:
                    curr_post = posts[curr_post_idx:curr_post_idx+1].get(0)  # this is done to avoid ListIndexOutOfRange
                    entry = self.handle_entry(action, curr_post, date=date)
                except Exception:
                    self.client.logger.warn("Invalid entry recieved, failed to handle", exc_info=True)
                else:
                    result.append(entry)
                
                if entry_action not in [Action.edit_comment, Action.edit_post, Action.edit_reply]:
                    curr_post_idx += 1

        return result
    
