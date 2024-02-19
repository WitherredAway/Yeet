from __future__ import annotations
import asyncio
from collections import defaultdict
import io

import logging
import re
import time
from typing import (
    TYPE_CHECKING,
    Callable,
    Coroutine,
    DefaultDict,
    List,
    Optional,
    Tuple,
    Union,
)
import PIL
from PIL import Image
import numpy as np
import pandas as pd
import random
from functools import cached_property
import difflib

import discord
import gists
from discord.ext import commands

from helpers.constants import INDENT, NL
from helpers.context import CustomContext
from cogs.AFD.utils.labels import PKM_LABEL
from cogs.AFD.utils.random import (
    RandomFlagDescriptions,
    RandomView,
    SkipView,
    RandomFlags,
)
from cogs.AFD.utils.list_paginator import (
    ActionSelectMenu,
    ListPageMenu,
    ListPageSource,
    ListSelectMenu,
    StatsPageMenu,
    RemindAllButton,
)
from ..utils.utils import (
    UrlView,
    enumerate_list,
    force_log_errors,
    reload_modules,
    url_to_image,
)
from .utils.views import AfdView, PokemonView
from .utils.utils import AFDRoleMenu, Stats, EmbedColours, Row, get_initial, URL_REGEX
from .utils.urls import AFD_CREDITS_GIST_URL, SHEET_URL
from .utils.sheet import AfdSheet
from .utils.constants import (
    AFD_ADMIN_ROLE_ID,
    AFD_ROLE_ID,
    AFD_LOG_CHANNEL_ID,
    AFD_UPDATE_CHANNEL_ID,
)
from .ext.afd_gist import AfdGist

if TYPE_CHECKING:
    from main import Bot


logger = logging.getLogger(__name__)


class Afd(AfdGist):
    def __init__(self, bot):
        self.bot: Bot = bot
        self.hidden = True

        self.sheet: AfdSheet

    display_emoji = "🗓️"

    async def setup(self):
        await self.reload_sheet()
        self.bot.afd_log_channel = await self.bot.fetch_channel(AFD_LOG_CHANNEL_ID)
        self.bot.afd_update_channel = await self.bot.fetch_channel(
            AFD_UPDATE_CHANNEL_ID
        )
        try:
            self.bot.afd_credits_gist = await self.bot.wgists_client.get_gist(
                AFD_CREDITS_GIST_URL
            )
        except gists.HTTPException as e:
            await self.bot.report_error(e)

        self.bot.add_view(AFDRoleMenu())

    async def reload_sheet(self):
        self.bot.sheet = AfdSheet(SHEET_URL, pokemon_df=self.pk) if SHEET_URL else None
        start = time.time()
        await self.bot.sheet.setup()
        logger.info(f"AFD: Fetched spreadsheet in {round(time.time()-start, 2)}s")

    @force_log_errors
    async def cog_unload(self):
        reload_modules("cogs/AFD", skip=__name__)

    def cog_check(self, ctx: CustomContext):
        if not ctx.guild:
            return False

        roles = [r.id for r in ctx.author.roles]
        return any(
            (
                ctx.author.id in ctx.bot.owner_ids,
                AFD_ROLE_ID in roles,
                AFD_ADMIN_ROLE_ID in roles,
            )
        )

    def is_admin(self, user: discord.Member) -> bool:
        return AFD_ADMIN_ROLE_ID in [r.id for r in user.roles]

    @property
    def sheet(self) -> AfdSheet:
        return self.bot.sheet

    @sheet.setter
    def sheet(self, value: AfdSheet):
        self.bot.sheet = value

    @property
    def log_channel(self) -> discord.TextChannel:
        return self.bot.afd_log_channel

    @property
    def update_channel(self) -> discord.TextChannel:
        return self.bot.afd_update_channel

    @property
    def credits_gist(self) -> gists.Gist:
        return self.bot.afd_credits_gist

    @property
    def pk(self) -> pd.DataFrame:
        return self.bot.pk

    @cached_property
    def all_pk_names(self) -> list:
        pk = self.pk
        names = (
            list(pk["slug"])
            + list(pk["name.ja"])
            + list(pk["name.ja_r"])
            + list(pk["name.ja_t"])
            + list(pk["name.en"])
            + list(pk["name.en2"])
            + list(pk["name.de"])
            + list(pk["name.fr"])
        )
        return list(filter(lambda n: n is not np.nan, names))

    @property
    def df(self) -> pd.DataFrame:
        return self.sheet.df

    @property
    def total_amount(self) -> int:
        return len(self.df)

    def confirmation_embed(
        self,
        description: str,
        *,
        row: Optional[Row] = None,
        colour: Optional[EmbedColours] = None,
        footer: Optional[str] = None,
        show_image: Optional[bool] = True,
    ) -> Bot.Embed:
        embed = self.bot.Embed(
            description=description, colour=colour.value if colour else colour
        )
        if row is not None:
            pokemon_image = self.sheet.get_pokemon_image(row.pokemon)
            embed.set_thumbnail(url=pokemon_image)
            if row.image and show_image:
                embed.set_image(url=row.image)
        if footer:
            embed.set_footer(text=footer)
        return embed

    async def fetch_user(
        self, user_id: int, /, return_from_cache: Optional[bool] = False
    ) -> Tuple[discord.User, bool]:
        try:
            user, from_cache = await self.bot.fetch_user_cache(user_id)
        except Exception as e:
            await self.update_channel.send(user_id)
            raise e

        return (user, from_cache) if return_from_cache else user

    def pkm_remind_embed(self, pkm_rows: Union[Row, List[Row]]) -> Bot.Embed:
        if not isinstance(pkm_rows, list):
            pkm_rows = [pkm_rows]
        embed = self.bot.Embed(
            title="AFD Reminder",
        )
        pkms = [
            f"- {row.pokemon}{f' (`{row.comment}`)' if row.comment else ''}"
            for row in pkm_rows
        ]
        embed.add_field(
            name="Your following claimed Pokémon have not been completed/corrected yet",
            value=NL.join(pkms),
            inline=False,
        )
        embed.add_field(name="Deadline", value=self.sheet.DEADLINE_TS, inline=False)
        embed.set_footer(
            text="Please draw them or unclaim any you think you cannot finish. Thank you!"
        )
        return embed

    async def send_notification(
        self,
        embed: Union[Bot.Embed, List[Bot.Embed]],
        *,
        user: Union[discord.abc.Snowflake, int],
        ctx: CustomContext,
        view: Optional[discord.ui.View] = None,
    ) -> bool:
        if not isinstance(embed, list):
            embed = [embed]

        if not isinstance(user, discord.abc.Snowflake):
            user = discord.Object(user)

        try:
            dm = await self.bot.create_dm(user)
            await asyncio.create_task(dm.send(embeds=embed, view=view))
        except (discord.Forbidden, discord.HTTPException):
            await asyncio.create_task(
                ctx.send(f"<@{user.id}> (Unable to DM)", embeds=embed, view=view)
            )
            return False
        else:
            return True

    def pokemon_by_name(self, name: str) -> Union[str, None, Tuple[str, str]]:
        try:
            name = self.sheet.get_pokemon(name)
        except IndexError:
            autocorrection = difflib.get_close_matches(name, self.all_pk_names)
            if not autocorrection:
                return None

            autocorrection = autocorrection[0]
            return self.pokemon_by_name(autocorrection), autocorrection
        return name

    async def get_pokemon(self, ctx: CustomContext, name: str) -> Union[str, None]:
        pokemon = self.pokemon_by_name(name)
        if pokemon is None:
            await ctx.reply(
                embed=self.confirmation_embed(
                    f"`{name}` is not a valid Pokémon!", colour=EmbedColours.INVALID
                )
            )
        elif isinstance(pokemon, tuple):
            await ctx.reply(
                embed=self.confirmation_embed(
                    f"`{name}` is not a valid Pokémon, did you mean `{pokemon[-1]}`?",
                    colour=EmbedColours.INVALID,
                )
            )
            pokemon = pokemon[0]

        return pokemon

    async def check_claim(
        self,
        ctx: CustomContext,
        decide_msg: Coroutine[Row, str],
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
                await decide_msg(row),
                row=row,
                colour=EmbedColours.INVALID,
                footer=decide_footer(row) if decide_footer else decide_footer,
            )
            if cmsg:
                await cmsg.edit(embed=embed)
            else:
                await ctx.reply(embed=embed)
            return True
        return False

    @property
    def embed(self) -> Bot.Embed:
        stats = self.get_stats()

        description = f"""**Theme:** {self.sheet.THEME}

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

        stats.correction_pending.total_amount = stats.submitted.amount
        embed.add_field(
            name="Community Stats",
            value=f"""{stats.claimed:bpN}
