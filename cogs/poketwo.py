import discord
import asyncio
import wikipedia
import random
import pandas as pd
import itertools
import numpy as np
import os

from typing import Counter, Union, Optional
from discord.ext import commands
from cogs.utils.paste import paste_to_bin


class Poketwo(commands.Cog):
    """Commands related to the poketwo bot."""
    def __init__(self, bot):
        self.bot = bot
        self.pk = (pd.read_csv("cogs/utils/poketwo.csv")).fillna(0)
        self.possible_abundance = round((self.pk['abundance'][self.pk['catchable'] > 0]).sum())

    display_emoji = "🫒"

    def format_msg(self, title: str, pokemon_dataframe: pd.DataFrame, *, list_pokemon: bool=True, pokemon_out_of: bool=True) -> str:
        pkm_df = pokemon_dataframe
        total_abundance = round(pkm_df['abundance'].sum())

        pokemon = []
        for pkm_idx, pkm_row in pkm_df.iterrows():
            pkm_per_cent = round(
                pkm_row['abundance'] / self.possible_abundance * 100, 4
            )
            pkm_out_of = round(1 / pkm_per_cent * 100)
            line = f"> **{pkm_row['name.en']}** - {pkm_per_cent}%"
            pokemon.append((f"{line} (1/{pkm_out_of})" if pokemon_out_of else line))
                
        per_cent = round(total_abundance / self.possible_abundance * 100, 4)
        out_of = round(1 / per_cent * 100)
        pokemon.sort()
        all_pokemon = ("\n".join(pokemon)) if list_pokemon else ""
        result = f"__**{title}**__ (Includes all catchable forms)\n{all_pokemon}\n**Total pokemon**: {len(pokemon)}\n**Total chance**: {per_cent}% (1/{out_of})"
        if len(result) > 2000:
            pass
        return result

    @commands.group(
        aliases=("chances",),
        help="See the chances of pokémon or a rarity.",
        invoke_without_command=True,
    )
    async def chance(self, ctx):
        await ctx.send_help(ctx.command)

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

        pkm_df = self.pk.loc[(self.pk['catchable'] > 0) & (self.pk[rarity] == 1)]

        result = self.format_msg(rarity.capitalize(), pkm_df, pokemon_out_of=False)
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

        pkm_df = self.pk.loc[(self.pk['catchable'] > 0) & (self.pk['slug'].str.endswith(form))]

        result = self.format_msg(f"{form.capitalize()}-form", pkm_df)
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
        if type(region) is str:
            region = region.lower()

        elif all((type(region) is int, region < 9)):
            region = options[region - 1].lower()

        pkm_df = self.pk.loc[(self.pk['catchable'] > 0) & (self.pk["region"] == region)]
        if len(pkm_df) == 0:
            return await ctx.send(
                f'Invalid region provided. Options: {", ".join(options)}'
            )
            
        result = self.format_msg(f"{region.capitalize()} region", pkm_df, list_pokemon=False)
        await ctx.send(result)

    @chance.command(
        name="pokemon",
        aliases=("poke", "pkm"),
        help="See the chances of a specific pokémon.",
    )
    async def _pokemon(self, ctx, *, pokemon: str):
        pokemon = pokemon.lower()

        pkm_df = self.pk.loc[(self.pk['catchable'] > 0) & ((self.pk['slug'].str.lower() == pokemon) | (self.pk['name.en'].str.lower() == pokemon))]
        if len(pkm_df) == 0:
            return await ctx.send("Invalid pokémon provided.")

        result = self.format_msg(", ".join([pkm_row['name.en'] for _, pkm_row in pkm_df.iterrows()]), pkm_df, list_pokemon=False)
        await ctx.send(result)

    @chance.command(
        name="type",
        aliases=("types", "ty", "t"),
        brief="See the chances of pokémon with certain type(s)",
        help="See the chances of pokémon with certain type(s). Types: Normal, Fire, Water, Grass, Flying, Fighting, Poison, Electric, Ground, Rock, Psychic, Ice, Bug, Ghost, Steel, Dragon, Dark and Fairy.",
    )
    async def _type(self, ctx, type_1: str, type_2: str=None):
        types = (type_1.capitalize(), type_2.capitalize() if type_2 else 0)
        pkm_groups = self.pk.groupby(['type.0', 'type.1'])
        try:
            pkm_df = pkm_groups.get_group(types)
            if type_2:
                pkm_df_1 = pkm_groups.get_group(tuple(reversed(types)))
                pkm_df = pd.concat([pkm_df, pkm_df_1])
        except KeyError:
            return await ctx.send(
                f'Invalid type(s) provided `{types}`.'
            )
        pkm_df = pkm_df[:][pkm_df['catchable'] > 0]
        
        result = self.format_msg(f'{types[0] if types[1] == 0 else (" & ".join(types))} type(s)', pkm_df, list_pokemon=True)
        await ctx.send(result)


async def setup(bot):
    await bot.add_cog(Poketwo(bot))
