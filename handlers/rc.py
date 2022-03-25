from core.abc import Handler

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