- {stats.submitted:b-pn}
  - {stats.correction_pending:b--pn}
  - {stats.unreviewed:b--pn}
- {stats.incomplete:b-pn}
- {stats.approved:b-pn}""",
            inline=False,
        )
        return embed

    @commands.group(
        name="afd",
        brief="Afd commands",
        description="Command with a variety of afd event subcommands! If invoked alone, it will show event stats.",
    )
    async def afd(self, ctx: CustomContext):
        await ctx.typing()
        if ctx.subcommand_passed is None:
            await ctx.invoke(self.info)
        elif ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # region RESTRICTED COMMANDS
    # --- Owner only commands ---
    @commands.is_owner()
    @afd.command(
        name="new_spreadsheet",
        brief="Used to create a brand new spreadsheet.",
        description="Sets up a new spreadsheet to use. Intended to be used only once.",
    )
    async def new(self, ctx: CustomContext):
        if self.sheet:
            return await ctx.reply("A spreadsheet already exists.")

        async with ctx.typing():
            new = await AfdSheet.create_new(pokemon_df=self.pk)
            await ctx.send(new.url)
            self.sheet: AfdSheet = new

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
        brief="Forcefully update AFD sheet.",
        description="Used to forcefully update the AFD sheet and AFD credits gist",
    )
    async def forceupdate(self, ctx: CustomContext):
        await ctx.message.add_reaction("▶️")
        await self.reload_sheet()
        await self.update_credits()
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

    # --- AFD Admin only commands ---
    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="forceclaim",
        aliases=("fc",),
        brief="Forcefully claim a pokémon on someone's behalf.",
        description="AFD Admin-only command to forcefully claim a pokémon on someone's behalf.",
        help=f"""When this command is ran, first the sheet data will be fetched. Then:
1. A pokemon, with the normalized and deaccented version of the provided name *including alt names*, will be searched for. If not found, it will return invalid.
2. That pokemon's availability on the sheet will be checked:
{INDENT}**i. If it's *not* claimed yet:**
{INDENT}{INDENT}- If the user already has max claims, it will still give you the option to proceed.
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

        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        if not row.claimed:
            content = None
            if self.sheet.can_claim(user) is False:
                content = f"**{user} ({user.id})** already has the max number ({self.sheet.CLAIM_MAX}) of pokémon claimed, still continue?"

            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    content
                    or f"Are you sure you want to forceclaim **{pokemon}** for **{user} ({user.id})**?",
                    row=row,
                ),
                confirm_label="Force Claim",
            )
            if conf is False:
                return
        elif row.user_id == user.id:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is already claimed by **{user} ({user.id})**!",
                    row=row,
                    colour=EmbedColours.INVALID,
                )
            )
        else:
            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is already claimed by **{await self.fetch_user(row.user_id)} ({row.user_id})**, override and claim it for **{user} ({user.id})**?\
                        {' There is a drawing submitted already which will be removed.' if row.image else ''}",
                    row=row,
                ),
                confirm_label="Force Claim",
            )
            if conf is False:
                return

        row = self.sheet.claim(user, pokemon)
        await self.sheet.update_row(row.dex)
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"You have successfully force claimed **{pokemon}** for **{user} ({user.id})**.",
                row=row,
                colour=EmbedColours.INCOMPLETE,
            )
        )
        embed = self.confirmation_embed(
            f"**{pokemon}** has been forcefully claimed for **{user} ({user.id})**.",
            row=row,
            colour=EmbedColours.INCOMPLETE,
            footer=f"by {ctx.author} ({ctx.author.id})",
        )
        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(embed=embed, view=view)
        embed.description = f"**{pokemon}** has been forcefully claimed for you."
        await self.send_notification(embed, user=user, ctx=ctx, view=view)

    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="forceunclaim",
        aliases=("ufc",),
        brief="Forcefully unclaim a pokémon",
        description="AFD Admin-only command to forcefully unclaim a pokémon",
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

        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        if not row.claimed:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not claimed.",
                    row=row,
                    colour=EmbedColours.INVALID,
                )
            )
        user = await self.fetch_user(row.user_id)
        conf, cmsg = await ctx.confirm(
            embed=self.confirmation_embed(
                f"**{pokemon}** is currently claimed by **{user} ({user.id})**, forcefully unclaim?\
                        {' There is a drawing already submitted which will be removed.' if row.image else ''}",
                row=row,
            ),
            confirm_label="Force Unclaim",
        )
        if conf is False:
            return

        row = self.sheet.unclaim(
            pokemon,
        )
        await self.sheet.update_row(row.dex)
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"You have successfully force unclaimed **{pokemon}** from **{user} ({user.id})**.",
                row=row,
                colour=EmbedColours.UNCLAIMED,
            )
        )
        embed = self.confirmation_embed(
            f"**{pokemon}** has been forcefully unclaimed from **{user} ({user.id})**.",
            row=row,
            colour=EmbedColours.UNCLAIMED,
            footer=f"by {ctx.author} ({ctx.author.id})",
        )
        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(embed=embed, view=view)
        embed.description = f"**{pokemon}** has been forcefully unclaimed from you."
        await self.send_notification(embed, user=user, ctx=ctx, view=view)

    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="forcesubmit",
        aliases=("fs",),
        brief="Forcefully submit drawing for a pokémon on someone's behalf.",
        description="AFD Admin-only command to forcefully submit drawing for a pokémon on someone's behalf. This also removes any approved or comment status.",
        usage="<pokémon> [image_url=None]",
    )
    async def forcesubmit(self, ctx: CustomContext, *pokemon_and_url: str):
        pokemon_and_url = list(pokemon_and_url)
        image_url = None
        if len(pokemon_and_url) > 1:
            if URL_REGEX.match(pokemon_and_url[-1]):
                image_url = pokemon_and_url.pop()

        pokemon = await self.get_pokemon(ctx, " ".join(pokemon_and_url))
        if not pokemon:
            return

        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        base_image = self.sheet.get_pokemon_image(row.pokemon)
        if not row.claimed:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not claimed.",
                    row=row,
                    colour=EmbedColours.INVALID,
                )
            )

        #! TEMPORARY
        if image_url is not None:
            try:
                image = await url_to_image(image_url, self.bot.session)
            except ValueError:
                return await ctx.send("That's not an image!")
        else:
            if not (attachments := ctx.message.attachments):
                return await ctx.send_help(ctx.command)

            if not attachments[0].content_type.startswith("image"):
                return await ctx.send("That's not an image!")

            try:
                image = Image.open(io.BytesIO(await attachments[0].read()))
            except PIL.UnidentifiedImageError:
                return await ctx.send("That's not an image!")

        if await self.submit_image_check(ctx, image) is not True:
            return

        conf = cmsg = None
        user = await self.fetch_user(row.user_id)

        embeds = self.dual_image_embed(
            description=f"Are you sure you want to force {'re' if row.image else ''}submit the following drawing for **{pokemon}** on **{user} ({user.id})**'s behalf?",
            before=row.image,
            after=image_url,
            thumbnail=base_image,
        )
        conf, cmsg = await ctx.confirm(
            embed=embeds,
            confirm_label="Force Submit",
        )
        if conf is False:
            return

        self.sheet.submit(pokemon, image_url=image_url)
        await self.sheet.update_row(row.dex)
        embeds = self.dual_image_embed(
            description=f"You have successfully force {'re' if row.image else ''}submitted the following image for **{pokemon}** on **{user} ({user.id})**'s behalf.",
            before=row.image,
            after=image_url,
            thumbnail=base_image,
            color=EmbedColours.UNREVIEWED.value,
            footer="You will be notified when it has been reviewed :)",
        )
        await cmsg.edit(embeds=embeds)

        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(
            embeds=self.dual_image_embed(
                description=f"**{ctx.author} ({ctx.author.id})** has force {'re' if row.image else ''}submitted the following image for **{pokemon}** on **{user} ({user.id})**'s behalf.",
                before=row.image,
                after=image_url,
                thumbnail=base_image,
                color=EmbedColours.UNREVIEWED.value,
            ),
            view=view,
        )

        embeds[
            0
        ].description = f"**{ctx.author} ({ctx.author.id})** has force {'re' if row.image else ''}submitted the following image for **{pokemon}** on your behalf."
        await self.send_notification(embeds, user=user, ctx=ctx, view=view)
        return True

    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="forceunsubmit",
        aliases=("ufs",),
        brief="Forcefully unsubmit a submitted drawing",
        description="AFD Admin-only command to forcefully clear submission of a pokémon.",
    )
    async def forceunsubmit(self, ctx: CustomContext, *, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        user = await self.fetch_user(row.user_id)
        base_image = self.sheet.get_pokemon_image(row.pokemon)
        if not row.image:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not submitted.",
                    colour=EmbedColours.INVALID,
                )
            )

        embeds = self.dual_image_embed(
            description=f"Are you sure you want to force unsubmit **{user} ({user.id})**'s drawing for **{pokemon}**?",
            after=row.image,
            thumbnail=base_image,
        )
        conf, cmsg = await ctx.confirm(
            embed=embeds,
            confirm_label="Force Unsubmit",
        )
        if conf is False:
            return

        self.sheet.submit(pokemon, image_url="")
        await self.sheet.update_row(row.dex)
        embeds = self.dual_image_embed(
            description=f"You have successfully force unsubmitted **{user} ({user.id})**'s drawing for **{pokemon}**.",
            after=row.image,
            thumbnail=base_image,
            color=EmbedColours.INCOMPLETE.value,
        )
        await cmsg.edit(embeds=embeds)

        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(
            embeds=self.dual_image_embed(
                description=f"**{ctx.author} ({ctx.author.id})** has force unsubmitted **{user} ({user.id})**'s drawing for **{pokemon}**.",
                after=row.image,
                thumbnail=base_image,
                color=EmbedColours.INCOMPLETE.value,
            ),
            view=view,
        )

        embeds[
            0
        ].description = f"**{ctx.author} ({ctx.author.id})** has force unsubmitted your drawing for **{pokemon}**."
        await self.send_notification(embeds, user=user, ctx=ctx, view=view)
        return True

    async def approve(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        approved_by = (
            await self.fetch_user(row.approved_by) if row.approved_by else None
        )
        if any((not row.claimed, not row.image)):
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** {'is not claimed' if not row.claimed else 'has not been submitted'}.",
                    colour=EmbedColours.INVALID,
                )
            )
        elif row.approved:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** has already been approved by **{approved_by} ({approved_by.id})**!",
                    colour=EmbedColours.APPROVED,
                )
            )
        conf, cmsg = await ctx.confirm(
            embed=self.confirmation_embed(
                f"""{f'There is a correction pending with comment "{row.comment}" by **{approved_by} ({approved_by.id})**. ' if row.correction_pending else ''}\nAre you sure you want to approve **{pokemon}**?""",
                row=row,
            ),
            confirm_label="Approve",
        )
        if conf is False:
            return

        user = await self.fetch_user(row.user_id)
        row = self.sheet.approve(pokemon, by=ctx.author.id)
        await self.sheet.update_row(row.dex)
        await self.update_credits()
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"**{pokemon}** has been approved! 🎉",
                row=row,
                colour=EmbedColours.APPROVED,
                footer=f"You can undo this using the `unapprove` command.",
            )
        )
        embed = self.confirmation_embed(
            f"**{pokemon}** has been approved! 🎉",
            row=row,
            colour=EmbedColours.APPROVED,
            footer=f"by {ctx.author} ({ctx.author.id})",
        )
        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(embed=embed, view=view)
        await self.send_notification(embed, user=user, ctx=ctx, view=view)
        return True

    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="approve",
        brief="Approve a drawing",
        help="""Used to approve a drawing submission. Clears comment.""",
    )
    async def approve_cmd(self, ctx: CustomContext, *, pokemon: str):
        await self.approve(ctx, pokemon)

    async def unapprove(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        if not row.approved:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** has not been approved.",
                    colour=EmbedColours.INVALID,
                )
            )
        approved_by = await self.fetch_user(row.approved_by)
        conf, cmsg = await ctx.confirm(
            embed=self.confirmation_embed(
                f"Are you sure you want to unapprove **{pokemon}**?",
                row=row,
                footer=f"Approved by {approved_by} ({approved_by.id})",
            ),
            confirm_label="Unapprove",
        )
        if conf is False:
            return

        user = await self.fetch_user(row.user_id)
        row = self.sheet.unapprove(pokemon)
        await self.sheet.update_row(row.dex)
        await self.update_credits()
        await cmsg.edit(
            embed=self.confirmation_embed(
                f"**{pokemon}** has been unapproved.",
                row=row,
                colour=EmbedColours.UNREVIEWED,
            )
        )
        embed = self.confirmation_embed(
            f"**{pokemon}** has been unapproved.",
            row=row,
            colour=EmbedColours.UNREVIEWED,
            footer=f"by {ctx.author} ({ctx.author.id})",
        )
        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(embed=embed, view=view)
        await self.send_notification(embed, user=user, ctx=ctx, view=view)
        return True

    @commands.has_role(AFD_ADMIN_ROLE_ID)
    @afd.command(
        name="unapprove",
        brief="Unapprove an approved drawing",
        help="""Used to unapprove an approved drawing submission.""",
    )
    async def unapprove_cmd(self, ctx: CustomContext, *, pokemon: str):
        await self.unapprove(ctx, pokemon)

    async def comment(
        self, ctx: CustomContext, pokemon: str, comment: Optional[str] = None
    ):
        if not comment:
            return await self.uncomment(ctx, pokemon)

        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        approved_by = (
            await self.fetch_user(row.approved_by) if row.approved_by else None
        )
        if any((not row.claimed, not row.image)):
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** {'is not claimed' if not row.claimed else 'has not been submitted'}.",
                    colour=EmbedColours.INVALID,
                )
            )

        if comment == row.comment:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"No changes found in the comment.",
                    colour=EmbedColours.INVALID,
                )
            )

        if row.correction_pending:
            desc = f"""Are you sure you want to modify the existing comment on **{pokemon}**?:
**From** (by **{approved_by} ({approved_by.id})**)
> {row.comment}
**To**
> {comment}"""
            conf_desc = f"""Comment has been modified on **{pokemon}**:
**From** (by **{approved_by} ({approved_by.id})**)
> {row.comment}
**To** (by **%s**)
> {comment}"""
        elif row.approved:
            desc = f"""**{pokemon}** has already been approved (by **{approved_by} ({approved_by.id})**)! Are you sure you want to unapprove and comment the following?
> {comment}"""
        else:
            desc = f"""Are you sure you want to comment the following on **{pokemon}**?
> {comment}"""
            conf_desc = f"""**%s** commented the following on **{pokemon}**:
> {comment}"""

        conf, cmsg = await ctx.confirm(
            embed=self.confirmation_embed(
                desc,
                row=row,
            ),
            confirm_label="Comment",
        )
        if conf is False:
            return

        user = await self.fetch_user(row.user_id)
        row = self.sheet.comment(pokemon, comment, by=ctx.author.id)
        await self.sheet.update_row(row.dex)

        await cmsg.edit(
            embed=self.confirmation_embed(
                conf_desc % "You",
                row=row,
                colour=EmbedColours.CORRECTION,
            )
        )
        embed = self.confirmation_embed(
            conf_desc % ctx.author,
            row=row,
            colour=EmbedColours.CORRECTION,
        )
        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(embed=embed, view=view)

        embed.set_footer(
            text="To resolve this, simply apply the requested correction(s) and resubmit!"
        )
        await self.send_notification(embed, user=user, ctx=ctx, view=view)
        return True

    async def uncomment(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        approved_by = (
            await self.fetch_user(row.approved_by) if row.approved_by else None
        )
        if not row.correction_pending:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"There is no comment to clear.",
                    colour=EmbedColours.INVALID,
                )
            )

        conf, cmsg = await ctx.confirm(
            embed=self.confirmation_embed(
                f"""Are you sure you want to *clear* the following comment (by **{approved_by} ({approved_by.id})**) on **{pokemon}**?
> {row.comment}""",
                row=row,
            ),
            confirm_label="Clear comment",
        )
        if conf is False:
            return

        user = await self.fetch_user(row.user_id)
        row = self.sheet.comment(pokemon, None, by=None)
        await self.sheet.update_row(row.dex)
        conf_desc = f"""The following comment (by **{approved_by} ({approved_by.id})**) on **{pokemon}** has been cleared:
> {row.comment}"""
        await cmsg.edit(
            embed=self.confirmation_embed(
                conf_desc,
                row=row,
                colour=EmbedColours.UNREVIEWED,
            )
        )
        embed = self.confirmation_embed(
            conf_desc,
            row=row,
            colour=EmbedColours.UNREVIEWED,
        )
        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(embed=embed, view=view)

        await self.send_notification(embed, user=user, ctx=ctx, view=view)
        return True

    # endregion

    # --- Public commands ---
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
        if user:
            return await ctx.invoke(self._list)
        if pokemon:
            return await ctx.invoke(self.view, pokemon=pokemon)

        await self.sheet.update_df()
        view = AfdView(self, ctx=ctx)
        view.message = await ctx.reply(embed=self.embed, view=view)

    async def send_view(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        user = (await self.fetch_user(row.user_id)) if row.claimed else None
        approved_by = (
            (await self.fetch_user(row.approved_by)) if row.approved_by else None
        )

        view = PokemonView(ctx, row, afdcog=self, user=user, approved_by=approved_by)
        await view.set_image_info()
        view.message = await ctx.send(embed=view.embed, view=view)

    @afd.command(
        name="view",
        aliases=("pokemon", "pkm", "d", "dex"),
        brief="See info of a pokémon from the sheet",
        help="""Shows you all the information about a pokemon such as:
    - Claim status
    - User who claimed
    - Status
    - Any comment
    - Submitted drawing if any, etc

and lets you directly perform actions such as:
    - Claiming/Unclaiming
    - Submitting/Editing submission
    - Sending reminder
    - Approving/Unapproving
    - Commenting""",
    )
    async def view(self, ctx: CustomContext, *, pokemon: str):
        await self.send_view(ctx, pokemon)

    def get_stats(self, user: Optional[discord.User] = None) -> Union[Stats, None]:
        if user is not None:
            try:
                df: pd.DataFrame = self.user_grouped.get_group(str(user.id))
            except KeyError:
                return Stats(pd.DataFrame(), self)
        else:
            df: pd.DataFrame = self.df.sort_values(by=PKM_LABEL)
        return Stats(df, self)

    async def send_all_list(
        self, ctx: CustomContext, stats: Stats, *, embed: Bot.Embed
    ):
        total_amount = stats.claimed.amount if stats is not None else 0
        embed.description = f"**Total pokémon**: {total_amount}"

        embed.description += f"\n**Total submitted pokémon**: {stats.submitted.amount}"

        embed.set_footer(
            text=f"Use the `{ctx.clean_prefix}afd view <pokémon>` command to see more info on and interact with an entry"
        )

        categories = [
            stats.correction_pending,
            stats.incomplete,
            stats.unreviewed,
            stats.approved,
        ]
        menu = StatsPageMenu(
            categories, ctx=ctx, original_embed=embed, total_amount=total_amount
        )
        await menu.start()

    @afd.group(
        name="list",
        brief="View the different categories of pokémon entries",
        help="View lists of every category of pokémon of a specific user. To see your own, leave the user argument empty.",
        invoke_without_command=True,
    )
    async def _list(
        self,
        ctx: CustomContext,
        *,
        user: Optional[Union[discord.User, discord.Member]] = None,
    ):
        await self.sheet.update_df()
        user = user or ctx.author
        stats = self.get_stats(user)

        embed = self.bot.Embed()
        embed.set_author(name=f"{user}'s stats", icon_url=user.display_avatar.url)

        await self.send_all_list(ctx, stats, embed=embed)

    @_list.command(
        name="all",
        brief="View all stats, categorized",
        help="View lists of every category of pokémon in a compact form compared to their respective subcommands.",
    )
    async def list_all(self, ctx: CustomContext):
        await self.sheet.update_df()
        stats = self.get_stats()

        embed = self.bot.Embed()
        embed.set_author(name=f"All stats")

        await self.send_all_list(ctx, stats, embed=embed)

    @staticmethod
    def bold_initials_fmt(rows: List[Row]) -> List[str]:
        entries = []
        initials = []
        for row in rows:
            pokemon = row.pokemon
            i, bolded = get_initial(
                pokemon, bold=True
            )  # !NOTE TO SELF: UPDATE get_pkm IF FORMAT CHANGES
            if i not in initials:
                entries.append(bolded)
                initials.append(i)
            else:
                entries.append(pokemon)
        return entries

    @_list.command(
        name="unclaimed",
        aliases=("unc", "available"),
        brief="View pokémon that have not been claimed yet.",
        help="View a list of pokémon that are available to claim.",
    )
    async def list_unclaimed(self, ctx: CustomContext):
        await self.sheet.update_df()
        stats = self.get_stats()
        category = stats.unclaimed
        entries = enumerate_list(self.bold_initials_fmt(category.rows))

        src = ListPageSource(category, entries=entries)
        menu = ListPageMenu(src, ctx=ctx)
        if entries:
            menu.add_selects(
                ListSelectMenu(menu),
                ActionSelectMenu(
                    menu,
                    # !NOTE TO SELF: THIS get_pkm IS HACKY AS HELL AND WILL BREAK IF A POKEMON HAS * IN ITS NAME OR FORMAT CHANGES
                    get_pkm=lambda e: re.match("\d+\\\. (.+)", e)
                    .groups()[0]
                    .replace("*", ""),
                    action_func=self.claim,
                    placeholder="Claim a pokémon",
                ),
            )
            random_btn = discord.ui.Button(
                label="Random", style=discord.ButtonStyle.blurple
            )

            async def callback(interaction: discord.Interaction):
                await interaction.response.defer()
                await self.random(ctx)

            random_btn.callback = callback
            menu.add_item(random_btn)

        await menu.start()

    async def pokemon_user_fmt(self, rows: List[Row]):
        entries_dict = defaultdict(list)
        for row in rows:
            entries_dict[await self.fetch_user(row.user_id)].append(row.pokemon)

        entries = []
        for user, pokemon in sorted(entries_dict.items(), key=lambda e: str(e[0])):
            for pkm in pokemon:
                entries.append(
                    f"**{pkm}** - `{user}`"
                )  # !NOTE TO SELF: UPDATE get_pkm IF FORMAT CHANGES

        return entries

    @_list.command(
        name="correction",
        aliases=("cor", "correction_pending"),
        brief="View pokémon that have a comment left by an admin.",
        help="View a list of pokémon that have a comment left by an admin, and hence pending correction of some sort.",
    )
    async def list_correction(self, ctx: CustomContext):
        await self.sheet.update_df()
        stats = self.get_stats()
        category = stats.correction_pending
        entries = enumerate_list(await self.pokemon_user_fmt(category.rows))

        src = ListPageSource(category, entries=entries)
        menu = ListPageMenu(src, ctx=ctx)
        if entries:
            menu.add_selects(
                ActionSelectMenu(
                    menu,
                    # !NOTE TO SELF: THIS get_pkm IS HACKY AS HELL AND WILL BREAK IF THE FORMAT CHANGES
                    get_pkm=lambda e: re.match("\d+\\\. \*\*(.+?)\*\* - ", e).groups()[
                        0
                    ],
                    action_func=self.send_view,
                    placeholder="View an entry",
                )
            )
            if self.is_admin(ctx.author):
                menu.add_item(RemindAllButton(self, category.rows, ctx=ctx))
        await menu.start()

    async def per_user_fmt(
        self,
        rows: List[Row],
        *,
        joiner: Optional[str] = ", ",
        enumerate: Optional[bool] = False,
    ) -> List[str]:
        users: DefaultDict[discord.User, List[str]] = defaultdict(list)
        for row in rows:
            users[await self.fetch_user(row.user_id)].append(f"`{row.pokemon}`")

        entries = []
        for user, pokemon in users.items():
            pokemon = enumerate_list(pokemon) if enumerate else pokemon
            pkm = joiner.join(pokemon)
            entry = f"""- **{str(user)}** ({user.id}) [`{len(pokemon)}`]
>    {pkm}"""
            entries.append(entry)
        entries.sort()

        return entries

    @_list.command(
        name="incomplete",
        aliases=("inc",),
        brief="View pokémon that have been claimed but not yet submitted.",
        help="View a list of pokémon that have been claimed but no submission yet.",
    )
    async def list_incomplete(self, ctx: CustomContext):
        await self.sheet.update_df()
        stats = self.get_stats()
        category = stats.incomplete
        entries = await self.per_user_fmt(category.rows)

        src = ListPageSource(
            category, entries=entries, dynamic_pages=True, max_per_page=5
        )
        menu = ListPageMenu(src, ctx=ctx)
        if entries and self.is_admin(ctx.author):
            menu.add_item(RemindAllButton(self, category.rows, ctx=ctx))
        await menu.start()

    @_list.command(
        name="unreviewed",
        aliases=("unr", "submitted"),
        brief="View submitted pokémon awaiting review",
        help="View a list of pokémon that have been submitted but no review (comment/approval) yet.",
    )
    async def list_unreviewed(self, ctx: CustomContext):
        await self.sheet.update_df()
        stats = self.get_stats()
        category = stats.unreviewed
        entries = enumerate_list(await self.pokemon_user_fmt(category.rows))

        src = ListPageSource(category, entries=entries)
        menu = ListPageMenu(src, ctx=ctx)
        if entries:
            menu.add_selects(
                ActionSelectMenu(
                    menu,
                    # !NOTE TO SELF: THIS get_pkm IS HACKY AS HELL AND WILL BREAK IF THE FORMAT CHANGES
                    get_pkm=lambda e: re.match("\d+\\\. \*\*(.+?)\*\* - ", e).groups()[
                        0
                    ],
                    action_func=self.send_view,
                    placeholder="View an entry",
                )
            )
        await menu.start()

    @_list.command(
        name="approved",
        aliases=("app",),
        brief="View approved pokémon",
        help="View a list of pokémon that have been submitted and approved.",
    )
    async def list_approved(self, ctx: CustomContext):
        await self.sheet.update_df()
        stats = self.get_stats()
        category = stats.approved
        entries = await self.per_user_fmt(category.rows)

        src = ListPageSource(
            category, entries=entries, dynamic_pages=True, max_per_page=3
        )
        menu = ListPageMenu(src, ctx=ctx)
        await menu.start()

    async def claim(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)

        max_msg = f"You already have the max number ({self.sheet.CLAIM_MAX}) of pokémon claimed"
        if not row.claimed:
            p = ""
            if self.sheet.can_claim(ctx.author) is False:
                p = max_msg
                if not self.is_admin(ctx.author):
                    return await ctx.reply(
                        embed=self.confirmation_embed(
                            f"{p}!",
                            colour=EmbedColours.INVALID,
                        )
                    )
                else:
                    p += ", "

            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    f"{p}Are you sure you want to claim **{pokemon}**?", row=row
                ),
            )
            if conf is False:
                return

        async def decide_msg(row: Row):
            if row.claimed:
                return f"**{pokemon}** is already claimed by **{'you' if row.user_id == ctx.author.id else await self.fetch_user(row.user_id)}**!"
            if not self.sheet.can_claim(ctx.author):
                return f"{max_msg}!"

        check = lambda row: row.claimed or not self.sheet.can_claim(ctx.author)
        decide_footer = (
            lambda row: "You can unclaim it using the `unclaim` command."
            if row.user_id == ctx.author.id
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

        row = self.sheet.claim(ctx.author, pokemon)
        await self.sheet.update_row(row.dex)
        embed = self.confirmation_embed(
            f"You have successfully claimed **{pokemon}**, have fun! :D",
            row=row,
            colour=EmbedColours.INCOMPLETE,
            footer=f"You can undo this using the `unclaim` command.",
        )
        await cmsg.edit(embed=embed)

        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(
            embed=self.confirmation_embed(
                f"**{ctx.author} ({ctx.author.id})** has claimed **{pokemon}**.",
                row=row,
                colour=EmbedColours.INCOMPLETE,
            ),
            view=view,
        )

        await self.send_notification(embed, user=ctx.author, ctx=ctx, view=view)
        return True

    @afd.command(
        name="claim",
        brief="Claim a pokémon to draw",
        description=f"Claim a pokémon to draw. Use the `afd` to know the claim limit at a time. Pokemon alt names are supported!",
        help=f"""When this command is ran, first the sheet data will be fetched. Then:
1. A pokemon, with the normalized and deaccented version of the provided name *including alt names*, will be searched for. If not found, it will return invalid.
2. That pokemon's availability on the sheet will be checked:
{INDENT}**i. If it's *not* claimed yet:**
{INDENT}{INDENT}- If you already have max claims, it will not let you claim. Does not apply to admins.
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
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        if row.user_id == ctx.author.id:
            conf, cmsg = await ctx.confirm(
                embed=self.confirmation_embed(
                    f"Are you sure you want to unclaim **{pokemon}**?\
                        {' You have already submitted a drawing which will be removed.' if row.image else ''}",
                    row=row,
                ),
                confirm_label="Unclaim",
            )
            if conf is False:
                return

        check = lambda row: (not row.claimed) or row.user_id != ctx.author.id

        async def decide_msg(row):
            return (
                f"**{pokemon}** is not claimed."
                if not row.claimed
                else f"**{pokemon}** is claimed by **{await self.fetch_user(row.user_id)}**!"
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

        row = self.sheet.unclaim(pokemon)
        await self.sheet.update_row(row.dex)
        embed = self.confirmation_embed(
            f"You have successfully unclaimed **{pokemon}**.",
            row=row,
            colour=EmbedColours.UNCLAIMED,
        )
        await cmsg.edit(embed=embed)

        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(
            embed=self.confirmation_embed(
                f"**{ctx.author} ({ctx.author.id})** has unclaimed **{pokemon}**.",
                row=row,
                colour=EmbedColours.UNCLAIMED,
            ),
            view=view,
        )

        await self.send_notification(embed, user=ctx.author, ctx=ctx, view=view)
        return True

    @afd.command(
        name="unclaim",
        aliases=("unc",),
        brief="Unclaim a pokémon",
        description=f"Unclaim a pokémon claimed by you.",
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

    def dual_image_embed(
        self,
        description: str,
        *,
        before: Optional[Union[str, None]] = None,
        after: str,
        thumbnail: str,
        color: Optional[int] = None,
        footer: Optional[str] = None,
    ):
        embeds = []
        embed = self.bot.Embed(description=description, color=color)
        embeds.append(embed)
        embed.set_thumbnail(url=thumbnail)

        if before:
            embed.add_field(name="Before", value="")
            embed.set_image(url=before)

            embed2 = self.bot.Embed(color=color)
            embed2.add_field(name="After", value="")
            embed2.set_image(url=after)
            embed2.set_footer(text=footer)
            embeds.append(embed2)
        else:
            embed.set_image(url=after)
            embed.set_footer(text=footer)

        return embeds

    async def submit_image_check(self, ctx: CustomContext, image: Image):
        if image.format != "PNG":
            return await ctx.send(
                "Image must have a transparent background (of PNG format)"
            )

        if [
            colour
            for n, colour in sorted(
                image.getcolors(image.size[0] * image.size[1]),
                key=lambda c: c[0],
                reverse=True,
            )
        ][0][-1] != 0:
            conf, msg = await ctx.confirm(
                "The image you have provided does not have a majority of transparent pixels."
                " This *could* mean that it has a non-transparent background, please double check to make sure!"
                "\n\nIf it does have a transparent background, please proceed using the confirm button.",
                edit_after=None,
            )
            if conf is False:
                return await ctx.send("Aborted.")

        if image.height != 475 or image.width != 475:
            return await ctx.reply(
                f"Image dimensions must be `475x475` but yours is `{image.width}x{image.height}`."
                f" Please resize it first using `{ctx.clean_prefix}afd resize`",
            )

        return True

    @afd.command(
        name="resize",
        brief="Resize a drawing to required specifications",
        help="Alias of the `resize` command with pre-defined specifications required for the AFD event. Equivalent to `resize --h 475 --w 475 --fit yes --center yes`",
    )
    async def _resize(self, ctx: CustomContext, *, image_url: Optional[str] = None):
        ctx.message.content = (
            f"{ctx.prefix}resize --h 475 --w 475 --fit yes --center yes"
        )
        if image_url:
            ctx.message.content += f" --url {image_url}"

        return await ctx.bot.process_commands(ctx.message)

    async def submit(self, ctx: CustomContext, pokemon: str, *, image_url: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        if not URL_REGEX.match(image_url):
            return await ctx.send(f"`{image_url}` is not a valid URL!")

        try:
            image = await url_to_image(image_url, self.bot.session)
        except ValueError:
            return await ctx.send("That's not an image!")

        if await self.submit_image_check(ctx, image) is not True:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        base_image = self.sheet.get_pokemon_image(row.pokemon)
        if not row.claimed:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not claimed.",
                    colour=EmbedColours.INVALID,
                )
            )
        if not (row.user_id == ctx.author.id):
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not claimed by you!",
                    colour=EmbedColours.INVALID,
                )
            )

        embeds = self.dual_image_embed(
            description=f"Are you sure you want to {'re' if row.image else ''}submit the following drawing for **{pokemon}**?",
            before=row.image,
            after=image_url,
            thumbnail=base_image,
        )
        conf, cmsg = await ctx.confirm(
            embed=embeds,
            confirm_label="Submit",
        )
        if conf is False:
            return

        self.sheet.submit(pokemon, image_url=image_url)
        await self.sheet.update_row(row.dex)
        embeds = self.dual_image_embed(
            description=f"You have successfully {'re' if row.image else ''}submitted the following image for **{pokemon}**.",
            before=row.image,
            after=image_url,
            thumbnail=base_image,
            color=EmbedColours.UNREVIEWED.value,
            footer="You will be notified when it has been reviewed :)",
        )
        await cmsg.edit(embeds=embeds)

        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(
            embeds=self.dual_image_embed(
                description=f"**{ctx.author} ({ctx.author.id})** has {'re' if row.image else ''}submitted the following image for **{pokemon}**.",
                before=row.image,
                after=image_url,
                thumbnail=base_image,
                color=EmbedColours.UNREVIEWED.value,
            ),
            view=view,
        )

        await self.send_notification(embeds, user=ctx.author, ctx=ctx, view=view)
        return True

    @afd.command(
        name="submit",
        brief="Submit a drawing.",
        help="Submit a drawing for a pokémon. This also removes any approved or comment status. WIP, TODO: VALIDATE URL",
        usage="<pokémon> [image_url=None]",
    )
    async def submit_cmd(self, ctx: CustomContext, *pokemon_and_url: str):
        pokemon_and_url = list(pokemon_and_url)
        image_url = None
        if len(pokemon_and_url) > 1:
            if URL_REGEX.match(pokemon_and_url[-1]):
                image_url = pokemon_and_url.pop()

        pokemon = " ".join(pokemon_and_url)

        #! TEMPORARY
        if image_url is None:
            if not (attachments := ctx.message.attachments):
                return await ctx.send_help(ctx.command)

            image_url = attachments[0].url

        await self.submit(ctx, pokemon, image_url=image_url)

    async def unsubmit(self, ctx: CustomContext, pokemon: str):
        pokemon = await self.get_pokemon(ctx, pokemon)
        if not pokemon:
            return

        conf = cmsg = None
        await self.sheet.update_df()
        row = self.sheet.get_pokemon_row(pokemon)
        base_image = self.sheet.get_pokemon_image(row.pokemon)
        if not row.image:
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not submitted.",
                    colour=EmbedColours.INVALID,
                )
            )
        if not (row.user_id == ctx.author.id):
            return await ctx.reply(
                embed=self.confirmation_embed(
                    f"**{pokemon}** is not submitted by you!",
                    colour=EmbedColours.INVALID,
                )
            )

        embeds = self.dual_image_embed(
            description=f"Are you sure you want to unsubmit the following drawing for **{pokemon}**?",
            after=row.image,
            thumbnail=base_image,
        )
        conf, cmsg = await ctx.confirm(
            embed=embeds,
            confirm_label="Unsubmit",
        )
        if conf is False:
            return

        self.sheet.submit(pokemon, image_url="")
        await self.sheet.update_row(row.dex)
        embeds = self.dual_image_embed(
            description=f"You have successfully unsubmitted the following image for **{pokemon}**",
            after=row.image,
            thumbnail=base_image,
            color=EmbedColours.INCOMPLETE.value,
        )
        await cmsg.edit(embeds=embeds)

        view = UrlView({"Go to message": cmsg.jump_url})
        await self.log_channel.send(
            embeds=self.dual_image_embed(
                description=f"**{ctx.author} ({ctx.author.id})** has unsubmitted the following image for **{pokemon}**.",
                after=row.image,
                thumbnail=base_image,
                color=EmbedColours.INCOMPLETE.value,
            ),
            view=view,
        )

        await self.send_notification(embeds, user=ctx.author, ctx=ctx, view=view)
        return True

    @afd.command(
        name="unsubmit",
        brief="Clear submitted drawing of a pokémon.",
        help="Clear submitted drawing of a pokémon. This also removes any approved or comment status.",
    )
    async def unsubmit_cmd(self, ctx: CustomContext, pokemon: str):
        await self.unsubmit(ctx, pokemon)

    DURATION = 3
    CHOICES_LEN = 10
    MESSAGES = [
        "{winner} bullied {loser} out of the contest :(",
        "{loser} got bored and left to make tea...",
        "{winner} caught {loser} with a Master Ball, {winner} wins this round!",
        "{winner} took inspiration from Will Smith and smacked {loser} out of the contest...",
        "{loser} forgot the time and didn't show up...",
        "{loser} lost due to [Intentional Game Design].",
        "{loser} stubbed its toe :( {winner} wins this round!",
        "{loser} is allergic to social interaction...",
        "{loser} had a jousting competition with {winner} and lost.",
        "{loser} was just a figment of your imagination...",
        "{loser} forgot to put on sunscreen and burnt up...",
        "{loser} was just a figment of your imagination...",
        "{loser} had an exam and could not attend...",
        "{loser} drank expired milk...",
        "{loser} tripped over a rock...",
    ]

    async def random(
        self,
        ctx: CustomContext,
        pokemon_options: Optional[List[str]] = None,
        *,
        skip: Optional[bool] = False,
        include_claimed: Optional[bool] = False,
    ):
        await self.sheet.update_df()

        errors = {}
        category_text = ""
        if pokemon_options is None:
            if include_claimed:
                stats = self.get_stats(ctx.author)
                category = stats.incomplete
                category_text = "claimed "
            else:
                stats = self.get_stats()
                category = stats.unclaimed
                category_text = "unclaimed "
            pokemon = category.pokemon
        else:
            pokemon = []
            for name in pokemon_options:
                pkm = self.pokemon_by_name(name)
                if pkm is None:
                    errors[name] = "Invalid pokémon"
                    continue
                elif isinstance(pkm, tuple):
                    pkm, ac = pkm
                    errors[name] = f"Invalid pokémon, autocorrected to `{ac}`"

                row = self.sheet.get_pokemon_row(pkm)
                if row.claimed:
                    if include_claimed and row.user_id == ctx.author.id:
                        pass
                    else:
                        errors[
                            pkm
                        ] = f"Already claimed{' by you' if row.user_id == ctx.author.id else ''}"
                        continue

                pokemon.append(pkm)

            if errors:
                conf_embed = ctx.bot.Embed()
                conf_embed.add_field(
                    name="Could not include",
                    value="\n".join([f"- `{p}` - {m}" for p, m in errors.items()]),
                )
                if len(pokemon) == 0:
                    return await ctx.reply(embed=conf_embed)

                conf_embed.add_field(
                    name="Proceed with the following?",
                    value="\n".join([f"- `{p}`" for p in pokemon]),
                )
                conf, _ = await ctx.confirm(embed=conf_embed, edit_after="")
                if conf is False:
                    return

                return await self.random(
                    ctx, pokemon, skip=skip, include_claimed=include_claimed
                )

        if len(pokemon) == 0:
            return await ctx.send(
                f"There are no {category_text}pokémon to choose from!"
            )
        elif len(pokemon) == 1:
            choices = pokemon
        elif skip is True:
            choices = [random.choice(pokemon)]
        else:
            choices = random.sample(pokemon, k=min(len(pokemon), self.CHOICES_LEN))

        cont = choices.copy()
        assert len(choices) > 0
        if skip is True:
            choice = choices[0]

        elif len(choices) > 1:
            desc = (
                lambda: f"__**Contestants ({len(cont)}/{len(choices)})**__:\n{NL.join(enumerate_list(choices))}"
            )
            text = (
                f"{len(choices)} out of {len(pokemon)} {category_text}pokémon were randomly chosen as contestants for this randomizer!"
                if pokemon_options is None
                else f"{len(pokemon)} pokémon are participating in this randomizer contest!"
            )
            embed = self.bot.Embed(
                title=f"{text} Who will win? 👀",
                description=desc(),
            )
            skip_view = SkipView(cont, ctx=ctx)
            skip_view.message = msg = await ctx.reply(embed=embed, view=skip_view)
            await asyncio.sleep(self.DURATION)

            rnd = 1
            while len(cont) > 1:
                winner, loser = random.sample(cont, 2)
                choices[choices.index(loser)] = f"~~{loser}~~ `❌`"
                cont.remove(loser)
                embed.description = desc()

                message = random.choice(self.MESSAGES).format_map(
                    {"winner": f"**{winner}**", "loser": f"**{loser}**"}
                )
                embed.add_field(name=f"Round {rnd}", value=message)

                rnd += 1
                await msg.edit(embed=embed)
                await asyncio.sleep(self.DURATION)

            choice = cont[0]

        else:
            choice = choices[0]
            embed = self.bot.Embed(
                title=f"1 pokémon was randomly chosen out of.. 1 {category_text}pokémon..",
                description=f"**{choice}** is the only one who showed up... 🦗",
            )
            msg = await ctx.reply(embed=embed)
            await asyncio.sleep(self.DURATION)

        embed = self.bot.Embed(title=f"{choice} has won the randomizer contest!")
        embed.set_image(url=self.sheet.get_pokemon_image(choice))

        view = RandomView(self, ctx, choice, pokemon_options)
        view.message = await ctx.reply(embed=embed, view=view)

    @afd.group(
        name="random",
        aliases=("rp", "rand"),
        brief="Pick a random unclaimed pokémon",
        description="Randomly rolls an unclaimed pokémon to help you decide what to draw. Has a little contest to make it more fun, suggested by @metspek (243763234685976577) :D",
        help=f"""## Flags
- `--name/n <pokemon>` - {RandomFlagDescriptions._name.value}
- `--skip/sk <y/n>` - {RandomFlagDescriptions.skip.value}
- `--claimed <y/n>` - {RandomFlagDescriptions.claimed.value}
## Examples
- `afd random` - Randomly rolls a pokémon from all unclaimed pokémon.
- `afd random --claimed y` - Randomly rolls a pokémon from all of your claimed pokémon.
- `afd random --skip y` - Randomly rolls a pokémon from all unclaimed pokémon, skipping straight to the winner.
- `afd random --n ralts --n kirlia --n gardevoir --n gallade` - Randomly rolls a pokémon from the 4 specified pokémon.
- `afd random --n ralts --n kirlia --n gardevoir --n gallade --claimed y` - Randomly rolls a pokémon from the 4 specified pokémon, even if one of them is claimed by you.""",
        invoke_without_command=True,
    )
    async def random_cmd(self, ctx: CustomContext, *, flags: RandomFlags):
        await self.random(
            ctx, flags.name, skip=flags.skip, include_claimed=flags.claimed
        )


async def setup(bot):
    await bot.add_cog(Afd(bot))
