import enum
from dataclasses import dataclass

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fandom.wiki import Wiki
    from datetime import datetime
    from fandom.account import Account

class ActionType(enum.Enum):
  edit = 1 << 0
  log = 1 << 1
  post = 1 << 2

class Action(enum.Enum):
    create_page = 1
    edit_page = 2

    delete_page = 3
    undelete_page = 4

    protect_page = 5
    change_protection_settings = 6
    unprotect_page = 7

    rename_page = 8

    upload_file = 9

    block_user = 10
    change_block_settings = 11
    unblock_user = 12

    change_user_rights = 13

    create_post = 14
    edit_post = 15


@dataclass
class Entry:
    type: ActionType 
    action: Action
    target: Any # a target the action was done against
    wiki: Wiki # a wiki the action was made on
    user: Account # an user who did that action
    summary: Optional[str]
    details: Any
    timestamp: datetime