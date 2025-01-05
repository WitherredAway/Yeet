from __future__ import annotations

import contextlib
from io import StringIO
import logging
import re
import textwrap
from typing import IO, TYPE_CHECKING, List, Optional

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
import pandas as pd

from cogs.Poketwo.utils.constants import POKEMON_GIST_URL
from cogs.Poketwo.utils.models import DataManager
from cogs.Poketwo.utils.utils import get_data_from
from helpers.utils import enumerate_list, force_log_errors, reload_modules
from helpers.context import CustomContext
from helpers.timer import Timer
from .ext.poketwo_chances import PoketwoChances

if TYPE_CHECKING:
    from main import Bot


logger = logging.getLogger(__name__)


class Poketwo(PoketwoChances):
    """Utility commands for the Pokétwo bot"""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def initialize_data(self, update_stream: Optional[IO[str]] = None):
        self.pokemon_gist = await self.bot.wgists_client.get_gist(POKEMON_GIST_URL)
        if update_stream is None:
            content = self.pokemon_gist.files[0].content
            stream = StringIO(content)
        else:
            content = update_stream.read()
            stream = StringIO(content)

        csv_data = get_data_from(stream)
        self.data = DataManager(csv_data)

        if update_stream is not None:
            has_changed = self.pokemon_gist.files[0].content != content
            if has_changed:
                self.pokemon_gist.files[0].content = content
                await self.pokemon_gist.edit()

    hint_pattern = re.compile(r"The pokémon is (?P<hint>.+)\.")
    ids_pattern = re.compile(r"^\**`?\s*(\d+)`?\**\b", re.MULTILINE)

    display_emoji = "🫒"

    @property
    def pk(self) -> pd.DataFrame:
        return self.data.df_catchable

    @property
    def pkm_list(self) -> List[str]:
        return list(self.pk["name.en"])

    async def cog_load(self):
        with Timer(logger=logger, end_message="Pokétwo data loaded in {end_time}"):
            await self.initialize_data()

    @force_log_errors
    async def cog_unload(self):
        reload_modules("cogs/Poketwo", skip=__name__)

    @commands.group(
        name="poketwo-data",
        aliases=("p2data",),
        brief="See info about the Pokétwo data currently loaded on the bot",
        invoke_without_command=True,
    )
    async def data_group(self, ctx: CustomContext) -> str:
        embed = self.bot.Embed(title="Local Pokétwo Data Information")
        embed.add_field(
            name="Total Pokémon", value=str(len(self.data.pokemon.values()))
        )
        embed.add_field(name="Enabled Pokémon", value=str(len(self.data.all_pokemon())))

        updated_timestamp = discord.utils.format_dt(self.pokemon_gist.updated_at, "F")
        updated_relative_timestamp = discord.utils.format_dt(
            self.pokemon_gist.updated_at, "R"
        )
        embed.add_field(
            name="Data Last Updated At",
            value=f"{updated_timestamp} ({updated_relative_timestamp})",
        )

        return await ctx.send(embed=embed)

    @commands.is_owner()
    @data_group.command(
        name="update",
        brief="Update the pokemon.csv gist containing the Pokétwo data using provided csv data url.",
    )
    async def update_data(self, ctx: CustomContext, *, csv_data_url: str):
        async with ctx.typing():
            old_pokemon = set(self.data.pokemon.values())
            try:
                response = await self.bot.session.get(csv_data_url)
            except aiohttp.InvalidURL:
                return await ctx.send("Invalid URL provided.")

            content = await response.text()
            try:
                await self.initialize_data(StringIO(content))
            except Exception as e:
                return await ctx.send(
                    f"Invalid data provided. Please make sure that it is a pokemon.csv file from Pokétwo."
                )
            else:
                new_pokemon = set(self.data.pokemon.values())
                has_changed = old_pokemon != new_pokemon

            if has_changed is True:
                old_pokemon_count = len(old_pokemon)
                new_pokemon_count = len(new_pokemon)

                message = f"""
                    Successfully updated the data! Total Pokémon `{old_pokemon_count}` -> `{new_pokemon_count}`!"""
                additions = [s for s in new_pokemon if s not in old_pokemon]
                removals = [s for s in old_pokemon if s not in new_pokemon]
                if additions:
                    message += f"""
                    ### Additions (`{len(additions)}`)
                    {", ".join([f"{s.name} (`{s.id}`)" for s in additions])}
                    """
                if removals:
                    message += f"""
                    ### Removals (`{len(removals)}`)
                    {", ".join([f"{s.name} (`{s.id}`)" for s in removals])}
                    """
            else:
                message = "No changes found!"

            await ctx.send(textwrap.dedent(message))

    @commands.hybrid_command(
        name="extract-ids",
        aliases=("ids", "extractids"),
        brief="Extract Pokémon IDs from Pokétwo embeds",
        help="Extract Pokémon IDs from Pokétwo embeds like marketplace, inventory, etc by providing message link, ID or by replying to the message.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def extract_ids(
        self, ctx: CustomContext, msg_link: Optional[str] = None
    ):
        with contextlib.suppress(discord.HTTPException):
            msg_link = await commands.MessageConverter().convert(ctx, msg_link)

        msg_link = msg_link or (
            (ref.resolved or await ctx.channel.fetch_message(ref.message_id))
            if (ref := ctx.message.reference)
            else None
        )
        if msg_link is not None:
            content = msg_link.embeds[0].description
        else:
            return await ctx.send_help(ctx.command)

        ids = self.ids_pattern.findall(content)
        await ctx.send(" ".join(ids) or "No IDs found.")

    @commands.hybrid_command(
        name="resolve-id",
        aliases=("resolveid",),
        brief="Get the timestamp associated with a Pokémon ID",
        help="Get the timestamp associated with a Pokémon ID",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def resolve_id(self, ctx: CustomContext, pokemon_id: str):
        try:
            if len(pokemon_id) < 8:
                raise ValueError

            b = bytes.fromhex(pokemon_id)
            timestamp = int.from_bytes(b[:4])
        except ValueError:
            content = f"`{pokemon_id}` is not a valid Pokémon ID!"
        else:
            content = f"<t:{timestamp}:F> (<t:{timestamp}:R>)"

        await ctx.reply(content)

    def solve_hint(self, text: str, *, limit: Optional[int] = 10) -> List[str] | None:
        match = self.hint_pattern.match(text)

        official_hint = match is not None

        hint = match.group("hint") if official_hint else text
        hint = re.sub(r"\\?_", ".", hint)
        pattern = re.compile(hint, re.IGNORECASE)

        if official_hint:
            hint = f"^{hint}$"
            method = pattern.match
        else:
            hint = text
            method = pattern.search

        matches = []
        for pkm in self.pkm_list:
            if match := method(pkm):
                matches.append((match.start() / len(pkm), pkm))
        matches.sort(key=lambda m: m[0])

        return [m[1] for m in matches][:limit]

    @commands.hybrid_command(
        name="solve-hint",
        aliases=("solvehint", "solve"),
        brief="Solve the hint sent by Pokétwo for a Pokémon spawn",
        help=(
            "Solve the hint sent by Pokétwo for a Pokémon spawn. Pass in the message/hint into this command."
        ),
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def solve_hint_command(self, ctx: CustomContext, *, text: str):
        pokemon = self.solve_hint(text)
        if not pokemon:
            return await ctx.send(
                "Could not solve that hint. Please make sure it's in the same format as posted by Pokétwo."
            )

        if len(pokemon) > 1:
            pokemon = enumerate_list(pokemon)

        return await ctx.send("\n".join(pokemon), reference=ctx.message)


async def setup(bot):
    await bot.add_cog(Poketwo(bot))
