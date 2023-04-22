from __future__ import annotations

import datetime
import io
import json
import logging
import os
import re
import time
import typing
from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from typing import Callable, Dict, List, Optional, Tuple, Union

import aiohttp
import discord
import gists
import gspread_asyncio
import numpy as np
import pandas as pd
from discord.ext import commands, tasks
from google.oauth2 import service_account
from pandas.core.groupby.generic import GroupBy

from cogs.Draw.constants import PADDING
from cogs.Poketwo.utils import get_pokemon
from helpers.constants import INDENT, LOG_BORDER, NL
from helpers.context import CustomContext

from ..utils.utils import RoleMenu, UrlView, make_progress_bar
from .utils.afd_view import AfdView
from .utils.constants import (
    AFD_ADMIN_ROLE_ID,
    AFD_ROLE_ID,
    APPROVED_TXT,
    CLAIM_LIMIT,
    COL_OFFSET,
    DEL_ATTRS_TO_UPDATE,
    EMAIL,
    EXPORT_SUFFIX,
    HEADERS_FMT,
    TOP_N,
    UPDATE_CHANNEL_ID,
)
from .utils.filenames import (
    CONTENTS_FILENAME,
    CREDITS_FILENAME,
    ML_FILENAME,
    PARTICIPANTS_FILENAME,
    SERVICE_ACCOUNT_FILE,
    TOP_PARTICIPANTS_FILENAME,
    UNC_FILENAME,
    UNR_FILENAME,
)
from .utils.labels import (
    APPROVED_LABEL,
    CLAIM_MAX_LABEL,
    CMT_LABEL,
    DEADLINE_LABEL,
    DEX_LABEL,
    DEX_LABEL_P,
    ENGLISH_NAME_LABEL_P,
    IMGUR_LABEL,
    PKM_LABEL,
    RULES_LABEL,
    TOPIC_LABEL,
    UNAPP_MAX_LABEL,
    USER_ID_LABEL,
    USERNAME_LABEL,
)
from .utils.urls import AFD_CREDITS_GIST_URL, AFD_GIST_URL, IMAGE_URL, SHEET_URL
from .utils.imgur import Imgur

if typing.TYPE_CHECKING:
    from main import Bot


LOG_CHANNEL_ID = 1098442880202313779


IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
IMGUR_CLIENT_SECRET = os.getenv("IMGUR_CLIENT_SECRET")


log = logging.getLogger(__name__)


class EmbedColours(Enum):
    INVALID: int = 0xCB3F49  # Invalid, Red
    UNCLAIMED: int = 0x6D6F77  # Not claimed, Grey
    CLAIMED: int = 0xE69537  # Claimed but not complete, Orange
    UNREVIEWED: int = 0x6BAAE8  # Link present awaiting review, Blue
    COMMENT: int = 0xF5CD6B  # Has a comment, Yellow
    APPROVED: int = 0x85AF63  # Link present and approved, Green


