import os
import re
import datetime
import pandas as pd
import json
import time
import logging
from functools import cached_property
from typing import Optional, Callable, Dict, List, Tuple

import discord
from discord.ext import commands, tasks
import gists
import random
from replit import db

from constants import NEW_LINE as NL
from keep_alive import app


IMGUR_API_URL = "https://api.imgur.com/3/album/%s/images"
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
IMGUR_CLIENT_SECRET = os.getenv("IMGUR_CLIENT_SECRET")

IMAGE_URL = os.getenv("POKETWO_IMAGE_SERVER_API")
SHEET_URL = os.getenv("AFD_SHEET_URL")
AFD_GIST_URL = os.getenv("AFD_GIST_URL")
AFD_CREDITS_GIST_URL = os.getenv("AFD_CREDITS_GIST_URL")
UPDATE_CHANNEL_ID = os.getenv("AFD_UPDATE_CHANNEL_ID")
ROW_INDEX_OFFSET = 8  # The number of rows after which the pokemon indexes begin
DEL_ATTRS_TO_UPDATE = ["unc_amount", "unr_amount", "ml_amount"]

UNC_FILENAME = "Unclaimed Pokemon.md"
UNR_FILENAME = "Unreviewed Pokemon.md"
ML_FILENAME = "Incomplete Pokemon.md"
CONTENTS_FILENAME = "(0) Contents.md"
TOP_PARTICIPANTS_FILENAME = "(1) Top Participants.md"
CREDITS_FILENAME = "(2) Credits.md"
PARTICIPANTS_FILENAME = "(3) Participants.md"

ID_LABEL = "Discord ID"
IMGUR_LABEL = "Imgur Link"
PKM_LABEL = "Pokemon"
CMT_LABEL = "Comments"
DEX_LABEL = "Dex Number"
STATUS_LABEL = "Status"
APPROVED_TXT = "Approved"

ENGLISH_NAME_LABEL_P = "name.en"
ID_LABEL_P = "id"

CR = "\r"
TOP_N = 5


HEADERS_FMT = "|   %s   |   %s   |   %s   |   %s   |   %s   |"


logger = logging.getLogger(__name__)


