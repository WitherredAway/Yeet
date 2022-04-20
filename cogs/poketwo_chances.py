import asyncio
import os
import typing
from typing import Counter, Union, Optional

import discord
from discord.ext import commands, tasks
import numpy as np
import pandas as pd

from cogs.utils.paste import paste_to_bin
from constants import NEW_LINE


class PoketwoChances(commands.Cog):
    """Commands related to the poketwo bot."""

    def __init__(self, bot):
        self.bot = bot
        self.pokemon_csv = (
            "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"
        )

    display_emoji = "🔣"

    async def format_msg(
        self,
        title: str,
        pokemon_dataframe: pd.DataFrame,
        *,
        list_pokemon: bool = True,
        pokemon_out_of: bool = True,
    ) -> str:
        pkm_df = pokemon_dataframe
        total_abundance = round(pkm_df["abundance"].sum())

        pokemon = []
        for pkm_idx, pkm_row in pkm_df.iterrows():
            pkm_per_cent = round(
                pkm_row["abundance"] / self.possible_abundance * 100, 4
            )
            pkm_out_of = round(1 / pkm_per_cent * 100)
            line = f"> **{pkm_row['name.en']}** - {pkm_per_cent}%"
            pokemon.append((f"{line} (1/{pkm_out_of})" if pokemon_out_of else line))

        per_cent = round(total_abundance / self.possible_abundance * 100, 4)
        out_of = round(1 / per_cent * 100)
        pokemon.sort()
        all_pokemon = (
            (("\n".join(pokemon)) if list_pokemon else "")
            if len(pokemon) < 30
            else f"> All pokémon: {await paste_to_bin(NEW_LINE.join(pokemon), 'md')}"
        )
        result = f"__**{title}**__ (Includes all catchable forms)\n{all_pokemon}\n**Total pokemon**: {len(pokemon)}\n**Total chance**: {per_cent}% (1/{out_of})"

        return result

    @commands.group(
        aliases=("chances",),
        help="See the chances of pokémon or a rarity.",
    )
    async def chance(self, ctx):
        self.pk = pd.read_csv(self.pokemon_csv)
        self.possible_abundance = round(
            (self.pk["abundance"][self.pk["catchable"] > 0]).sum()
        )

    @chance.command(
        name="rarity",
        help="See the chances of a rarity and the pokémon that belong to that rarity.",
    )
    async def _rarity(self, ctx, rarity):
        options = ["Mythical", "Legendary", "Ultra_beast"]
        for option in options:
            if rarity.lower() in option.lower():
                rarity = option.lower()
                break
        else:
            return await ctx.send(
                f'Invalid rarity provided. Valid rarities: {", ".join(options)}.'
            )

        pkm_df = self.pk.loc[(self.pk["catchable"] > 0) & (self.pk[rarity] == 1)]

        async with ctx.channel.typing():
            result = await self.format_msg(
                rarity.capitalize(), pkm_df, pokemon_out_of=False
            )
        await ctx.send(result)

    @chance.command(
        name="form",
        help="See the chances of a form and the individual pokémon. Options: Alolan, Galarian.",
    )
    async def _form(self, ctx, form):
        options = ["Alolans", "Galarians"]
        for option in options:
            if form.lower() in option.lower():
                form = option.lower()[:5]
                break
        else:
            return await ctx.send(
                f'Invalid form provided. Options: {", ".join(options)}'
            )

        pkm_df = self.pk.loc[
            (self.pk["catchable"] > 0) & (self.pk["slug"].str.endswith(form))
        ]

        async with ctx.channel.typing():
            result = await self.format_msg(f"{form.capitalize()}-form", pkm_df)
        await ctx.send(result)

    @chance.command(
        name="region",
        aliases=("gen",),
        brief="See the chances of the pokémon from a region.",
        help="See the chances of the pokémon from a region. Options: Kanto/1, Johto/2, Hoenn/3, Sinnoh/4, Unova/5, Kalos/6, Alola/7, Galar/8.",
    )
    async def _region(self, ctx, region: Union[int, str]):
        options = [
            "Kanto",
            "Johto",
            "Hoenn",
            "Sinnoh",
            "Unova",
            "Kalos",
            "Alola",
            "Galar",
        ]
        if isinstance(region, str):
            region = region.lower()

        elif all((isinstance(region, int), region < 9)):
            region = options[region - 1].lower()

        pkm_df = self.pk.loc[(self.pk["catchable"] > 0) & (self.pk["region"] == region)]
        if len(pkm_df) == 0:
            return await ctx.send(
                f'Invalid region provided. Options: {", ".join(options)}'
            )

        async with ctx.channel.typing():
            result = await self.format_msg(
                f"{region.capitalize()} region", pkm_df, list_pokemon=True
            )
        await ctx.send(result)

    @chance.command(
        name="pokemon",
        aliases=("poke", "pkm"),
        help="See the chances of a specific pokémon.",
    )
    async def _pokemon(self, ctx, *, pokemon: str):
        pokemon = pokemon.lower()

        pkm_df = self.pk.loc[
            (self.pk["catchable"] > 0)
            & (
                (self.pk["slug"].str.lower() == pokemon)
                | (self.pk["name.en"].str.lower() == pokemon)
            )
        ]
        if len(pkm_df) == 0:
            return await ctx.send("Invalid pokémon provided.")

        async with ctx.channel.typing():
            result = await self.format_msg(
                ", ".join([pkm_row["name.en"] for _, pkm_row in pkm_df.iterrows()]),
                pkm_df,
                list_pokemon=False,
            )
        await ctx.send(result)

    @chance.command(
        name="type",
        aliases=("types", "ty", "t"),
        brief="See the chances of pokémon with certain type(s)",
        help="See the chances of pokémon with certain type(s). Types: Normal, Fire, Water, Grass, Flying, Fighting, Poison, Electric, Ground, Rock, Psychic, Ice, Bug, Ghost, Steel, Dragon, Dark and Fairy.",
    )
    async def _type(self, ctx, type_1: str, type_2: str = None):
        type_1 = type_1.capitalize()
        if not type_2:
            msg = type_1
            pkm_df = self.pk.loc[
                (self.pk["type.0"] == type_1) | (self.pk["type.1"] == type_1)
            ]
        else:
            msg = " & ".join([type_1, type_2])
            type_2 = type_2.capitalize()
            pkm_df = self.pk.loc[
                ((self.pk["type.0"] == type_1) & (self.pk["type.1"] == type_2))
                | ((self.pk["type.0"] == type_2) & (self.pk["type.1"] == type_1))
            ]

        if len(pkm_df) == 0:
            return await ctx.send(f"Invalid type(s) provided `{type_1}`, `{type_2}`.")
        pkm_df = pkm_df[:][pkm_df["catchable"] > 0]

        async with ctx.channel.typing():
            result = await self.format_msg(
                f"{msg} Type(s)",
                pkm_df,
                list_pokemon=True,
            )
        await ctx.send(result)


async def setup(bot):
    await bot.add_cog(PoketwoChances(bot))