@dataclass
class Row:
    row: Union[pd.DataFrame, pd.Series]

    dex: Optional[int] = None
    pokemon: Optional[str] = None
    username: Optional[discord.User] = None
    user_id: Optional[int] = None
    imgur: Optional[str] = None
    approved_by: Optional[int] = None
    comment: Optional[str] = None

    claimed: Optional[bool] = None
    unreviewed: Optional[bool] = None

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
        self.user_id = self.user_id if not pd.isna(self.user_id) else None

        self.imgur = self.row[IMGUR_LABEL]
        self.imgur = self.imgur if not pd.isna(self.imgur) else None

        self.approved_by = self.row[APPROVED_LABEL]
        self.approved_by = self.approved_by if not pd.isna(self.approved_by) else None

        self.comment = self.row[CMT_LABEL]
        self.comment = self.comment if not pd.isna(self.comment) else None

        self.claimed = not pd.isna(self.user_id)
        self.unreviewed = all(
            (not pd.isna(self.imgur), not self.approved_by, not self.comment)
        )

    @property
    def colour(self) -> int:
        if self.claimed:
            if self.approved_by:
                return EmbedColours.APPROVED.value
            elif self.comment:
                return EmbedColours.COMMENT.value
            elif self.unreviewed:
                return EmbedColours.UNREVIEWED.value
            else:
                return EmbedColours.CLAIMED.value
        else:
            return EmbedColours.UNCLAIMED.value


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

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE
        ).with_scopes(SCOPES)

        self.gc = await gspread_asyncio.AsyncioGspreadClientManager(
            lambda: creds
        ).authorize()

    def get_pokemon(self, name: str) -> str:
        return get_pokemon(name, pk=self.pk)

    def get_pokemon_dex(self, pokemon: str) -> int:
        try:
            return int(self.pk[self.pk[ENGLISH_NAME_LABEL_P] == pokemon][DEX_LABEL_P])
        except TypeError as e:
            print(pokemon)
            raise e

    def get_row(self, dex_num: str) -> Row:
        return Row(self.df.iloc[int(dex_num) - COL_OFFSET])

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
                            IMGUR_LABEL
                        ].isna()
                    )
                ]
            )
            >= CLAIM_LIMIT
        ):
            return False
        return True

    def claim(self, user: Union[discord.User, discord.Member], pokemon: str):
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=USERNAME_LABEL, to_val=str(user)
        )
        self.edit_row_where(
            PKM_LABEL, pokemon, set_column=USER_ID_LABEL, to_val=str(user.id)
        )
        for col in self.df.columns[3:]:  # For all columns after Discord ID
            self.edit_row_where(PKM_LABEL, pokemon, set_column=col, to_val=None)

    def unclaim(self, pokemon: str):
        for col in self.df.columns[1:]:  # For all columns after Pokemon
            self.edit_row_where(PKM_LABEL, pokemon, set_column=col, to_val=None)

    async def update_row(
        self, dex: str, *, from_col: Optional[str] = "B", to_col: Optional[str] = "H"
    ) -> None:
        ABC = "ABCDEFGHIJKLMNOP"
        row_vals = [
            self.df.iloc[
                int(dex) - COL_OFFSET, ABC.index(from_col) - 1 : ABC.index(to_col) - 1
            ]
            .fillna("")
            .tolist()
        ]
        await self.worksheet.update(f"{from_col}{int(dex) + COL_OFFSET}", row_vals)

    async def update_sheet(self) -> None:
        self.df = self.df.fillna("").reset_index()
        vals = [self.df.columns.tolist()] + self.df.values.tolist()
        await self.worksheet.update("A1", vals)

    async def update_df(self):
        data = await self.worksheet.get_all_values()
        self.df = (
            pd.DataFrame(data[1:], columns=data[0], dtype="object")
            .set_index("Dex")
            .replace("", np.nan)
        )

    @property
    def TOPIC(self):
        return self.df.loc["1", TOPIC_LABEL]

    @property
    def RULES(self):
        return self.df.loc["1", RULES_LABEL]

    @property
    def DEADLINE(self):
        return self.df.loc["1", DEADLINE_LABEL]

    @property
    def DEADLINE_TS(self):
        return discord.utils.format_dt(
            datetime.datetime.strptime(self.DEADLINE, "%d/%m/%Y %H:%M"), "f"
        )

    @property
    def CLAIM_MAX(self):
        return int(self.df.loc["1", CLAIM_MAX_LABEL])

    @property
    def UNAPP_MAX(self):
        return int(self.df.loc["1", UNAPP_MAX_LABEL])

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

            self.df = pd.DataFrame(
                columns=[
                    DEX_LABEL,
                    PKM_LABEL,
                    USERNAME_LABEL,
                    USER_ID_LABEL,
                    IMGUR_LABEL,
                    APPROVED_LABEL,
                    CMT_LABEL,
                ]
            )
            for idx, row in pokemon_df.iterrows():
                new_row = [
                    row[DEX_LABEL_P],
                    row[ENGLISH_NAME_LABEL_P],
                    None,
                    None,
                    None,
                    None,
                    None,
                ]
                self.df.loc[len(self.df.index)] = new_row

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


COMPLETED_EMOJI = "✅"
UNREVIEWED_EMOJI = "☑️"
REVIEW_EMOJI = "❗"


@dataclass
class Claimed:
    claimed_df: pd.DataFrame
    sheet: AfdSheet

    def __post_init__(self):
        self.review = []
        self.claimed = []
        self.unreviewed = []
        self.completed = []
        for idx, row in self.claimed_df.iterrows():
            row = self.sheet.get_row(idx)
            pkm = row.pokemon
            if row.approved_by:
                self.completed.append(f"{pkm} {COMPLETED_EMOJI}")
            elif row.unreviewed:
                self.unreviewed.append(f"{pkm} {UNREVIEWED_EMOJI}")
            elif row.comment:
                self.review.append(f"{pkm} {REVIEW_EMOJI}")
            else:
                self.claimed.append(f"{pkm}")
        self.total_list = self.review + self.claimed + self.unreviewed + self.completed
        self.total_list = [
            f"{idx + 1}. {pkm}" for idx, pkm in enumerate(self.total_list)
        ]

        self.total_amount = len(self.total_list)
        self.review_amount = len(self.review)
        self.claimed_amount = len(self.claimed)
        self.unreviewed_amount = len(self.unreviewed)
        self.completed_amount = len(self.completed)


class AFDRoleMenu(RoleMenu):
    def __init__(self):
        roles_dict = {
            "AFD": discord.ButtonStyle.green,
            "AFD Admin": discord.ButtonStyle.red,
        }
        super().__init__(roles_dict)


