import os
import datetime
import pandas as pd
import json

import discord
from discord.ext import commands, tasks
import gists
import random
from replit import db
from functools import cached_property

from constants import NEW_LINE as NL
from keep_alive import app


IMAGE_URL = "https://poketwo.s3.object1.us-east-1.tswcloud.com/staging/images/%s.png?v=26"
SHEET_URL = os.getenv("AFD_SHEET_URL")
AFD_GIST_ID = os.getenv("AFD_GIST_ID")
UNC_FILENAME = "Unclaimed Pokemon.md"
UNR_FILENAME = "Unreviewed Pokemon.md"
ML_FILENAME = "Incomplete Pokemon.md"
CONTENTS_FILENAME = "Contents.md"
UPDATE_CHANNEL_ID = os.getenv("AFD_UPDATE_CHANNEL_ID")
ROW_INDEX_OFFSET = 8  # The number of rows after which the pokemon indexes begin
DEL_ATTRS_TO_UPDATE = ["unc_amount", "unr_amount", "ml_amount"]


class Afd(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

        self.update_pokemon.start()

    @cached_property
    def original_pk(self):
        return self.bot.get_cog("Poketwo").pk

    async def cog_load(self):
        self.gists_client = gists.Client()
        await self.gists_client.authorize(os.getenv("WgithubTOKEN"))

        self.update_channel = await self.bot.fetch_channel(UPDATE_CHANNEL_ID)
        self.afd_gist = await self.gists_client.get_gist(AFD_GIST_ID)

    def cog_unload(self):
        self.update_pokemon.cancel()

    display_emoji = "🧪"

    def format_unreviewed(
        self, df: pd.DataFrame, user: discord.User, pkm_indexes: list
    ):
        pkm_list = []
        for idx, pkm_idx in enumerate(pkm_indexes):
            pokename = df.loc[pkm_idx, "Pokemon"]
            comment = (
                df.loc[pkm_idx, "Comments"]
                if str(df.loc[pkm_idx, "Comments"]) != "nan"
                else None
            )
            link = df.loc[pkm_idx, "Imgur Link"]
            location = f"{SHEET_URL[:-24]}/edit#gid=0&range=E{pkm_idx+ROW_INDEX_OFFSET}"

            comment_text = f"""(Marked for review)
        - Comments: {comment}
            """
            text = f"""
1. `{pokename}` {comment_text if comment else ""}
    - [Sheet location]({location})
    - [Imgur]({link})"""
            pkm_list.append(text)
        format_list = "\n".join(pkm_list)
        return_text = f"""<details>
<summary>{user} ({user.id}) - {len(pkm_list)}</summary>
{format_list}
</details>"""
        return return_text

    def validate_unclaimed(self):
        pk = self.pk
        unc_df = pk[pk["Discord name + tag"].isna()].sort_values(by="Dex Number")
        unc_list = []
        unclaimed = {}
        for idx, row in unc_df.iterrows():
            pkm = row["Pokemon"]
            try:
                dex = int(self.original_pk[self.original_pk["name.en"] == pkm]["id"])
            except TypeError:
                continue
            unc_list.append(f"1. [{pkm}]({SHEET_URL[:-24]}/edit#gid=0&range=B{idx+ROW_INDEX_OFFSET})")
            unclaimed[dex] = {'name': pkm, 'sheet_url': f"{SHEET_URL[:-24]}/edit#gid=0&range=B{idx+ROW_INDEX_OFFSET}", 'image_url': IMAGE_URL % dex}

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

    async def get_unreviewed(self, df, df_grouped):
        df_list = []
        for _id, pkm_idx in df_grouped.groups.items():
            user = await self.bot.fetch_user(int(_id))
            msg = self.format_unreviewed(df, user, pkm_idx)

            df_list.append(msg)

        return df_list

    async def validate_unreviewed(self):
        pk = self.pk
        df = pk.loc[
            (~pk["Discord ID"].isna())
            & (~pk["Imgur Link"].isna())
            & (pk["Status"] != "Approved")
        ]

        df_grouped = df.groupby("Discord ID")

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
            pkm_list = df.loc[pkm_idx, "Pokemon"]
            formatted_list = list(map(lambda x: f"`{x}`", pkm_list))
            msg = f'- **{await self.bot.fetch_user(int(_id))}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            df_list.append(msg)
            mention_msg = f'- **{(await self.bot.fetch_user(int(_id))).mention}** [{len(pkm_list)}] - {", ".join(formatted_list)}'
            mention_list.append(mention_msg)

        return df_list, mention_list

    async def validate_missing_link(self):
        pk = self.pk
        df = pk.loc[(~pk["Discord ID"].isna()) & (pk["Imgur Link"].isna())]

        df_grouped = df.groupby("Discord ID")

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
    @commands.command()
    async def forceupdate(self, ctx: commands.Context):
        for attr in DEL_ATTRS_TO_UPDATE:
            try:
                delattr(self, attr)
            except AttributeError:
                pass

        await ctx.message.add_reaction("▶️")
        self.update_pokemon.restart()
        await ctx.message.add_reaction("✅")

    # The task that updates the unclaimed pokemon gist
    @tasks.loop(minutes=5)
    async def update_pokemon(self):
        self.pk = pd.read_csv(
            SHEET_URL, index_col=0, header=6, dtype={"Discord ID": object}
        )
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
        await self.afd_gist.edit(
            files=files,
            description=description,
        )
        update_msg = f"""Updated {" and ".join(updated)}!
({self.afd_gist.url})"""
        await self.update_channel.send(update_msg)

    @update_pokemon.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Afd(bot))
