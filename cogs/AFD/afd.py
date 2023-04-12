from __future__ import annotations

import datetime
import logging
import os
import time
import typing
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

from helpers.context import CustomContext
from helpers.constants import LOG_BORDER, NL
from ..utils.utils import UrlView, make_progress_bar
from .utils.constants import (
    APPROVED_TXT,
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
    CMT_LABEL,
    DEX_LABEL,
    DEX_LABEL_P,
    ENGLISH_NAME_LABEL_P,
    USER_ID_LABEL,
    IMGUR_LABEL,
    PKM_LABEL,
    STATUS_LABEL,
    USERNAME_LABEL,
)

from .utils.urls import (
    AFD_CREDITS_GIST_URL,
    AFD_GIST_URL,
    IMAGE_URL,
    SHEET_URL,
)

if typing.TYPE_CHECKING:
    from main import Bot


CLAIM_LIMIT = 5
AFD_ROLE_ID = 1095381341178183851
AFD_ADMIN_ROLE_ID = 1095393318281678848

IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
IMGUR_CLIENT_SECRET = os.getenv("IMGUR_CLIENT_SECRET")


log = logging.getLogger(__name__)


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

    def unclaim(self, pokemon: str):
        for col in self.df.columns[1:]:  # For all columns after Pokemon
            self.edit_row_where(PKM_LABEL, pokemon, set_column=col, to_val=None)

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
                    STATUS_LABEL,
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