class Afd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

        self.bot.user_cache = {}
        self.user_cache: dict = self.bot.user_cache

    display_emoji = "🗓️"

    @cached_property
    def original_pk(self):
        return self.bot.get_cog("Poketwo").pk

    async def cog_load(self):
        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("WgithubTOKEN"))

        self.update_channel = await self.bot.fetch_channel(UPDATE_CHANNEL_ID)
        self.afd_gist = await self.gists_client.get_gist(AFD_GIST_URL)
        self.credits_gist = await self.gists_client.get_gist(AFD_CREDITS_GIST_URL)

        self.update_pokemon.start()

    def cog_unload(self):
        self.update_pokemon.cancel()

    async def fetch_user(self, user_id: int) -> discord.User:
        if (user := self.user_cache.get(user_id)) is not None:
            return user

        if (user := self.bot.get_user(user_id)) is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except Exception as e:
                await self.update_channel.send(person_id)
                raise e

        self.user_cache[user_id] = user
        return user

    def validate_unclaimed(self):
        pk = self.pk
        unc_df = pk[pk["Discord name + tag"].isna()].sort_values(by=DEX_LABEL)
        unc_list = []
        unclaimed = {}
        for idx, row in unc_df.iterrows():
            pkm = row[PKM_LABEL]
            try:
                dex = int(
                    self.original_pk[self.original_pk[ENGLISH_NAME_LABEL_P] == pkm][
                        ID_LABEL_P
                    ]
                )
            except TypeError as e:
                print(pkm)
                raise e
            unc_list.append(f"1. {pkm}")
            unclaimed[dex] = {"name": pkm, "image_url": IMAGE_URL % dex}

        db["afd_random"] = json.dumps(unclaimed, indent=4)

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
            location = f"{SHEET_URL[:-24]}/edit#gid=0&range=E{pkm_idx+ROW_INDEX_OFFSET}"

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
            user = await self.fetch_user(int(_id))
            msg = self.format_unreviewed(df, user, pkm_idx)

            df_list.append(msg)

        return df_list

    async def validate_unreviewed(self):
        pk = self.pk
        df = pk.loc[
            (~pk[ID_LABEL].isna())
            & (~pk[IMGUR_LABEL].isna())
            & (pk[STATUS_LABEL] != APPROVED_TXT)
        ]

        df_grouped = df.groupby(ID_LABEL)

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
            pkm_list = df.loc[pkm_idx, PKM_LABEL]
            formatted_list = list(map(lambda x: f"`{x}`", pkm_list))
            msg = f'- **{await self.fetch_user(int(_id))}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            df_list.append(msg)
            mention_msg = f'- **{(await self.fetch_user(int(_id))).mention}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            mention_list.append(mention_msg)

        return df_list, mention_list

    async def validate_missing_link(self):
        pk = self.pk
        df = pk.loc[(~pk[ID_LABEL].isna()) & (pk[IMGUR_LABEL].isna())]

        df_grouped = df.groupby(ID_LABEL)

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

    @commands.is_owner()
    @commands.group(invoke_without_command=True)
    async def afd(self, ctx: commands.Context):
        await ctx.send(self.afd_gist.url)

    @commands.is_owner()
    @afd.command()
    async def forceupdate(self, ctx: commands.Context):
        for attr in DEL_ATTRS_TO_UPDATE:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

        await ctx.message.add_reaction("▶️")
        self.update_pokemon.restart()
        await ctx.message.add_reaction("✅")

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
        df_grouped: pd.core.groupby.DataFrameGroupBy,
        *,
        n: Optional[int] = None,
        count: Optional[bool] = False,
        sort_key: Optional[Callable] = None,
        reverse: Optional[bool] = False,
    ) -> str:
        if sort_key is None:
            sort_key = lambda s: s[-1]

        participants = [
            (
                len(pkms),
                f"1. {await self.fetch_user(user_id)} (`{user_id}`){f' - {len(pkms)} Drawings' if count is True else ''}",
            )
            for user_id, pkms in df_grouped.groups.items()
        ]
        participants.sort(key=sort_key, reverse=reverse)

        return NL.join([p for l, p in participants[:n]])

    async def get_credits(self) -> gists.File:
        pk = self.pk
        original_pk = self.original_pk
        credits_rows = [
            HEADERS_FMT % ("Dex", PKM_LABEL, "Art", "Artist", "Artist's ID"),
            HEADERS_FMT % ("---", "---", "---", "---", "---"),
        ]

        for idx, row in pk.iterrows():
            pkm_name = row[PKM_LABEL]
            try:
                pkm_dex = int(
                    original_pk[original_pk[ENGLISH_NAME_LABEL_P] == pkm_name][
                        ID_LABEL_P
                    ]
                )
            except TypeError as e:
                print(pkm_name)
                raise e
            if not pd.isna(person_id := row[ID_LABEL]):
                person_id = int(person_id)

                imgur = row[IMGUR_LABEL]
                if not pd.isna(imgur):
                    imgur = await self.resolve_imgur_url(imgur)
                    link = f"![art]({imgur})"
                else:
                    link = "None"

                user = await self.fetch_user(person_id)
                person = discord.utils.escape_markdown(str(user))
            else:
                person = person_id = "None"
            credits_rows.append(
                HEADERS_FMT % (pkm_dex, pkm_name, link, person, person_id)
            )
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

        df = self.pk
        df_grouped = df.groupby(ID_LABEL)

        contents_file = gists.File(
            name=CONTENTS_FILENAME,
            content=f"""# Contents of this Gist
1. [Top {TOP_N} Participants]({AFD_CREDITS_GIST_URL}#file-1-top-participants-md)
1. [Formatted table of credits]({AFD_CREDITS_GIST_URL}#file-2-credits-md)
1. [List of participants]({AFD_CREDITS_GIST_URL}#file-3-participants-md)""",
        )

        start = time.time()
        logger.info("AFD Credits: Started working on top participants")
        top_participants_file = gists.File(
            name=TOP_PARTICIPANTS_FILENAME,
            content=f"""# Top {TOP_N} Participants
Thank you to EVERYONE who participated, but here are the top few that deserve extra recognition!

{await self.get_participants(df_grouped, n=TOP_N, count=True, sort_key=lambda s: s[0], reverse=True)}""".replace(
                "\r", ""
            ),
        )
        logger.info(f"AFD Credits: Done in {round(time.time()-start, 2)}")

        start = time.time()
        logger.info("AFD Credits: Started working on credits file")
        credits_file = await self.get_credits()
        logger.info(f"AFD Credits: Done in {round(time.time()-start, 2)}")

        start = time.time()
        logger.info("AFD Credits: Started working on participants")
        participants = await self.get_participants(df_grouped)
        participants_file = gists.File(
            name=PARTICIPANTS_FILENAME,
            content=f"""# List of participants
In alphabetical order. Thank you everyone who participated!

{participants}""".replace(
                "\r", ""
            ),
        )
        logger.info(f"AFD Credits: Done in {round(time.time()-start, 2)}")

        start = time.time()
        files = [contents_file, top_participants_file, credits_file, participants_file]
        await self.credits_gist.edit(
            description=f"THANKS TO ALL {len(df_grouped)} PARTICIPANTS WITHOUT WHOM THIS WOULDN'T HAVE BEEN POSSIBLE!",
            files=files,
        )

    # The task that updates the unclaimed pokemon gist
    @tasks.loop(minutes=5)
    async def update_pokemon(self):
        og_start = time.time()
        logger.info(f"AFD: Task started")

        start = time.time()
        logger.info(f"AFD: Fetching spreadsheet started")
        self.pk = pd.read_csv(
            SHEET_URL, index_col=0, header=6, dtype={ID_LABEL: object}
        )
        logger.info(f"AFD: Done in {round(time.time()-start, 2)}")

        self.pk.reset_index(inplace=True)
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
            unc_content = f'# Unclaimed Pokemon\nCount: {unc_amount}\n## [Pick a random one](https://yeet.witherredaway.repl.co/afd/random)\n## Pokemon: \n<details>\n<summary>Click to expand</summary>\n\n{NL.join(unc_list) if unc_list else "None"}\n\n</details>'
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
            return

        description = f"{self.ml_amount} claimed pokemon with missing links, {self.unc_amount} unclaimed pokemon and {self.unr_amount} unreviewed pokemon - As of {date} GMT (Checks every 5 minutes, and updates only if there is a change)"
        start = time.time()
        await self.afd_gist.edit(
            files=files,
            description=description,
        )

        start = time.time()
        logger.info(f"AFD: Updating credits started")
        try:
            await self.update_credits()
        except Exception as e:
            await self.update_channel.send(e)
            raise e
        logger.info(f"AFD: Updated credits in {round(time.time()-start, 2)}s")

        update_msg = f"""Updated {" and ".join(updated)}!
(<{self.afd_gist.url}>)

Credits: <{self.credits_gist.url}>"""
        await self.update_channel.send(update_msg)
        logger.info(f"AFD: Task completed in {round(time.time()-og_start, 2)}s")

    @update_pokemon.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Afd(bot))