class PokemonView(discord.ui.View):
    def __init__(self, ctx: CustomContext, row: Row, *, afdcog: Afd, user: Optional[discord.User] = None):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.row = row
        self.pokemon = self.row.pokemon
        self.afdcog = afdcog
        self.sheet = self.afdcog.sheet
        self.user = user

        self.msg: discord.Message

    async def on_timeout(self):
        self.clear_items()
        await self.msg.edit(embed=self.embed, view=self)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"You can't use this!",
                ephemeral=True,
            )
            return False
        return True

    @property
    def embed(self) -> Bot.Embed:
        ctx = self.ctx
        row = self.row
        pokemon = self.pokemon
        base_image = self.sheet.get_pokemon_image(pokemon)

        embed = ctx.bot.Embed(title=f"#{row.dex} - {pokemon}", colour=row.colour)
        embed.set_thumbnail(url=base_image)
        self.update_buttons(embed)
        return embed

    def update_buttons(self, embed: Bot.Embed):
        row = self.row
        self.clear_items()
        if row.claimed:
            self.add_item(self.unclaim_btn)
            if row.imgur:
                embed.set_image(url=row.imgur)

            if row.approved_by:
                status = "Complete and approved."
            elif row.comment:
                status = "Correction pending."
                embed.add_field(name=CMT_LABEL, value=str(row.comment), inline=False)
            elif row.unreviewed:
                status = "Submitted, Awaiting review."
            else:
                status = "Claimed by"

            embed.set_footer(
                text=f"{status}\n{row.username} ({row.user_id})",
                icon_url=self.user.avatar.url,
            )
        else:
            status = "Not claimed"
            embed.set_footer(text=status)
            self.add_item(self.claim_btn)

    async def update_msg(self):
        await self.sheet.update_df()
        self.row = self.sheet.get_pokemon_row(self.pokemon)
        self.user = (await self.afdcog.fetch_user(int(self.row.user_id))) if self.row.claimed else None
        await self.msg.edit(embed=self.embed, view=self)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple)
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.afdcog.claim(self.ctx, self.pokemon)
        await self.update_msg()

    @discord.ui.button(label="Unclaim", style=discord.ButtonStyle.red)
    async def unclaim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.afdcog.unclaim(self.ctx, self.pokemon)
        await self.update_msg()

