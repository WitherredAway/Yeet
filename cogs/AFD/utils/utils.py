from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Union
import discord
import pandas as pd
from cogs.AFD.utils.constants import PROGRESS_BAR_LENGTH
from cogs.AFD.utils.labels import (
    APPROVED_LABEL,
    COMMENT_LABEL,
    IMAGE_LABEL,
    PKM_LABEL,
    USER_ID_LABEL,
)
from cogs.Draw.utils.constants import ALPHABET_EMOJIS

from cogs.utils.utils import RoleMenu, enumerate_list, make_progress_bar

if TYPE_CHECKING:
    from cogs.AFD.afd import Afd


class EmbedColours(Enum):
    INVALID: int = 0xCB3F49  # Invalid, Red
    UNCLAIMED: int = 0x6D6F77  # Not claimed, Grey
    INCOMPLETE: int = 0xE69537  # Claimed but not complete, Orange
    UNREVIEWED: int = 0x6BAAE8  # Link present awaiting review, Blue
    CORRECTION: int = 0xF5CD6B  # Has a comment, Yellow
    APPROVED: int = 0x85AF63  # Link present and approved, Green


@dataclass
class Row:
    row: Union[pd.DataFrame, pd.Series]

    dex: Optional[int] = None
    pokemon: Optional[str] = None
    user_id: Optional[int] = None
    image: Optional[str] = None
    approved_by: Optional[int] = None
    comment: Optional[str] = None

    claimed: Optional[bool] = None
    unreviewed: Optional[bool] = None
    approved: Optional[bool] = None
    correction_pending: Optional[bool] = None

    def __post_init__(self):
        self.dex = self.row.index.values[0]
        if isinstance(self.row, pd.DataFrame):
            self.row = self.row.loc[self.dex, :]

        self.pokemon = self.row[PKM_LABEL]

        self.user_id = self.row[USER_ID_LABEL]
        self.user_id = int(self.user_id) if not pd.isna(self.user_id) else None

        self.image = self.row[IMAGE_LABEL]
        self.image = self.image if not pd.isna(self.image) else None

        self.approved_by = self.row[APPROVED_LABEL]
        self.approved_by = (
            int(self.approved_by) if not pd.isna(self.approved_by) else None
        )

        self.comment = self.row[COMMENT_LABEL]
        self.comment = self.comment if not pd.isna(self.comment) else None

        self.claimed = not pd.isna(self.user_id)
        self.unreviewed = all((self.image, not self.approved_by, not self.comment))
        self.approved = all(
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


class Categories(Enum):
    CLAIMED: str = "Claimed"
    UNCLAIMED: str = "Unclaimed"
    SUBMITTED: str = "Submitted"
    INCOMPLETE: str = "Claimed (Incomplete)"
    UNREVIEWED: str = "Submitted (Awaiting review)"
    CORRECTION: str = "Correction Pending"
    APPROVED:  str = "Approved 🎉"


@dataclass
class Category:
    category: Categories
    rows: List[Row]
    total_amount: int
    negative_pb: Optional[bool] = False

    amount: Optional[int] = None

    def __post_init__(self):
        self.name = self.category.value
        self.amount = len(self.pokemon)

    @property
    def pokemon(self) -> List[str]:
        return [row.pokemon for row in self.rows]

    @property
    def enumerated_pokemon(self) -> List[str]:
        return enumerate_list(self.pokemon)

    def progress(self, total_amount: Optional[int] = None) -> str:
        return f"{self.amount}/{total_amount if total_amount is not None else self.total_amount}"

    def progress_bar(self, total_amount: Optional[int] = None) -> str:
        return make_progress_bar(self.amount, total_amount if total_amount is not None else self.total_amount, negative=self.negative_pb, length=PROGRESS_BAR_LENGTH)


@dataclass
class Stats:
    df: pd.DataFrame
    afdcog: Afd

    def __post_init__(self):
        self.total_amount = len(self.df)

        unclaimed_rows = []
        incomplete_rows = []
        correction_pending_rows = []
        unreviewed_rows = []
        approved_rows = []
        for idx in self.df.index:
            row = self.afdcog.sheet.get_row(idx)

            if row.claimed:
                if row.approved:
                    approved_rows.append(row)
                elif row.unreviewed:
                    unreviewed_rows.append(row)
                elif row.correction_pending:
                    correction_pending_rows.append(row)
                else:
                    incomplete_rows.append(row)
            else:
                unclaimed_rows.append(row)

        claimed_list = (correction_pending_rows + incomplete_rows + unreviewed_rows + approved_rows)
        self.claimed = Category(Categories.CLAIMED, claimed_list, total_amount=self.afdcog.total_amount)
        self.unclaimed = Category(Categories.UNCLAIMED, unclaimed_rows, total_amount=self.afdcog.total_amount, negative_pb=True)

        self.incomplete = Category(Categories.INCOMPLETE, incomplete_rows, total_amount=self.claimed.amount, negative_pb=True)
        submitted_list = (correction_pending_rows + unreviewed_rows)
        self.submitted = Category(Categories.SUBMITTED, submitted_list, total_amount=self.claimed.amount)
        self.correction_pending = Category(Categories.CORRECTION, correction_pending_rows, total_amount=self.submitted.amount, negative_pb=True)
        self.unreviewed = Category(Categories.UNREVIEWED, unreviewed_rows, total_amount=self.submitted.amount, negative_pb=True)
        self.approved = Category(Categories.APPROVED, approved_rows, total_amount=self.total_amount)


