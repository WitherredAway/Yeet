import discord
from discord.ext import commands
import asyncio
from main import *
from typing import Counter, Union
import wikipedia
import random
import pandas as pd
import itertools

class Poketwo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pk = pd.read_csv("pokemon.csv")
        self.possible_abundance = sum([self.pk.at[pkm, 'abundance'] for pkm in self.pk.index if self.pk.at[pkm, 'catchable'] > 0])

    display_emoji = "🫒"

    @commands.group(aliases=("chances",),
                    help="See the chances of pokémon or a rarity.",
                    invoke_without_command=True)
    async def chance(self, ctx):
        await ctx.send_help(ctx.command)
    
    @chance.command(name="rarity", help="See the chances of a rarity and the pokémon that belong to that rarity.")
    async def _rarity(self, ctx, rarity):
        pokemon = []
        total_abundance = 0
        options = ["Mythical", "Legendary", "Ultra_beast"]
        for option in options:
            if rarity.lower() in option.lower():
                rarity = option.lower()
                break
        else:
            return await ctx.send(f'Invalid rarity provided. Valid rarities: {", ".join(options)}.')
        for pkm in self.pk.index:
            if all((self.pk.at[pkm, 'catchable'] > 0, self.pk.at[pkm, rarity] > 0)):
                pkm_per_cent = round(self.pk.at[pkm, 'abundance']/self.possible_abundance*100, 4)
                pkm_out_of = round(1/pkm_per_cent, 1)
                total_abundance += self.pk.at[pkm, 'abundance']
                pokemon.append(f"> **{self.pk.at[pkm, 'name.en']}** - {pkm_per_cent}%")
                    #pokes[f"{round(pk.at[pkm, 'abundance']/266933*100, 4)}%"].append(f"{pk.at[pkm, 'name.en']}")

        per_cent = round(total_abundance/self.possible_abundance*100, 3)
        out_of = round(1/per_cent, 1)
        pokemon.sort()
        all_pokemon = "\n".join(pokemon)
        result = f'__**{rarity.capitalize()}**__ (Includes all forms of all pokémon)\n{all_pokemon}\n**Total pokemon**: {len(pokemon)}\n**Total chance**: {per_cent}% (1/{out_of})'
        await ctx.send(result)

    @chance.command(name="form", help="See the chances of a form and the individual pokémon. Options: Alolan, Galarian.")
    async def _form(self, ctx, form):
        pokemon = []
        total_abundance = 0
        options = ["Alolans", "Galarians"]
        for option in options:
            if form.lower() in option.lower():
                form = option.lower()[:5]
                break
        else:
            return await ctx.send(f'Invalid form provided. Options: {", ".join(options)}')
        for pkm in self.pk.index:
            if all((self.pk.at[pkm, 'catchable'] > 0, self.pk.at[pkm, "slug"].endswith(form))):
                pkm_per_cent = round(self.pk.at[pkm, 'abundance']/self.possible_abundance*100, 4)
                pkm_out_of = round(1/pkm_per_cent, 1)
                total_abundance += self.pk.at[pkm, 'abundance']
                pokemon.append(f"> **{self.pk.at[pkm, 'name.en']}** - {pkm_per_cent}% (1/{pkm_out_of})")
                #pokemon[f"{round(pk.at[pkm, 'abundance']/266933*100, 4)}%"].append(f"{pk.at[pkm, 'name.en']}")

        per_cent = round(total_abundance/self.possible_abundance*100, 3)
        out_of = round(1/per_cent, 1) 
        pokemon.sort()
        all_pokemon = "\n".join(pokemon)
        result = f'__**{form.capitalize()}-form**__ (Includes all forms of all pokémon)\n{all_pokemon}\n**Total pokemon**: {len(pokemon)}\n**Total chance**: {per_cent}% (1/{out_of})'
        await ctx.send(result)

    @chance.command(name="region", aliases=("r", "gen"), help="See the chances of a region and the individual pokémon. Options: Kanto/1, Johto/2, Hoenn/3, Sinnoh/4, Unova/5, Kalos/6, Alola/7, Galar/8.")
    async def _region(self, ctx, region: Union[int, str]):
        pokemon = []
        total_abundance = 0
        options = ["Kanto", "Johto", "Hoenn", "Sinnoh", "Unova", "Kalos", "Alola", "Galar"]
        if type(region) is str:
            if region.capitalize() in options:
                region = region.lower()
        
        elif all((type(region) is int, region < 9)):
            region = options[region-1].lower()
        else:
            return await ctx.send(f'Invalid region provided. Options: {", ".join(options)}')

        for pkm in self.pk.index:
            if all((self.pk.at[pkm, 'catchable'] > 0, self.pk.at[pkm, "region"] == region)):
                total_abundance += self.pk.at[pkm, 'abundance']
                pokemon.append({self.pk.at[pkm, 'name.en']})
                #pokemon[f"{round(pk.at[pkm, 'abundance']/266933*100, 4)}%"].append(f"{pk.at[pkm, 'name.en']}")

        per_cent = round(total_abundance/self.possible_abundance*100, 3)
        out_of = round(1/per_cent, 1) 
        result = f'__**{region.capitalize()}**__ (Includes all forms of all pokémon)\n\n**Total pokemon**: {len(pokemon)}\n**Total chance**: {per_cent}% (1/{out_of})'
        await ctx.send(result)

    @chance.command(name="pokemon", aliases=("poke", "pkm"), help="See the chances of a specific pokémon.")
    async def _pokemon(self, ctx, *, pokemon: str):
        pokemon = pokemon.lower()
        pokemons = []
        total_abundance = 0
        for pkm in self.pk.index:
            if all(
                (
                    self.pk.at[pkm, 'catchable'] > 0,
                    any(
                        (
                            self.pk.at[pkm, "slug"].lower() == pokemon,
                            self.pk.at[pkm, "name.en"].lower() == pokemon
                        )
                    )
                )
            ):                
                 total_abundance = self.pk.at[pkm, 'abundance']
                 pokemons.append(self.pk.at[pkm, 'name.en'])
                 break
        else:
            return await ctx.send("Invalid pokémon provided.")
                
        per_cent = round(total_abundance/self.possible_abundance*100, 4)
        out_of = round(1/per_cent, 1) 
        result = f'__**{", ".join(pokemons)}**__\n\n**Total pokemon**: {len(pokemons)}\n**Total chance**: {per_cent}% (1/{out_of})'
        await ctx.send(result)

def setup(bot):
    bot.add_cog(Poketwo(bot))