class Afd(commands.Cog):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.hidden = True

        self.bot.user_cache: dict = {}
        self.user_cache = self.bot.user_cache

        self.sheet: AfdSheet

    display_emoji = "🗓️"

    @property
    def pk(self) -> pd.DataFrame:
        return self.bot.pk

    @property
    def df(self) -> pd.DataFrame:
        return self.sheet.df

    @property
    def total_amount(self) -> int:
        return len(self.df)

    async def cog_load(self):
        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("WgithubTOKEN"))

        self.update_channel = await self.bot.fetch_channel(UPDATE_CHANNEL_ID)
        self.afd_gist = await self.gists_client.get_gist(AFD_GIST_URL)
        self.credits_gist = await self.gists_client.get_gist(AFD_CREDITS_GIST_URL)

        start = time.time()
        await self.sheet.setup()
        log.info(f"AFD: Fetched spreadsheet in {round(time.time()-start, 2)}s")

        self.update_pokemon.start()

    async def cog_unload(self):
        self.update_pokemon.cancel()

    @cached_property
    def sheet(self) -> AfdSheet:
        return AfdSheet(SHEET_URL, pokemon_df=self.pk)

    @commands.check_any(commands.is_owner(), commands.has_role(AFD_ROLE_ID))
    @commands.group(
        name="afd",
        brief="Afd commands",
        description="Command with a variety of afd subcommands!",
    )
    async def afd(self, ctx: CustomContext):
        await self.sheet.update_df()
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.info)

    @afd.command(
        name="info",
        aliases=("information", "progress"),
        brief="View progress of the april fool's event.",
    )
    async def info(self, ctx: CustomContext):
        url_dict = {
            "AFD Gist": (self.afd_gist.url, 0),
            "AFD Credits": (self.credits_gist.url, 0),
            "Spreadsheet": (self.sheet.url, 1),
        }
        view = UrlView(url_dict)

        unc_list, unc_amount = self.validate_unclaimed()
        claimed_amount = self.total_amount - unc_amount

        ml_list, ml_list_mention, ml_amount = await self.validate_missing_link()
        completed_amount = claimed_amount - ml_amount

        unr_list, unr_amount = await self.validate_unreviewed()

        embed = self.bot.Embed(title="April Fool's Day Event")

        embed.add_field(
            name="Completed",
            value=f"{make_progress_bar(completed_amount, self.total_amount)} {completed_amount}/{self.total_amount}",
            inline=False,
        )
        embed.add_field(
            name="Claimed",
            value=f"{make_progress_bar(claimed_amount, self.total_amount)} {claimed_amount}/{self.total_amount}",
            inline=False,
        )
        embed.add_field(
            name="Unreviewed",
            value=f"{make_progress_bar(unr_amount, completed_amount)} {unr_amount}/{completed_amount}",
            inline=False,
        )

        await ctx.send(embed=embed, view=view)

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
    @afd.command(
        name="new_spreadsheet",
        brief="Used to create a brand new spreadsheet.",
        description="Sets up a new spreadsheet to use. Intended to be used only once.",
    )
    async def new(self, ctx: CustomContext):
        if hasattr(self, "sheet"):
            return await ctx.send("A spreadsheet already exists.")

        async with ctx.typing():
            self.sheet: AfdSheet = await AfdSheet.create_new(pokemon_df=self.pk)

        embed = self.bot.Embed(
            title="New Spreadsheet created",
            description=f"[Please set it permanently in the code.]({self.sheet.url})",
        )
        await ctx.send(embed=embed, view=UrlView({"Go To Spreadsheet": self.sheet.url}))

    def get_pokemon(self, name: Union[str, int]) -> str:
        return self.pk.loc[
            (self.pk["slug"].str.casefold() == name)
            | (self.pk["name.ja"].str.casefold() == name)
            | (self.pk["name.ja_r"].str.casefold() == name)
            | (self.pk["name.ja_t"].str.casefold() == name)
            | (self.pk["name.en"].str.casefold() == name)
            | (self.pk["name.en2"].str.casefold() == name)
            | (self.pk["name.de"].str.casefold() == name)
            | (self.pk["name.fr"].str.casefold() == name)
        ]["name.en"].iloc[0]

    @afd.command(
        name="claim",
        brief="Claim a pokemon to draw",
        description=f"Claim a pokemon to draw. Can have upto {CLAIM_LIMIT} claimed pokemon at a time!",
        help="Pass in a pokemon already claimed by you to unclaim, alternatively you can use the `unclaim` command. Pokemon alt names are supported!",
    )
    async def claim(self, ctx: CustomContext, *, pokemon: str):
        try:
            pokemon = self.get_pokemon(pokemon.casefold())
        except IndexError:
            return await ctx.send("Invalid pokemon provided!")

        function = None

        row = self.df.loc[self.df[PKM_LABEL] == pokemon]
        user = row[USERNAME_LABEL].iloc[0]
        user_id = row[USER_ID_LABEL].iloc[0]
        complete = not pd.isna(row[IMGUR_LABEL].iloc[0])
        if pd.isna(user_id):
            if self.sheet.can_claim(ctx.author) is False:
                return await ctx.send(
                    f"You already have the max number ({CLAIM_LIMIT}) of pokemon claimed!"
                )

            conf, cmsg = await ctx.confirm(
                f"Are you sure you want to claim **{pokemon}**?",
                edit_after="Hang on...",
            )
            if conf is False:
                return

            function = self.sheet.claim
            args = (ctx.author, pokemon)
            content = f"You have successfully claimed **{pokemon}**, have fun! :D\n\nYou can undo this using the `unclaim` command."
        elif user_id == str(ctx.author.id):
            conf, cmsg = await ctx.confirm(
                f"**{pokemon}** is already claimed by you!\n\nWould you like to unclaim?{' You have already submitted a drawing which will be removed.' if complete is True else ''}",
                edit_after="Hang on...",
                confirm_label="Unclaim",
            )
            if conf is False:
                return

            function = self.sheet.unclaim
            args = (pokemon,)
            content = f"You have successfully unclaimed **{pokemon}**."
        else:
            return await ctx.send(f"**{pokemon}** is already claimed by **{user}**!")

        # Check once again for any changes to the sheet
        await self.sheet.update_df()
        row = self.df.loc[self.df[PKM_LABEL] == pokemon]
        user = row[USERNAME_LABEL].iloc[0]
        user_id = row[USER_ID_LABEL].iloc[0]
        if not any((pd.isna(user_id), user_id == str(ctx.author.id))):
            return await cmsg.edit(
                content=f"**{pokemon}** is already claimed by **{user}**!"
            )

        # Perform the claiming/unclaiming
        if function:
            function(*args)

        await self.sheet.update_sheet()
        await cmsg.edit(content=content)

    @afd.command(
        name="unclaim",
        brief="Unclaim a pokemon",
        description=f"Unclaim a pokemon already claimed by you.",
        help="""Pass in a pokemon already claimed by you to unclaim. Pokemon alt names are supported!

Admins can force unclaim.""",
    )
    async def unclaim(self, ctx: CustomContext, *, pokemon: str):
        try:
            pokemon = self.get_pokemon(pokemon.casefold())
        except IndexError:
            return await ctx.send("Invalid pokemon provided!")

        function = None

        row = self.df.loc[self.df[PKM_LABEL] == pokemon]
        user = row[USERNAME_LABEL].iloc[0]
        user_id = row[USER_ID_LABEL].iloc[0]
        complete = not pd.isna(row[IMGUR_LABEL].iloc[0])
        if pd.isna(user_id):
            if self.sheet.can_claim(ctx.author) is False:
                return await ctx.send(
                    f"""**{pokemon}** is not claimed yet.

I would ask you if you'd like to claim it, but you already have the max number ({CLAIM_LIMIT}) of pokemon claimed :("""
                )
            conf, cmsg = await ctx.confirm(
                f"**{pokemon}** is not claimed yet, would you like to claim it?",
                edit_after="Hang on...",
                confirm_label="Claim",
            )
            if conf is False:
                return

            function = self.sheet.claim
            args = (ctx.author, pokemon)
            content = f"You have successfully claimed **{pokemon}**, have fun! :D\n\nYou can undo this using the `unclaim` command."
        elif user_id == str(ctx.author.id):
            conf, cmsg = await ctx.confirm(
                f"Are you sure you want to unclaim **{pokemon}**?{' You have already submitted a drawing which will be removed.' if complete is True else ''}",
                edit_after="Hang on...",
                confirm_label="Unclaim",
            )
            if conf is False:
                return

            function = self.sheet.unclaim
            args = (pokemon,)
            content = f"You have successfully unclaimed **{pokemon}**."
        else:
            prompt = f"**{pokemon}** is claimed by **{user}**!"
            if AFD_ADMIN_ROLE_ID not in (r.id for r in ctx.author.roles):
                return await ctx.send(prompt)
            conf, cmsg = await ctx.confirm(
                f"{prompt}\n\nSince you are registered as an Admin, would you like to **force** unclaim it?{' A drawing has already been submitted which will be removed.' if complete is True else ''}",
                edit_after="Hang on...",
                confirm_label="Force Unclaim",
            )
            if conf is False:
                return

            function = self.sheet.unclaim
            args = (pokemon,)
            content = (
                f"You have successfully force unclaimed **{pokemon}** from **{user}**."
            )

        # Perform the claiming/unclaiming
        if function:
            function(*args)

        await self.sheet.update_sheet()
        await cmsg.edit(content=content)

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
        unr_list, unr_amount = await self.validate_unreviewed()
        self.ml = True
        ml_list, ml_list_mention, ml_amount = await self.validate_missing_link()

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
        start = time.time()
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
    def pk_grouped(
        self, label: Optional[str] = USER_ID_LABEL
    ) -> pd.core.groupby.DataFrameGroupBy:
        return self.df.groupby(label)

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

    def get_dex_from_name(self, name: str):
        try:
            return int(self.pk[self.pk[ENGLISH_NAME_LABEL_P] == name][DEX_LABEL_P])
        except TypeError as e:
            print(name)
            raise e

    def validate_unclaimed(self):
        df = self.df
        unc_df = df[df[USERNAME_LABEL].isna()].sort_values(by=DEX_LABEL)
        unc_list = []
        for idx, row in unc_df.iterrows():
            pkm = row[PKM_LABEL]
            unc_list.append(f"1. {pkm}")

        unc_amount = len(unc_list)
        if hasattr(self, "unc_amount"):
            if self.unc_amount == unc_amount:
                self.unc = False
                return False, unc_amount
            else:
                self.unc_amount = unc_amount
        else:
            self.unc_amount = unc_amount

        return unc_list, unc_amount

    def format_unreviewed(
        self, df: pd.DataFrame, user: discord.User, pkm_indexes: list
    ):
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

            comment_text = f"""(Marked for review)
        - Comments: {comment}
            """
            text = f"""
1. `{pokename}` {comment_text if comment else ""}"""
            # - [Sheet location]({location})
            # - [Imgur]({link})"""
            pkm_list.append(text)
        format_list = "\n".join(pkm_list)
        return_text = f"""<details>
<summary>{user} ({user.id}) - {len(pkm_list)}</summary>
{format_list}
</details>"""
        return return_text

    async def get_unreviewed(self, df, df_grouped):
        df_list = []
        for _id, pkm_idx in df_grouped.groups.items():
            if pd.isna(_id):
                continue
            user = await self.fetch_user(int(_id))
            msg = self.format_unreviewed(df, user, pkm_idx)

            df_list.append(msg)

        return df_list

    async def validate_unreviewed(self):
        pk = self.df
        df = pk.loc[
            (~pk[USER_ID_LABEL].isna())
            & (~pk[IMGUR_LABEL].isna())
            & (pk[STATUS_LABEL] != APPROVED_TXT)
        ]

        df_grouped = df.groupby(USER_ID_LABEL)

        unr_amount = len(
            [pkm_id for pkm_idx in df_grouped.groups.values() for pkm_id in pkm_idx]
        )

        if hasattr(self, "unr_amount"):
            if self.unr_amount == unr_amount:
                self.unr = False
                return False, unr_amount
            else:
                unr_list = await self.get_unreviewed(df, df_grouped)
                self.unr_amount = unr_amount
        else:
            unr_list = await self.get_unreviewed(df, df_grouped)
            self.unr_amount = unr_amount

        return unr_list, unr_amount

    async def get_missing_link(self, df, df_grouped):
        df_list = []
        mention_list = []
        for _id, pkm_idx in df_grouped.groups.items():
            if pd.isna(_id):
                continue
            pkm_list = df.loc[pkm_idx, PKM_LABEL]
            formatted_list = list(map(lambda x: f"`{x}`", pkm_list))
            msg = f'- **{await self.fetch_user(int(_id))}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            df_list.append(msg)
            mention_msg = f'- **{(await self.fetch_user(int(_id))).mention}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            mention_list.append(mention_msg)

        return df_list, mention_list

    async def validate_missing_link(self):
        pk = self.df
        df = pk.loc[(~pk[USER_ID_LABEL].isna()) & (pk[IMGUR_LABEL].isna())]

        df_grouped = df.groupby(USER_ID_LABEL)

        ml_amount = len(
            [pkm_id for pkm_idx in df_grouped.groups.values() for pkm_id in pkm_idx]
        )

        if hasattr(self, "ml_amount"):
            if self.ml_amount == ml_amount:
                self.ml = False
                return False, False, ml_amount
            else:
                ml_list, ml_list_mention = await self.get_missing_link(df, df_grouped)
                self.ml_amount = ml_amount
        else:
            ml_list, ml_list_mention = await self.get_missing_link(df, df_grouped)
            self.ml_amount = ml_amount

        return ml_list, ml_list_mention, ml_amount

    async def resolve_imgur_url(self, url: str):
        if url.startswith("https://imgur.com/"):
            link = (url.replace("https://imgur.com/", "").strip()).split("/")
            _id = link[-1]
            if link[0] == "a":
                req_url = f"https://api.imgur.com/3/album/{_id}"
            elif link[0] == "gallery":
                req_url = f"https://api.imgur.com/3/gallery/{_id}"
            elif len(link) == 1:
                return f"https://i.imgur.com/{_id}.png"
        elif url.startswith("https://i.imgur.com/"):
            return url
        else:
            raise ValueError(f"Invalid url: {url}")

        headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
        log.info("Calling Imgur API")
        async with self.bot.session.get(req_url, headers=headers) as resp:
            try:
                result = await resp.json()
            except aiohttp.ContentTypeError:
                print("Error requesting", req_url)
                print("Text:")
                print(await resp.text())
                raise
            else:
                try:
                    return result["data"]["images"][0]["link"]
                except KeyError as e:
                    print(result)

    async def get_participants(
        self,
        *,
        n: Optional[int] = None,
        count: Optional[bool] = False,
        sort_key: Optional[Callable] = None,
        reverse: Optional[bool] = False,
    ) -> List[Tuple[int, str]]:
        if sort_key is None:
            sort_key = lambda s: s[-1]

        participants = []
        for user_id, pkms in self.pk_grouped.groups.items():
            if pd.isna(user_id):
                continue
            participants.append(
                (
                    len(pkms),
                    f"1. {await self.fetch_user(user_id)} (`{user_id}`){f' - {len(pkms)} Drawings' if count is True else ''}",
                )
            )
        participants.sort(key=sort_key, reverse=reverse)

        return participants[:n]

    async def get_credits(self) -> gists.File:
        pk = self.df
        credits_rows = [
            HEADERS_FMT % ("Dex", PKM_LABEL, "Art", "Artist", "Artist's ID"),
            HEADERS_FMT % ("---", "---", "---", "---", "---"),
        ]

        start = time.time()
        for idx, row in pk.iterrows():
            pkm_name = row[PKM_LABEL]
            pkm_dex = self.get_dex_from_name(pkm_name)
            link = "None"
            if not pd.isna(person_id := row[USER_ID_LABEL]):
                person_id = int(person_id)

                imgur = row[IMGUR_LABEL]
                if not pd.isna(imgur):
                    imgur = await self.resolve_imgur_url(imgur)
                    link = f"![art]({imgur})"

                user = await self.fetch_user(person_id)
                person = discord.utils.escape_markdown(str(user))
            else:
                person = person_id = "None"
            credits_rows.append(
                HEADERS_FMT % (pkm_dex, pkm_name, link, person, person_id)
            )
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

{NL.join([p for l, p in (await self.get_participants(n=TOP_N, count=True, sort_key=lambda s: s[0], reverse=True))])}""".replace(
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

        participants = NL.join([p for l, p in await self.get_participants()])
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
            description=f"THANKS TO ALL {len(self.pk_grouped)} PARTICIPANTS WITHOUT WHOM THIS WOULDN'T HAVE BEEN POSSIBLE!",
            files=files,
        )
        log.info(f"AFD Credits: Updated credits in {round(time.time()-og_start, 2)}s")


async def setup(bot):
    await bot.add_cog(Afd(bot))
