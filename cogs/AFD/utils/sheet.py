from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Optional, Union

import discord
import gspread_asyncio
import numpy as np
import pandas as pd
from google.oauth2 import service_account

from cogs.Draw.utils.constants import ALPHABETS

from .constants import (
    DATETIME_FMT,
    DEFAULT_CLAIM_MAX,
    COL_OFFSET,
    DEFAULT_UNAPP_MAX,
    EMAIL,
    EXPORT_SUFFIX,
    FIRST_ROW_IDX,
)
from .labels import (
    APPROVED_LABEL,
    CLAIM_MAX_LABEL,
    COMMENT_LABEL,
    DEADLINE_LABEL,
    DEX_LABEL,
    DEX_LABEL_P,
    ENGLISH_NAME_LABEL_P,
    IMAGE_LABEL,
    PKM_LABEL,
    RULES_LABEL,
    SEPARATOR_LABEL,
    UNAPP_MAX_LABEL,
    USER_ID_LABEL,
    THEME_LABEL,
    RULES_LABEL,
    DEADLINE_LABEL,
    CLAIM_MAX_LABEL,
    UNAPP_MAX_LABEL,
)
from .utils import Row
from cogs.Poketwo.utils.utils import get_pokemon
from cogs.Poketwo.utils.constants import IMAGE_URL


log = logging.getLogger("cogs.AFD.afd")


