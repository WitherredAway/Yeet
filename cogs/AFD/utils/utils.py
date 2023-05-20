from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Union
import discord
import pandas as pd
from cogs.AFD.utils.labels import (
    APPROVED_LABEL,
    CMT_LABEL,
    IMAGE_LABEL,
    PKM_LABEL,
    USER_ID_LABEL,
    USERNAME_LABEL,
)

from cogs.utils.utils import RoleMenu

if TYPE_CHECKING:
    from cogs.AFD.utils.sheet import AfdSheet


class EmbedColours(Enum):
    INVALID: int = 0xCB3F49  # Invalid, Red
    UNCLAIMED: int = 0x6D6F77  # Not claimed, Grey
    CLAIMED: int = 0xE69537  # Claimed but not complete, Orange
    UNREVIEWED: int = 0x6BAAE8  # Link present awaiting review, Blue
    CORRECTION: int = 0xF5CD6B  # Has a comment, Yellow
    COMPLETED: int = 0x85AF63  # Link present and approved, Green


@dataclass
class Row:
    row: Union[pd.DataFrame, pd.Series]

    dex: Optional[int] = None
    pokemon: Optional[str] = None
    username: Optional[discord.User] = None
    user_id: Optional[int] = None
    image: Optional[str] = None
    approved_by: Optional[int] = None
    comment: Optional[str] = None

    claimed: Optional[bool] = None
    unreviewed: Optional[bool] = None
    completed: Optional[bool] = None
    correction_pending: Optional[bool] = None

    def __post_init__(self):
        self.dex = self.row.index.values[0]
        if isinstance(self.row, pd.DataFrame):
            self.row = self.row.loc[self.dex, :]

        self.pokemon = self.row[PKM_LABEL]

        self.username = self.row[USERNAME_LABEL]
        self.username = (
            discord.utils.escape_markdown(self.username)
            if not pd.isna(self.username)
            else None
        )

        self.user_id = self.row[USER_ID_LABEL]
        self.user_id = int(self.user_id) if not pd.isna(self.user_id) else None

        self.image = self.row[IMAGE_LABEL]
        self.image = self.image if not pd.isna(self.image) else None

        self.approved_by = self.row[APPROVED_LABEL]
        self.approved_by = (
            int(self.approved_by) if not pd.isna(self.approved_by) else None
        )

        self.comment = self.row[CMT_LABEL]
        self.comment = self.comment if not pd.isna(self.comment) else None

        self.claimed = not pd.isna(self.user_id)
        self.unreviewed = all((self.image, not self.approved_by, not self.comment))
        self.completed = all(
            (self.approved_by, not self.comment)
        )  # If approved but no comment
        self.correction_pending = all((self.comment, self.approved_by))


class AFDRoleMenu(RoleMenu):
    def __init__(self):
        roles_dict = {
            "AFD": discord.ButtonStyle.green,
            "AFD Admin": discord.ButtonStyle.red,
        }
        super().__init__(roles_dict)


COMPLETED_EMOJI = "✅"
UNREVIEWED_EMOJI = "☑️"
REVIEW_EMOJI = "❗"


@dataclass
class Claimed:
    claimed_df: pd.DataFrame
    sheet: AfdSheet

    def __post_init__(self):
        self.correction_pending = []
        self.claimed = []
        self.unreviewed = []
        self.completed = []
        for idx in self.claimed_df.index:
            row = self.sheet.get_row(idx)
            pkm = row.pokemon

            if row.completed:
                self.completed.append(pkm)
            elif row.unreviewed:
                self.unreviewed.append(pkm)
            elif row.correction_pending:
                self.correction_pending.append(pkm)
            else:
                self.claimed.append(pkm)

        self.total = (
            self.correction_pending + self.claimed + self.unreviewed + self.completed
        )

        self.total_amount = len(self.total)
        self.correction_pending_amount = len(self.correction_pending)
        self.claimed_amount = len(self.claimed)
        self.unreviewed_amount = len(self.unreviewed)
        self.completed_amount = len(self.completed)


@dataclass
class Category:
    name: str
    pokemon: List[str]
