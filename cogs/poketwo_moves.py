import io
import asyncio
import typing
from typing import Optional, TypeVar
from dataclasses import dataclass
from functools import cached_property

import discord
import aiohttp
from discord.ext import commands
import pandas as pd

import time


D = TypeVar("D", bound="Data")


_MOVES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/moves.csv"
_POKEMON_MOVES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_moves.csv"
_POKETWO_MOVES = (
    "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon_moves.csv"
)
_MOVE_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/move_names.csv"
_POKEMON_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_species_names.csv"
_POKEMON_FORM_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_form_names.csv"
_POKETWO_NAMES = "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"

ENGLISH_ID = 9


TYPES = {
    1: 'Normal',
    2: 'Fighting',
    3: 'Flying',
    4: 'Poison',
    5: 'Ground',
    6: 'Rock',
    7: 'Bug',
    8: 'Ghost',
    9: 'Steel',
    10: 'Fire',
    11: 'Water',
    12: 'Grass',
    13: 'Electric',
    14: 'Psychic',
    15: 'Ice',
    16: 'Dragon',
    17: 'Dark',
    18: 'Fairy',
    10001: '???',
    10002: 'Shadow'
}

DAMAGE_CLASSES = {
    1: 'Status',
    2: 'Physical',
    3: 'Special'
}


@dataclass
class Pokemon:
    id: int
    name: str
    level: int


@dataclass
class Move:
    id: int
    name: str
    pokemon_objs: typing.Dict[int, typing.List[Pokemon]]
    power: int
    pp: int
    accuracy: int
    priority: int
    damage_class: str
    type: str

    data: D

    @cached_property
    def pokemon(self) -> typing.Dict[str, typing.List[str]]:
        pokemon = {}
        for gen, pokemon_obj_list in self.pokemon_objs.items():
            pokemon_dict = {pkm.name: pkm.id for pkm in sorted(pokemon_obj_list, key=lambda p: p.name)}
            pokemon[gen] = list(pokemon_dict.keys())

        return pokemon

class Data:
    async def get_csv(self, session, url):
        async with session.get(url) as response:
            return io.StringIO(await response.text())
            
    async def fetch_data(self):
        async with aiohttp.ClientSession() as session:
            MOVES = await self.get_csv(session, _MOVES)
            MOVE_NAMES = await self.get_csv(session, _MOVE_NAMES)
            POKEMON_MOVES = await self.get_csv(session, _POKEMON_MOVES)
            POKETWO_MOVES = await self.get_csv(session, _POKETWO_MOVES)
            POKEMON_FORM_NAMES = await self.get_csv(session, _POKEMON_FORM_NAMES)
            POKEMON_NAMES = await self.get_csv(session, _POKEMON_NAMES)
            POKETWO_NAMES = await self.get_csv(session, _POKETWO_NAMES)
            
        # moves.csv
        self.moves_data = pd.read_csv(
            MOVES,
            index_col=0,
            usecols=[
                "id",
                "type_id",
                "power",
                "pp",
                "accuracy",
                "priority",
                "damage_class_id",
            ],
        )
        # move_names.csv
        self.move_names_data = pd.read_csv(
            MOVE_NAMES,
            index_col=0,
        )
        self.move_names_data.query("local_language_id == @ENGLISH_ID", inplace=True)

        # pokemon_moves.csv
        self.pkm_moves_data = pd.read_csv(
            POKEMON_MOVES,
            index_col=0,
        )
        self.pkm_moves_data.query(
            "pokemon_move_method_id == 1 & version_group_id == 20", inplace=True
        )

        # pokemon_moves.csv, poketwo's gen7 data
        self.pkm_moves_data_7 = pd.read_csv(
            POKETWO_MOVES,
            index_col=0,
        )
        self.pkm_moves_data_7.query("pokemon_move_method_id == 1", inplace=True)

        self.pkm_grouped = {
            7: self.pkm_moves_data_7.groupby("move_id"),
            8: self.pkm_moves_data.groupby("move_id"),
        }
        
        # pokemon_form_names.csv
        self.pkm_form_names_data = pd.read_csv(
            POKEMON_FORM_NAMES,
            index_col=0,
            usecols=["pokemon_form_id", "local_language_id", "pokemon_name"]
        )
        self.pkm_form_names_data.query("local_language_id == @ENGLISH_ID & pokemon_name == pokemon_name", inplace=True)
        self.pkm_form_names_data.columns = ["local_language_id", "name"]

        # pokemon_species_names.csv
        self.pkm_names_data_8 = pd.read_csv(
            POKEMON_NAMES,
            index_col=0,
            usecols=["pokemon_species_id", "local_language_id", "name"],
        )
        self.pkm_names_data_8.query("local_language_id == @ENGLISH_ID", inplace=True)

        con = pd.concat([self.pkm_names_data_8, self.pkm_form_names_data])
        con = con[~con.index.duplicated(keep='first')]  # Keep the first instance of duplicate indices

        self.pkm_names_data_8 = con
        
        # pokemon.csv, poketwo's gen7 data
        self.pkm_names_data_7 = pd.read_csv(
            POKETWO_NAMES,
            index_col=0,
            usecols=["id", "name.en"],
        )
        self.pkm_names_data_7.columns = ["name"]

        #con = pd.concat([self.pkm_names_data_7, self.pkm_form_names_data])
        #con = con[~con.index.duplicated(keep='first')]  # Keep the first instance of duplicate indices

        #self.pkm_names_data_7 = con

        self.pkm_names_data = {7: self.pkm_names_data_7, 8: self.pkm_names_data_8}
        
    async def resync(self):
        await self.fetch_data()

    def move_by_name(self, move_name: str) -> Move:
        move_name = move_name.lower()
        
        moves_data = self.moves_data
        move_names = self.move_names_data

        index = (move_names.loc[move_names['name'].str.lower() == move_name]).index[0]
        move_row = moves_data.loc[index]
        move_pokemon = self.get_move_pokemon(index)
        move_type = self.types[move_row.loc["type_id"]]
        move_class = self.damage_classes[move_row.loc["damage_class_id"]]

        return Move(
            id=index,
            name=move_names.loc[index, "name"],
            pokemon_objs=move_pokemon,
            power=move_row.loc["power"],
            pp=move_row.loc["pp"],
            accuracy=move_row.loc["accuracy"],
            priority=move_row.loc["priority"],
            damage_class=move_class,
            type=move_type,
            data=self,
        )

    @property
    def types(self) -> typing.Dict[int, str]:
        return TYPES

    @property
    def damage_classes(self) -> typing.Dict[int, str]:
        return DAMAGE_CLASSES

    def get_move_pokemon(self, move_id) -> typing.List[str]:
        pkm_grouped = self.pkm_grouped

        pokemon = {7: [], 8: []}
        for gen, grouped in pkm_grouped.items():
            pkm_names = self.pkm_names_data[gen]
            
            move_group = grouped.get_group(move_id) if move_id in grouped.groups else None
            if move_group is not None:
                for pkm_id, row in move_group.iterrows():
                    pkm_name = pkm_names.loc[pkm_id, 'name']
                    
                    pokemon[gen].append(
                        Pokemon(
                            id=pkm_id,
                            name=pkm_name,
                            level=row.loc['level']
                        )
                    )

        return pokemon


