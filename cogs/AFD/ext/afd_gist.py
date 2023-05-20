from __future__ import annotations
import datetime
import logging
import time
import pandas as pd
from pandas.core.groupby.generic import GroupBy
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

import discord
from discord.ext import commands, tasks
from cogs.AFD.utils.constants import HEADERS_FMT, TOP_N
from cogs.AFD.utils.filenames import (
    CONTENTS_FILENAME,
    CREDITS_FILENAME,
    ML_FILENAME,
    PARTICIPANTS_FILENAME,
    TOP_PARTICIPANTS_FILENAME,
    UNC_FILENAME,
    UNR_FILENAME,
)
from cogs.AFD.utils.labels import (
    APPROVED_LABEL,
    CMT_LABEL,
    DEX_LABEL,
    IMAGE_LABEL,
    PKM_LABEL,
    USER_ID_LABEL,
    USERNAME_LABEL,
)
from cogs.AFD.utils.urls import AFD_CREDITS_GIST_URL, SHEET_URL
from cogs.AFD.utils.utils import Row
import gists

from helpers.constants import LOG_BORDER, NL

if TYPE_CHECKING:
    from main import Bot


log = logging.getLogger("cogs.AFD.afd")


class AfdGist(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

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
            link = df.loc[pkm_idx, IMAGE_LABEL]
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
            & (~self.df[IMAGE_LABEL].isna())
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
                if not row.claimed and not row.image:
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
        df = df.loc[(~df[USER_ID_LABEL].isna()) & (df[IMAGE_LABEL].isna())]

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
                participants_dict[row.user_id] = (
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
                user_id = row.user_id

                if row.image:
                    link = f"![art]({row.image})"

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
            description=f"THANKS TO ALL {len(participants.split(NL))} PARTICIPANTS WITHOUT WHOM THIS WOULDN'T HAVE BEEN POSSIBLE!",
            files=files,
        )
        log.info(f"AFD Credits: Updated credits in {round(time.time()-og_start, 2)}s")
