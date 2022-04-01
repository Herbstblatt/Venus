import enum
from dataclasses import dataclass

from typing import Any, Generic, List, Optional, TypeVar, Union
from fandom.page import Page, PageVersion

from fandom.wiki import Wiki
from datetime import datetime
from fandom.account import Account

DiffT = TypeVar("DiffT")

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
    reupload_file = 10
    revert_file = 11

    block_user = 12
    change_block_settings = 13
    unblock_user = 14

    change_user_rights = 15

    create_post = 16
    edit_post = 17


@dataclass
class Diff(Generic[DiffT]):
    old: DiffT
    new: DiffT


# Edits
EditParams = Diff[PageVersion]


# Rename log
@dataclass
class RenameParams:
    diff: Diff[Page]
    suppress_redirect: bool


# Protection log
class ProtectionLevel(enum.Enum):
    everyone = 1
    autoconfirmed = 2
    sysop = 3

@dataclass
class ProtectionParams:
    create: Optional[ProtectionLevel]
    edit: Optional[ProtectionLevel]
    move: Optional[ProtectionLevel]
    comment: Optional[ProtectionLevel]
    upload: Optional[ProtectionLevel]

    cascading: bool


# Block log
@dataclass
class BlockParams:
    expiry: datetime
    autoblock_enabled: bool
    can_edit_talkpage: bool
    can_create_accounts: bool

# Rights log
@dataclass
class Group:
    name: str
    expiry: Optional[datetime]

RightsParams = Diff[List[Group]]


@dataclass
class Entry:
    type: ActionType 
    action: Action
    target: Any    # a target the action was done against
    wiki: Wiki     # a wiki the action was made on
    user: Account  # an user who did that action
    summary: Optional[str]
    details: Union[None, EditParams, RenameParams, ProtectionParams, BlockParams, RightsParams]
    timestamp: datetime
