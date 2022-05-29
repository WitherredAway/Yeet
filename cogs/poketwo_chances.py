import asyncio
import os
import typing
from typing import Counter, Union, Optional
from functools import cached_property

import discord
from discord.ext import commands, tasks
import numpy as np
import pandas as pd
import gists

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

    async def get_chance_gist(self, df: pd.DataFrame, *, title: Optional[str] = "pokemon") -> gists.Gist:
        for idx in df.index:
            df.at[idx, 'Chance'] = "1/" + str(round(1/(df.at[idx, "abundance"]/266933*100)*100))
            df.at[idx, 'Chance percentage'] = str((df.at[idx, "abundance"]/266933*100).round(4)) + "%"

        df.sort_values('abundance', ascending=False, inplace=True)
        df.drop(columns=['abundance', 'catchable'], inplace=True)
        df.rename(columns={'name.en': "Pokemon", 'dex_number': "Dex"}, inplace=True)

        file = gists.File(name=f'{title.casefold()}_chances.csv', content=df.to_csv(index=False))

        g = await self.bot.gists_client.create_gist(files=[file], description=f"Chances of {title} pokémon", public=False)
        return g

    async def format_msg(
        self,
        title: str,
        pokemon_dataframe: pd.DataFrame,
        *,
        list_pokemon: bool = True,
    ) -> str:
        pkm_df = pokemon_dataframe
        total_abundance = round(pkm_df["abundance"].sum())

        out_of = round(1 / (total_abundance / self.possible_abundance * 100) * 100)
        per_cent = round(1 / out_of * 100, 4)
        
        extra = "\n"
        if list_pokemon is True:
            all_pokemon = f"> All pokémon: <{(await self.get_chance_gist(pkm_df, title=title)).url}>"
            extra = f" (Includes all catchable forms)\n{all_pokemon}\n**Total pokemon**: {len(pkm_df)}"
        
        result = f"__**{title}**__{extra}\n**Total chance**: {per_cent}% (1/{out_of})"
        return result

    @cached_property
    def pk(self):
        pk = pd.read_csv(self.pokemon_csv)
        self.possible_abundance = round(
            (pk.loc[:, "abundance"][pk.loc[:, "catchable"] > 0]).sum()
        )
        return pk

    @commands.group(
        aliases=("chances",),
        help="See the chances of pokémon or a rarity.",
        invoke_without_command=True
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

        pkm_df = self.pk.loc[(self.pk["catchable"] > 0) & (self.pk[rarity] == 1)]
        pkm_df = pkm_df.loc[:, ['dex_number', 'name.en', 'catchable', 'abundance']]
        
        async with ctx.channel.typing():
            result = await self.format_msg(
                rarity.capitalize(), pkm_df
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
        pkm_df = pkm_df.loc[:, ['dex_number', 'name.en', 'catchable', 'abundance']]
        
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
        pkm_df = pkm_df.loc[:, ['dex_number', 'name.en', 'catchable', 'abundance']]
        
        if len(pkm_df) == 0:
            return await ctx.send(
                f'Invalid region provided. Options: {", ".join(options)}'
            )

        async with ctx.channel.typing():
            result = await self.format_msg(
                f"{region.capitalize()} region", pkm_df
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
                (self.pk["slug"].str.casefold() == pokemon)
                | (self.pk["name.en"].str.casefold() == pokemon)
            )
        ]
        pkm_df = pkm_df.loc[:, ['dex_number', 'name.en', 'catchable', 'abundance']]
        
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
            type_2 = type_2.capitalize()
            msg = " & ".join([type_1, type_2])
            pkm_df = self.pk.loc[
                ((self.pk["type.0"] == type_1) & (self.pk["type.1"] == type_2))
                | ((self.pk["type.0"] == type_2) & (self.pk["type.1"] == type_1))
            ]

        if len(pkm_df) == 0:
            return await ctx.send(f"Invalid type(s) provided `{type_1}`, `{type_2}`.")
        pkm_df = pkm_df.loc[pkm_df["catchable"] > 0]
        pkm_df.rename(columns={'type.0': "Type 1", 'type.1': "Type 2"}, inplace=True)
        pkm_df = pkm_df.loc[:, ['dex_number', 'name.en', 'Type 1', 'Type 2', 'catchable', 'abundance']]
        
        async with ctx.channel.typing():
            result = await self.format_msg(
                f"{msg} Type(s)",
                pkm_df,
            )
        await ctx.send(result)


async def setup(bot):
    await bot.add_cog(PoketwoChances(bot))
