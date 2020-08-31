from datetime import datetime
import json

from .abc import Handler # pylint: disable=relative-beyond-top-level

class DiscussionsHandler(Handler):
    def __init__(self, client):
        self.client = client

    def handle(self, data):
        post_type = data["_embedded"]["thread"][0]["containerType"]
        handled = {
            "id": data["id"],
            "datetime": datetime.fromtimestamp(data["creationDate"]["epochSecond"]),
            "author": {
                "name": data["createdBy"]["name"],
                "id": data["createdBy"]["id"],
                "avatar": data["createdBy"]["avatarUrl"]
            },
            "data": {
                "content": data["rawContent"],
                "is_reply": data["isReply"]
            }
        }
        if data["isReply"]:
            handled["data"]["replying_to"] = data["threadCreatedBy"]["name"]
            handled["data"]["thread_id"] = data["_embedded"]["thread"][0]["firstPost"]["id"]

        if post_type == "FORUM":
            handled["type"] = "discussions"
            handled["data"]["title"] = data["title"]
            handled["data"]["forum"] = data["forumName"]
        elif post_type == "WALL":
            handled["type"] = "wall"
            handled["data"]["title"] = data["title"]
            handled["data"]["wall_owner"] = data["forumName"][:-13]
        elif post_type == "ARTICLE_COMMENT":
            handled["type"] = "comment"
            handled["data"]["content"] = self.get_text(json.loads(data["jsonModel"]))
        
        return handled
    
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
    def __init__(self, client):
        self.client = client

    def handle(self, data):
        handled = {
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

        return handled