class AfdSheet:
    def __init__(
        self,
        url: str,
        *,
        pokemon_df: pd.DataFrame,
    ) -> None:
        """url must be in the format https://docs.google.com/spreadsheets/d/{ID}"""
        self.url = url
        self.export_url = f"{url}/{EXPORT_SUFFIX}"
        self.pk = pokemon_df

        self.df: pd.DataFrame
        self.gc: gspread_asyncio.AsyncioGspreadClient
        self.spreadsheet: gspread_asyncio.AsyncioGspreadSpreadsheet
        self.worksheet: gspread_asyncio.AsyncioGspreadWorksheet

    async def setup(self) -> None:
        await self.authorize()
        self.spreadsheet = await self.gc.open_by_url(self.url)
        self.worksheet = await self.spreadsheet.get_worksheet(0)
        await self.update_df()

    async def authorize(self) -> None:
        SCOPES = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]

        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GS_ACCOUNT_INFO"])
        ).with_scopes(SCOPES)

        self.gc = await gspread_asyncio.AsyncioGspreadClientManager(
            lambda: creds
        ).authorize()

    @classmethod
    async def create_new(cls, *, pokemon_df: pd.DataFrame) -> AfdSheet:
        self: AfdSheet = cls.__new__(cls)
        await self.authorize()

        sheet = await self.gc.create("AFD Sheet")
        try:
            self.spreadsheet = sheet
            self.worksheet = await self.spreadsheet.get_worksheet(0)

            url = f"https://docs.google.com/spreadsheets/d/{sheet.id}"
            await self.gc.insert_permission(
                sheet.id, None, perm_type="anyone", role="reader"
            )
            await self.gc.insert_permission(
                sheet.id, EMAIL, perm_type="user", role="writer"
            )

            data = []
            for idx, row in pokemon_df.iterrows():
                new_row = [
                    row[DEX_LABEL_P],
                    row[ENGLISH_NAME_LABEL_P],
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ]
                data.append(new_row)
            self.df = pd.DataFrame(
                data,
                columns=[
                    DEX_LABEL,
                    PKM_LABEL,
                    USER_ID_LABEL,
                    IMAGE_LABEL,
                    APPROVED_LABEL,
                    COMMENT_LABEL,
                    SEPARATOR_LABEL,
                    THEME_LABEL,
                    RULES_LABEL,
                    DEADLINE_LABEL,
                    CLAIM_MAX_LABEL,
                    UNAPP_MAX_LABEL,
                ],
            )
            deadline_str = datetime.datetime(
                year=datetime.datetime.utcnow().year + 1,
                month=3,
                day=25,
                hour=0,
                minute=0,
                second=0,
            ).strftime(DATETIME_FMT)

            self.df.loc[FIRST_ROW_IDX, THEME_LABEL] = "INSERT THEME HERE"
            self.df.loc[FIRST_ROW_IDX, RULES_LABEL] = "INSERT RULES HERE"
            self.df.loc[FIRST_ROW_IDX, DEADLINE_LABEL] = deadline_str
            self.df.loc[FIRST_ROW_IDX, CLAIM_MAX_LABEL] = DEFAULT_CLAIM_MAX
            self.df.loc[FIRST_ROW_IDX, UNAPP_MAX_LABEL] = DEFAULT_UNAPP_MAX

            await self.update_sheet()
            await self.update_df()

            self.__init__(url, pokemon_df=pokemon_df)
        except Exception as e:
            await self.gc.del_spreadsheet(sheet.id)
            log.info(
                "\033[31;1mAFD: Encountered error. Deleted created spreadsheet.\033[0m"
            )
            raise e
        else:
            return self

    @property
    def THEME(self):
        return self.df.loc[FIRST_ROW_IDX, THEME_LABEL]

    @property
    def RULES(self):
        return self.df.loc[FIRST_ROW_IDX, RULES_LABEL]

    @property
    def DEADLINE(self):
        return self.df.loc[FIRST_ROW_IDX, DEADLINE_LABEL]

    @property
    def DEADLINE_DT(self):
        return datetime.datetime.strptime(self.DEADLINE, DATETIME_FMT)

    @property
    def DEADLINE_TS(self):
        return discord.utils.format_dt(self.DEADLINE_DT, "f")

    @property
    def CLAIM_MAX(self):
        return int(self.df.loc[FIRST_ROW_IDX, CLAIM_MAX_LABEL])

    @property
    def UNAPP_MAX(self):
        return int(self.df.loc[FIRST_ROW_IDX, UNAPP_MAX_LABEL])

    async def update_row(
        self,
        dex: int,
        *,
        from_col: Optional[str] = DEX_LABEL,
        to_col: Optional[str] = COMMENT_LABEL,
    ) -> None:
        from_col_idx = self.df.columns.get_loc(from_col)
        to_col_idx = self.df.columns.get_loc(to_col) + 1
        row_vals = [self.df.iloc[dex, from_col_idx:to_col_idx].fillna("").tolist()]
        await self.worksheet.update(
            f"{ALPHABETS[from_col_idx]}{dex + COL_OFFSET}", row_vals
        )

    async def update_sheet(self) -> None:
        """Drops index column"""
        self.df = self.df.fillna("").reset_index(drop=True)
        vals = [self.df.columns.tolist()] + self.df.values.tolist()
        await self.worksheet.update("A1", vals)

    async def update_df(self):
        data = await self.worksheet.get_all_values()
        self.df = pd.DataFrame(data[1:], columns=data[0], dtype="object").replace(
            "", np.nan
        )

    def get_pokemon(self, name: str) -> str:
        return get_pokemon(name, pk=self.pk)

    def get_pokemon_loc(self, dex: int) -> str:
        return f"{self.url}/edit#gid=0&range=B{dex + COL_OFFSET}"

    def get_pokemon_dex(self, pokemon: str) -> int:
        try:
            return int(self.pk[self.pk[ENGLISH_NAME_LABEL_P] == pokemon][DEX_LABEL_P])
        except TypeError as e:
            print(pokemon)
            raise e

    def get_row(self, dex_num: str) -> Row:
        return Row(self.df.iloc[int(dex_num)])

    def get_pokemon_row(self, pokemon: str) -> Row:
        return Row(self.df.loc[self.df[PKM_LABEL] == pokemon])

    def get_pokemon_image(self, pokemon: str) -> str:
        return IMAGE_URL % self.get_pokemon_dex(pokemon)

    def edit_row_where(
        self, column: str, equals_to: str, *, set_column: str, to_val: str
    ):
        self.df.loc[self.df[column] == equals_to, set_column] = to_val

    def can_claim(self, user: discord.User) -> bool:
        if (
            len(
                self.df.loc[
                    (self.df[USER_ID_LABEL] == str(user.id))
                    & (
                        self.df.loc[self.df[USER_ID_LABEL] == str(user.id)][
                            IMAGE_LABEL
                        ].isna()
                    )
                ]
            )
            >= self.CLAIM_MAX
        ):
            return False
        return True

    def claim(self, user: Union[discord.User, discord.Member], pokemon: str) -> Row:
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=USER_ID_LABEL, to_val=str(user.id)
        )
        for col in self.df.columns[
            self.df.columns.get_loc(IMAGE_LABEL) :
        ]:  # For all columns after Discord ID
            self.edit_row_where(PKM_LABEL, pokemon, set_column=col, to_val=None)
        return self.get_pokemon_row(pokemon)

    def unclaim(self, pokemon: str) -> Row:
        for col in self.df.columns[
            self.df.columns.get_loc(USER_ID_LABEL) :
        ]:  # For all columns after Pokemon
            self.edit_row_where(PKM_LABEL, pokemon, set_column=col, to_val=None)
        return self.get_pokemon_row(pokemon)

    def submit(self, pokemon: str, *, image_url: str) -> Row:
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=IMAGE_LABEL, to_val=str(image_url)
        )
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=APPROVED_LABEL, to_val=None
        )  # Clear approved field
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=COMMENT_LABEL, to_val=None
        )  # Clear any comment
        return self.get_pokemon_row(pokemon)

    def approve(self, pokemon: str, *, by: int) -> Row:
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=APPROVED_LABEL, to_val=str(by)
        )
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=COMMENT_LABEL, to_val=None
        )  # Clear any comment
        return self.get_pokemon_row(pokemon)

    def unapprove(self, pokemon: str) -> Row:
        self.edit_row_where(PKM_LABEL, pokemon, set_column=APPROVED_LABEL, to_val=None)
        return self.get_pokemon_row(pokemon)

    def comment(
        self, pokemon: str, comment: Union[str, None], *, by: Union[int, None]
    ) -> Row:
        self.edit_row_where(
            PKM_LABEL,
            pokemon,
            set_column=COMMENT_LABEL,
            to_val=str(comment) if comment else comment,
        )
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=APPROVED_LABEL, to_val=str(by) if by else by
        )  # Set approved col to whoever commented
        return self.get_pokemon_row(pokemon)