class PoketwoMoves(commands.Cog):
    """The cog for poketwo move related commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def data(self) -> Data:
        if not hasattr(self.bot, "data"):
            self.bot.data = Data()
            await self.bot.data.fetch_data()
        return self.bot.data
    
    def format_message(self, move: Move):
        gen_7_pokemon = move.pokemon[7]
        len_gen_7 = len(gen_7_pokemon)

        gen_8_pokemon = move.pokemon[8]
        len_gen_8 = len(gen_8_pokemon)
        
        format = (
            f"`{move.id}`  __**{move.name}**__\n"
            f"**Type:** {move.type}\n"
            f"**Class:** {move.damage_class}\n\n"
            f"**Pokemon that learn it by leveling up in *Poketwo - Gen 7 (Alola)*** [`{len_gen_7}`]\n"
            f'```\n{", ".join(gen_7_pokemon) if len_gen_7 > 0 else "None"}\n```\n'
            f"**Pokemon that learn it by leveling up in *Gen 8 (Galar)*** [`{len_gen_8}`]"
            f'```\n{", ".join(gen_8_pokemon) if len_gen_8 > 0 else "None"}\n```'
        )
        return format

    @commands.group(
        name="moveinfo",
        aliases=("mi", "move", "mv"),
        brief="See extended info of a move.",
        help="See the name, type and the pokemon that have a certain move.",
        invoke_without_command=True
    )
    async def moveinfo(self, ctx: commands.Context, *, move_name: str):
        data = await self.data()
        async with ctx.typing():
            try:
                move = data.move_by_name(move_name)
            except IndexError:
                return await ctx.send(f"No move named `{move_name}` exists!")
        await ctx.send(self.format_message(move))
        
    @moveinfo.command(
        name="resync",
        aliases=("sync",),
        brief="Resync data",
        description="Resync the data that the moveinfo command uses."
    )
    async def resync(self, ctx):
        data = await self.data()
        async with ctx.channel.typing():
            await data.resync()
        await ctx.send("Resynced data!")


async def setup(bot):
    await bot.add_cog(PoketwoMoves(bot))