class Afd(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.hidden = True

        self.bot.user_cache: dict = {}
        self.user_cache = self.bot.user_cache

        self.sheet: AfdSheet

    display_emoji = "🗓️"

    async def cog_load(self):
        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("WgithubTOKEN"))

        self.log_channel = await self.bot.fetch_channel(LOG_CHANNEL_ID)
        self.update_channel = await self.bot.fetch_channel(UPDATE_CHANNEL_ID)
        self.afd_gist = await self.gists_client.get_gist(AFD_GIST_URL)
        self.credits_gist = await self.gists_client.get_gist(AFD_CREDITS_GIST_URL)

        start = time.time()
        await self.sheet.setup()
        log.info(f"AFD: Fetched spreadsheet in {round(time.time()-start, 2)}s")

        self.imgur = Imgur(IMGUR_CLIENT_ID, session=self.bot.session)

        self.update_pokemon.start()

    async def cog_unload(self):
        if self.update_pokemon.is_running():
            self.update_pokemon.cancel()

    @property
    def pk(self) -> pd.DataFrame:
        return self.bot.pk

    @property
    def df(self) -> pd.DataFrame:
        return self.sheet.df

    @property
    def total_amount(self) -> int:
        return len(self.df)

    @cached_property
    def sheet(self) -> AfdSheet:
        return AfdSheet(SHEET_URL, pokemon_df=self.pk)

    def is_admin(self, user: discord.Member) -> bool:
        return AFD_ADMIN_ROLE_ID in [r.id for r in user.roles]

    def confirmation_embed(
        self,
        msg: str,
        *,
        pokemon: Optional[str] = None,
        colour: Optional[EmbedColours] = None,
        footer: Optional[str] = None,
    ) -> Bot.Embed:
        embed = self.bot.Embed(
            description=msg, colour=colour.value if colour else colour
        )
        if pokemon is not None:
            pokemon_image = self.sheet.get_pokemon_image(pokemon)
            embed.set_thumbnail(url=pokemon_image)
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def get_pokemon(self, ctx: CustomContext, name: str) -> Union[str, None]:
        try:
            name = self.sheet.get_pokemon(name)
        except IndexError:
            await ctx.reply(
                embed=self.confirmation_embed(
                    "Invalid pokemon provided!", colour=EmbedColours.INVALID
                )
            )
            return None
        return name

    @commands.check_any(commands.is_owner(), commands.has_role(AFD_ROLE_ID))
    @commands.group(
        name="afd",
        brief="Afd commands",
        description="Command with a variety of afd event subcommands! If invoked alone, it will show event stats.",
    )
    async def afd(self, ctx: CustomContext):
        await ctx.typing()
        await self.sheet.update_df()
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.info)

    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="forceclaim",
        aliases=("fc",),
        brief="Forcefully claim a pokemon in someone's behalf.",
        description="AFD Admin-only command to forcefully claim a pokemon in someone's behalf.",
        help=f"""When this command is ran, first the sheet data will be fetched. Then:
1. A pokemon, with the normalized and deaccented version of the provided name *including alt names*, will be searched for. If not found, it will return invalid.
2. That pokemon's availability on the sheet will be checked:
{INDENT}**i. If it's *not* claimed yet:**
{INDENT}{INDENT}- If the user already has max claims ({CLAIM_LIMIT}), it will still give you the option to proceed.
{INDENT}{INDENT}- Otherwise, you will be prompted to confirm that you want to forceclaim the pokemon for the user.
{INDENT}**ii. If it's already claimed by *the same user*, you will be informed of such.**
{INDENT}**iii. If it's already claimed by *another user*, you will be prompted to confirm if you want to override. Will warn you \
    if there is a drawing submitted already.**
3. The sheet will finally be updated with the user's Username and ID""",
    )
    async def forceclaim(
        self, ctx: CustomContext, user: Optional[discord.User] = None, *, pokemon: str
    ):
        if user is None:
            user = ctx.author
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        row = self.sheet.get_pokemon_row(pokemon)
        if not row.claimed:
            content = None
            if self.sheet.can_claim(user) is False:
                content = f"**{user}** already has the max number ({CLAIM_LIMIT}) of pokemon claimed, still continue?"

            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    content
                    or f"Are you sure you want to forceclaim **{pokemon}** for **{user}**?",
                    pokemon=pokemon,
                ),
                confirm_label="Force Claim",
            )
            if conf is False:
                return
        elif row.user_id == str(user.id):
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is already claimed by **{user}**!",
                    pokemon=pokemon,
                    colour=EmbedColours.INVALID,
                )
            )
        else:
            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is already claimed by **{row.username}**, override and claim it for **{user}**?\
                        {' There is a drawing submitted already which will be removed.' if row.imgur else ''}",
                    pokemon=pokemon,
                ),
                confirm_label="Force Claim",
            )
            if conf is False:
                return

        self.sheet.claim(user, pokemon)
        await self.sheet.update_row(row.dex)
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"You have successfully force claimed **{pokemon}** for **{user}**.",
                pokemon=pokemon,
                colour=EmbedColours.CLAIMED,
            )
        )
        await self.log_channel.send(
            embed=self.confirmation_embed(
                f"**{pokemon}** has been forcefully claimed for **{user}**.",
                pokemon=pokemon,
                colour=EmbedColours.CLAIMED,
            ),
            view=UrlView({"Go to message": cmsg.jump_url}),
        )

    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="forceunclaim",
        aliases=("ufc",),
        brief="Forcefully unclaim a pokemon",
        description="AFD Admin-only command to forcefully unclaim a pokemon",
        help=f"""When this command is ran, first the sheet data will be fetched. Then:
1. A pokemon, with the normalized and deaccented version of the provided name *including alt names*, will be searched for. If not found, it will return invalid.
2. That pokemon's availability on the sheet will be checked:
{INDENT}**i. If it is claimed:**
{INDENT}{INDENT}- You will be prompted to confirm that you want to force unclaim the pokemon.\
    Will warn you if there is a drawing submitted already.
{INDENT}{INDENT}- The sheet will finally be updated and remove the user's Username and ID
{INDENT}**ii. If it's *not* claimed, you will be informed of such.**""",
    )
    async def forceunclaim(self, ctx, *, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        row = self.sheet.get_pokemon_row(pokemon)
        if not row.claimed:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not claimed.",
                    pokemon=pokemon,
                    colour=EmbedColours.INVALID,
                )
            )
        conf, cmsg = await ctx.confirm(
            embed=self.confirmation_embed(
                f"**{pokemon}** is currently claimed by **{row.username}**, forcefully unclaim?\
                        {' There is a drawing already submitted which will be removed.' if row.imgur else ''}",
                pokemon=pokemon,
            ),
            confirm_label="Force Unclaim",
        )
        if conf is False:
            return

        self.sheet.unclaim(
            pokemon,
        )
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"You have successfully force unclaimed **{pokemon}** from **{row.username}**.",
                pokemon=pokemon,
                colour=EmbedColours.UNCLAIMED,
            )
        )
        await self.log_channel.send(
            embed=self.confirmation_embed(
                f"**{pokemon}** has been forcefully unclaimed from **{row.username}**.",
                pokemon=pokemon,
                colour=EmbedColours.UNCLAIMED,
            ),
            view=UrlView({"Go to message": cmsg.jump_url}),
        )

    @commands.is_owner()
    @afd.command(
        name="new_spreadsheet",
        brief="Used to create a brand new spreadsheet.",
        description="Sets up a new spreadsheet to use. Intended to be used only once.",
    )
    async def new(self, ctx: CustomContext):
        if hasattr(self, "sheet"):
            return await ctx.reply("A spreadsheet already exists.")

        async with ctx.typing():
            self.sheet: AfdSheet = await AfdSheet.create_new(pokemon_df=self.pk)

        embed = self.bot.Embed(
            title="New Spreadsheet created",
            description=f"[Please set it permanently in the code.]({self.sheet.url})",
        )
        await ctx.reply(
            embed=embed, view=UrlView({"Go To Spreadsheet": self.sheet.url})
        )

    @commands.is_owner()
    @afd.command(
        name="forceupdate",
        brief="Forcefully update AFD gists.",
        description="Used to forcefully update the AFD gist and Credits gist",
    )
    async def forceupdate(self, ctx: CustomContext):
        for attr in DEL_ATTRS_TO_UPDATE:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

        await ctx.message.add_reaction("▶️")
        self.update_pokemon.restart()
        await ctx.message.add_reaction("✅")

    @commands.is_owner()
    @afd.command(name="rolemenu")
    async def rolemenu(self, ctx: CustomContext):
        role_menu = AFDRoleMenu()
        await ctx.send(
            f"""<@&{AFD_ROLE_ID}>: Role required to access `afd` commands
<@&{AFD_ADMIN_ROLE_ID}>: Role required to access AFD Admin only `afd` commands.""",
            view=role_menu,
            allowed_mentions=discord.AllowedMentions(roles=False),
        )

    @property
    def embed(self) -> Bot.Embed:
        unc_list, unc_amount = self.validate_unclaimed()
        claimed_amount = self.total_amount - unc_amount

        unr_list, unr_amount = self.validate_unreviewed()

        ml_list, ml_list_mention, ml_amount = self.validate_missing_link()
        submitted_amount = claimed_amount - ml_amount
        completed_amount = submitted_amount - unr_amount

        description = f"""**Topic:** {self.sheet.TOPIC}

**Deadline**: {self.sheet.DEADLINE_TS}
**Max claimed (unfinished) pokemon**: {self.sheet.CLAIM_MAX}
**Max unapproved pokemon**: {self.sheet.UNAPP_MAX}
"""
        embed = self.bot.Embed(
            title="Welcome to the April Fools community project!",
            description=description,
        )
        embed.add_field(
            name="Rules",
            value=self.sheet.RULES.format(
                CLAIM_MAX=self.sheet.CLAIM_MAX, UNAPP_MAX=self.sheet.UNAPP_MAX
            ),
            inline=False,
        )

        embed.add_field(
            name="Community Stats",
            value=f"""**Completed**
{make_progress_bar(completed_amount, self.total_amount)} {completed_amount}/{self.total_amount}
**Submitted**
{make_progress_bar(submitted_amount, self.total_amount)} {submitted_amount}/{self.total_amount}
**Claimed**
{make_progress_bar(claimed_amount, self.total_amount)} {claimed_amount}/{self.total_amount}""",
            inline=False,
        )
        return embed

    @afd.command(
        name="info",
        aliases=("information", "progress"),
        brief="View progress of the april fool's event.",
        help="""If `pokemon` arg is passed and `user` is not, it will show info of that pokemon.
If `user` arg is passed, it will show stats of that user. Otherwise it will show your stats. If `user` is a non-participant, it will not show their stats.""",
        description="Shows user and community stats.",
    )
    async def info(
        self,
        ctx: CustomContext,
        user: Optional[discord.User] = None,
        *,
        pokemon: Optional[str] = None,
    ):
        if pokemon and (user is None):
            return await ctx.invoke(self.view, pokemon=pokemon)
        if user is None:
            user = ctx.author

        view = AfdView(self, ctx=ctx)
        view.msg = await ctx.reply(embed=self.embed, view=view)

    @afd.command(
        name="view",
        aliases=("pokemon", "pkm", "d", "dex"),
        brief="See info of a pokemon from the sheet",
    )
    async def view(self, ctx: CustomContext, *, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        row = self.sheet.get_pokemon_row(pokemon)
        user = (await self.fetch_user(int(row.user_id))) if row.claimed else None

        view = PokemonView(ctx, row, afdcog=self, user=user)
        view.msg = await ctx.send(embed=view.embed, view=view)

    async def claim(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        row = self.sheet.get_pokemon_row(pokemon)
        if not row.claimed:
            if self.sheet.can_claim(ctx.author) is False and not self.is_admin(
                ctx.author
            ):
                return await ctx.reply(
                    embed=self.confirmation_embed(
                        f"You already have the max number ({CLAIM_LIMIT}) of pokemon claimed!",
                        colour=EmbedColours.INVALID,
                    )
                )

            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    f"Are you sure you want to claim **{pokemon}**?", pokemon=pokemon
                ),
            )
            if conf is False:
                return

        decide_msg = (
            lambda row: f"**{pokemon}** is already claimed by **{'you' if row.user_id == str(ctx.author.id) else row.username}**!"
        )
        check = lambda row: row.claimed
        decide_footer = (
            lambda row: "You can unclaim it using the `unclaim` command."
            if row.user_id == str(ctx.author.id)
            else None
        )
        claimed = await self.check_claim(
            ctx,
            decide_msg,
            pokemon,
            check=check,
            row=row if conf is None else None,
            decide_footer=decide_footer,
            cmsg=cmsg,
        )
        if claimed is True:
            return

        self.sheet.claim(ctx.author, pokemon)
        await self.sheet.update_row(row.dex)
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"You have successfully claimed **{pokemon}**, have fun! :D",
                pokemon=pokemon,
                colour=EmbedColours.CLAIMED,
                footer=f"You can undo this using the `unclaim` command.",
            )
        )
        await self.log_channel.send(
            embed=self.confirmation_embed(
                f"**{ctx.author}** has claimed **{pokemon}**.",
                pokemon=pokemon,
                colour=EmbedColours.CLAIMED,
            ),
            view=UrlView({"Go to message": cmsg.jump_url}),
        )

    @afd.command(
        name="claim",
        brief="Claim a pokemon to draw",
        description=f"Claim a pokemon to draw. Can have upto {CLAIM_LIMIT} claimed pokemon at a time. Pokemon alt names are supported!",
        help=f"""When this command is ran, first the sheet data will be fetched. Then:
1. A pokemon, with the normalized and deaccented version of the provided name *including alt names*, will be searched for. If not found, it will return invalid.
2. That pokemon's availability on the sheet will be checked:
{INDENT}**i. If it's *not* claimed yet:**
{INDENT}{INDENT}- If you already have max claims ({CLAIM_LIMIT}), it will not let you claim. Does not apply to admins.
{INDENT}{INDENT}- Otherwise, you will be prompted to confirm that you want to claim the pokemon.
{INDENT}{INDENT}- The sheet data will be fetched again to check for any changes since.
{INDENT}{INDENT}{INDENT}- If the pokemon has since been claimed, you will be informed of such.
{INDENT}{INDENT}- The sheet will finally be updated with your Username and ID
{INDENT}**ii. If it's already claimed by *you* or *someone else*, you will be informed of such.**""",
    )
    async def claim_cmd(self, ctx: CustomContext, *, pokemon: str):
        await self.claim(ctx, pokemon)

    async def unclaim(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        row = self.sheet.get_pokemon_row(pokemon)
        if row.user_id == str(ctx.author.id):
            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    f"Are you sure you want to unclaim **{pokemon}**?\
                        {' You have already submitted a drawing which will be removed.' if row.imgur else ''}",
                    pokemon=pokemon,
                ),
                confirm_label="Unclaim",
            )
            if conf is False:
                return

        check = lambda row: (not row.claimed) or row.user_id != str(ctx.author.id)
        decide_msg = (
            lambda row: f"**{pokemon}** is not claimed."
            if not row.claimed
            else f"**{pokemon}** is claimed by **{row.username}**!"
        )
        decide_footer = (
            lambda row: None
            if not row.claimed
            else (
                "You can force unclaim it using the `forceunclaim` command."
                if self.is_admin(ctx.author)
                else None
            )
        )
        not_claimed = await self.check_claim(
            ctx,
            decide_msg,
            pokemon,
            check=check,
            row=row if conf is None else None,
            decide_footer=decide_footer,
            cmsg=cmsg,
        )
        if not_claimed is True:
            return

        self.sheet.unclaim(pokemon)
        await self.sheet.update_row(row.dex)
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"You have successfully unclaimed **{pokemon}**.",
                pokemon=pokemon,
                colour=EmbedColours.UNCLAIMED,
            )
        )
        await self.log_channel.send(
            embed=self.confirmation_embed(
                f"**{ctx.author}** has unclaimed **{pokemon}**.",
                pokemon=pokemon,
                colour=EmbedColours.UNCLAIMED,
            ),
            view=UrlView({"Go to message": cmsg.jump_url}),
        )

    @afd.command(
        name="unclaim",
        brief="Unclaim a pokemon",
        description=f"Unclaim a pokemon claimed by you.",
        help=f"""When this command is ran, first the sheet data will be fetched. Then:
1. A pokemon, with the normalized and deaccented version of the provided name *including alt names*, will be searched for. If not found, it will return invalid.
2. That pokemon's availability on the sheet will be checked:
{INDENT}**i. If it is claimed by *you*:**
{INDENT}{INDENT}- You will be prompted to confirm that you want to unclaim the pokemon.\
    Will warn you if you have already submitted a drawing.
{INDENT}{INDENT}- The sheet will finally be updated and remove your Username and ID
{INDENT}**ii. If it's *not* claimed, you will be informed of such.**
{INDENT}**iii. If it's claimed by *someone else*, you will be informed of such.**""",
    )
    async def unclaim_cmd(self, ctx: CustomContext, *, pokemon: str):
        await self.unclaim(ctx, pokemon)

    async def check_claim(
        self,
        ctx: CustomContext,
        decide_msg: Callable[[Row], str],
        pokemon: str,
        *,
        check: Callable[[Row], bool],
        row: Optional[Row] = None,
        decide_footer: Optional[Callable[[Row], str]] = None,
        cmsg: Optional[bool] = None,
    ) -> bool:
        if not row:
            # Check once again for any changes to the sheet
            await self.sheet.update_df()
            row = self.sheet.get_pokemon_row(pokemon)

        if check(row):
            embed = self.confirmation_embed(
                decide_msg(row),
                pokemon=pokemon,
                colour=EmbedColours.INVALID,
                footer=decide_footer(row) if decide_footer else decide_footer,
            )
            if cmsg:
                await cmsg.edit(embed=embed)
            else:
                await ctx.reply(embed=embed)
            return True
        return False

    # The task that updates the unclaimed pokemon gist
    @tasks.loop(minutes=5)
    async def update_pokemon(self):
        og_start = time.time()
        log.info(NL + LOG_BORDER + NL + f"AFD: Task started")

        await self.sheet.update_df()

        date = (datetime.datetime.utcnow()).strftime("%I:%M%p, %d/%m/%Y")
        updated = []

        self.unc = True
        unc_list, unc_amount = self.validate_unclaimed()
        self.unr = True
        unr_list, unr_amount = self.validate_unreviewed()
        self.ml = True
        ml_list, ml_list_mention, ml_amount = self.validate_missing_link()

        files = []
        if self.unc:
            updated.append(f"`Unclaimed pokemon` **({unc_amount})**")
            unc_content = f'# Unclaimed Pokemon\nCount: {unc_amount}/{self.total_amount}\n## Pokemon: \n<details>\n<summary>Click to expand</summary>\n\n{NL.join(unc_list) if unc_list else "None"}\n\n</details>'
            files.append(gists.File(name=UNC_FILENAME, content=unc_content))

        if self.unr:
            updated.append(f"`Unreviewed pokemon` **({unr_amount})**")
            unr_content = f'# Unreviewed Pokemon\nCount: {unr_amount}\n## Users: \n{NL.join(unr_list) if unr_list else "None"}'
            files.append(gists.File(name=UNR_FILENAME, content=unr_content))

        if self.ml:
            updated.append(f"`Incomplete pokemon` **({ml_amount})**")
            ml_content = f'# Incomplete Pokemon\nCount: {ml_amount}\n## Users: \n<details>\n<summary>Click to expand</summary>\n\n{NL.join(ml_list) if ml_list else "None"}\n\n</details>\n\n## Copy & paste to ping:\n<details>\n<summary>Click to expand</summary>\n\n```\n{NL.join(ml_list_mention) if ml_list else "None"}\n```\n\n</details>'
            files.append(gists.File(name=ML_FILENAME, content=ml_content))

        contents = f"""# Contents
- [{ML_FILENAME}](#file-incomplete-pokemon-md)
- [{UNC_FILENAME}](#file-unclaimed-pokemon-md)
- [{UNR_FILENAME}](#file-unreviewed-pokemon-md)"""
        files.append(gists.File(name=CONTENTS_FILENAME, content=contents))

        if not (self.unc or self.unr or self.ml):
            log.info(
                f"AFD: Task returned in {round(time.time()-og_start, 2)}s"
                + NL
                + LOG_BORDER
            )
            return

        description = f"{self.ml_amount} claimed pokemon with missing links, {self.unc_amount} unclaimed pokemon and {self.unr_amount} unreviewed pokemon - As of {date} GMT (Checks every 5 minutes, and updates only if there is a change)"
        await self.afd_gist.edit(
            files=files,
            description=description,
        )

        try:
            await self.update_credits()
        except Exception as e:
            await self.update_channel.send(e)
            raise e

        update_msg = f"""Updated {" and ".join(updated)}!
(<{self.afd_gist.url}>)

Credits: <{self.credits_gist.url}>"""
        await self.update_channel.send(update_msg)
        log.info(
            f"AFD: Task completed in {round(time.time()-og_start, 2)}s"
            + NL
            + LOG_BORDER
        )

    @update_pokemon.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

    @property
    def user_grouped(self) -> GroupBy:
        return self.df.groupby(USERNAME_LABEL)

    async def fetch_user(self, user_id: int) -> discord.User:
        user_id = int(user_id)
        if (user := self.user_cache.get(user_id)) is not None:
            return user

        if (user := self.bot.get_user(user_id)) is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except Exception as e:
                await self.update_channel.send(user_id)
                raise e

        self.user_cache[user_id] = user
        return user

    def validate_claimed(self, user: discord.User) -> Claimed:
        try:
            c_df: pd.DataFrame = self.user_grouped.get_group(str(user))
        except KeyError:
            return False
        return Claimed(c_df, self.sheet)

    def validate_unclaimed(self) -> Tuple[List[str], int]:
        unc_df = self.df[self.df[USERNAME_LABEL].isna()].sort_values(by=DEX_LABEL)
        unc_list = []
        for idx, row in unc_df.iterrows():
            pkm = row[PKM_LABEL]
            unc_list.append(f"1. {pkm}")

        unc_amount = len(unc_list)
        if hasattr(self, "unc_amount"):
            if self.unc_amount == unc_amount:
                self.unc = False
        self.unc_amount = unc_amount

        return unc_list, unc_amount

    def format_unreviewed(self, df: pd.DataFrame, row: Row, pkm_indexes: list) -> str:
        pkm_list = []
        for idx, pkm_idx in enumerate(pkm_indexes):
            pokename = df.loc[pkm_idx, PKM_LABEL]
            comment = (
                df.loc[pkm_idx, CMT_LABEL]
                if str(df.loc[pkm_idx, CMT_LABEL]) != "nan"
                else None
            )
            link = df.loc[pkm_idx, IMGUR_LABEL]
            location = f"{SHEET_URL[:-24]}/edit#gid=0&range=E{pkm_idx}"

            comment_text = f""" (Marked for review)
        - Comment: {comment}
            """
            text = f"""
1. `{pokename}` {comment_text if comment else ""}"""
            # - [Sheet location]({location})
            # - [Imgur]({link})"""
            pkm_list.append(text)
        format_list = "\n".join(pkm_list)
        return_text = f"""<details>
<summary>{row.username} ({row.user_id}) - {len(pkm_list)}</summary>
{format_list}
</details>"""
        return return_text

    def get_unreviewed(self, df, df_grouped) -> List[str]:
        df_list = []
        for username, pkm_indexes in df_grouped.groups.items():
            row_0 = self.sheet.get_row(pkm_indexes[0])
            if pd.isna(username):
                continue
            msg = self.format_unreviewed(df, row_0, pkm_indexes)

            df_list.append(msg)

        return df_list

    def validate_unreviewed(self) -> Tuple[List[str], int]:
        df = self.df.loc[
            (~self.df[USER_ID_LABEL].isna())
            & (~self.df[IMGUR_LABEL].isna())
            & (self.df[APPROVED_LABEL].isna())
        ]

        df_grouped = df.groupby(USERNAME_LABEL)

        unr_amount = len(
            [pkm_id for pkm_idx in df_grouped.groups.values() for pkm_id in pkm_idx]
        )

        if hasattr(self, "unr_amount"):
            if self.unr_amount == unr_amount:
                self.unr = False
        unr_list = self.get_unreviewed(df, df_grouped)
        self.unr_amount = unr_amount

        return unr_list, unr_amount

    def get_missing_link(self, df_grouped) -> Tuple[List[str], List[str]]:
        ml_list = []
        mention_list = []
        for _id, pkms in df_grouped.groups.items():
            pkm_list = []
            for pkm in pkms:
                row = self.sheet.get_row(pkm)
                if not row.claimed and not row.imgur:
                    continue
                pkm_list.append(f"`{row.pokemon}`")
            msg = f'- **{row.username}** [{len(pkm_list)}] - {", ".join(pkm_list)}'
            ml_list.append(msg)
            mention_msg = (
                f'- **<@{row.user_id}>** [{len(pkm_list)}] - {", ".join(pkm_list)}'
            )
            mention_list.append(mention_msg)

        return ml_list, mention_list

    def validate_missing_link(self) -> Tuple[List[str], List[str], int]:
        df = self.df
        df = df.loc[(~df[USER_ID_LABEL].isna()) & (df[IMGUR_LABEL].isna())]

        df_grouped = df.groupby(USERNAME_LABEL)

        ml_amount = len(
            [pkm_id for pkm_idx in df_grouped.groups.values() for pkm_id in pkm_idx]
        )

        if hasattr(self, "ml_amount"):
            if self.ml_amount == ml_amount:
                self.ml = False
        ml_list, ml_list_mention = self.get_missing_link(df_grouped)
        self.ml_amount = ml_amount

        return ml_list, ml_list_mention, ml_amount

    def get_participants(
        self,
        *,
        n: Optional[int] = None,
        count: Optional[bool] = False,
        sort_key: Optional[Callable] = None,
        reverse: Optional[bool] = False,
    ) -> List[Tuple[int, str]]:
        if sort_key is None:
            sort_key = lambda s: s[-1]

        participants_dict = {}
        for user_id, pkms in self.user_grouped.groups.items():
            for pkm in pkms:
                row = self.sheet.get_row(pkm)
                if not row.approved_by:
                    continue
                participants[row.user_id] = (
                    len(pkms),
                    f"1. {row.username} (`{user_id}`){f' - {len(pkms)} Drawings' if count is True else ''}",
                )
        participants = list(
            sorted(list(participants_dict.values()), key=sort_key, reverse=reverse)
        )

        return participants[:n]

    async def get_credits(self) -> gists.File:
        credits_rows = [
            HEADERS_FMT % ("Dex", PKM_LABEL, "Art", "Artist", "Artist's ID"),
            HEADERS_FMT % ("---", "---", "---", "---", "---"),
        ]

        start = time.time()
        for idx, row in self.df.iterrows():
            pkm_name = row[PKM_LABEL]
            row = self.sheet.get_pokemon_row(pkm_name)
            pkm_dex = self.sheet.get_pokemon_dex(pkm_name)
            link = "None"
            if row.approved_by:
                user_id = int(row.user_id)

                if row.imgur:
                    imgur = await self.imgur.resolve_url(row.imgur)
                    link = f"![art]({imgur})"

                user = row.username
            else:
                user = user_id = "None"
            credits_rows.append(HEADERS_FMT % (pkm_dex, pkm_name, link, user, user_id))
        log.info(f"AFD Credits: Row loop complete in {round(time.time()-start, 2)}s")
        return gists.File(
            name=CREDITS_FILENAME,
            content=f"""# Formatted table of credits
(Use your browser's "Find in page" feature (Ctrl/CMD + F) to look for specific ones)

(Click on an image to see a bigger version)

{NL.join(credits_rows)}""".replace(
                "\r", ""
            ),
        )

    async def update_credits(self):
        og_start = time.time()
        contents_file = gists.File(
            name=CONTENTS_FILENAME,
            content=f"""# Contents of this Gist
1. [Top {TOP_N} Participants]({AFD_CREDITS_GIST_URL}#file-1-top-participants-md)
1. [Formatted table of credits]({AFD_CREDITS_GIST_URL}#file-2-credits-md)
1. [List of participants]({AFD_CREDITS_GIST_URL}#file-3-participants-md)""",
        )

        start = time.time()
        top_participants_file = gists.File(
            name=TOP_PARTICIPANTS_FILENAME,
            content=f"""# Top {TOP_N} Participants
Thank you to EVERYONE who participated, but here are the top few that deserve extra recognition!

{NL.join([p for l, p in (self.get_participants(n=TOP_N, count=True, sort_key=lambda s: s[0], reverse=True))])}""".replace(
                "\r", ""
            ),
        )
        log.info(
            f"AFD Credits: Top participants fetched in {round(time.time()-start, 2)}s"
        )

        start = time.time()
        credits_file = await self.get_credits()
        log.info(
            f"AFD Credits: Credits file completed in {round(time.time()-start, 2)}s"
        )

        participants = NL.join([p for l, p in self.get_participants()])
        participants_file = gists.File(
            name=PARTICIPANTS_FILENAME,
            content=f"""# List of participants
In alphabetical order. Thank you everyone who participated!

{participants}""".replace(
                "\r", ""
            ),
        )

        start = time.time()
        files = [contents_file, top_participants_file, credits_file, participants_file]
        await self.credits_gist.edit(
            description=f"THANKS TO ALL {len(participants)} PARTICIPANTS WITHOUT WHOM THIS WOULDN'T HAVE BEEN POSSIBLE!",
            files=files,
        )
        log.info(f"AFD Credits: Updated credits in {round(time.time()-og_start, 2)}s")


async def setup(bot):
    await bot.add_cog(Afd(bot))
