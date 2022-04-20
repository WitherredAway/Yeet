import typing
from typing import Optional, TypeVar
from dataclasses import dataclass
from functools import cached_property

import discord
from discord.ext import commands
import pandas as pd


D = TypeVar("D", bound="Data")


MOVES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/moves.csv"
POKEMON_MOVES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_moves.csv"
POKETWO_MOVES = (
    "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon_moves.csv"
)
MOVE_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/move_names.csv"
POKEMON_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_species_names.csv"
POKETWO_NAMES = "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"
TYPE_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/type_names.csv"
DAMAGE_CLASSES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/move_damage_classes.csv"

ENGLISH_ID = 9


@dataclass
class Move:
    id: int
    name: str
    pokemon: typing.Dict[str, typing.List[str]]
    power: int
    pp: int
    accuracy: int
    priority: int
    damage_class: str
    type: str

    data: D


class Data:
    def __init__(self):
        self.fetch_data()

    def fetch_data(self):
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
            usecols=[
                "pokemon_id",
                "version_group_id",
                "move_id",
                "pokemon_move_method_id",
                "level",
            ],
        )
        self.pkm_moves_data.query(
            "pokemon_move_method_id == 1 & version_group_id == 1", inplace=True
        )

        # pokemon_moves.csv, poketwo's gen7 data
        self.pkm_moves_data_7 = pd.read_csv(
            POKEMON_MOVES,
            index_col=0,
            usecols=["pokemon_id", "move_id", "pokemon_move_method_id", "level"],
        )
        self.pkm_moves_data_7.query("pokemon_move_method_id == 1", inplace=True)

        self.pkm_grouped = {
            7: self.pkm_moves_data_7.groupby("move_id"),
            8: self.pkm_moves_data.groupby("move_id"),
        }
        # pokemon_species_names.csv
        self.pkm_names_data_8 = pd.read_csv(
            POKEMON_NAMES,
            index_col=0,
            usecols=["pokemon_species_id", "local_language_id", "name"],
        )
        self.pkm_names_data_8.query("local_language_id == @ENGLISH_ID", inplace=True)

        # pokemon.csv, poketwo's gen7 data
        self.pkm_names_data_7 = pd.read_csv(
            POKETWO_NAMES,
            index_col=0,
            usecols=["id", "name.en"],
        )
        self.pkm_names_data_7.columns = ["name"]

        self.pkm_names_data = {7: self.pkm_names_data_7, 8: self.pkm_names_data_8}

        # type_names.csv
        self.type_names_data = pd.read_csv(
            TYPE_NAMES,
            index_col=0,
        )
        self.type_names_data.query("local_language_id == @ENGLISH_ID", inplace=True)

        # move_damage_classes.csv
        self.damage_classes_data = pd.read_csv(
            DAMAGE_CLASSES,
            index_col=0,
        )
        self.moves_by_index = self.moves_by_index

    def resync(self):
        self.fetch_data()

    def move_by_name(self, move_name: str) -> Move:
        move_name = move_name.lower()
        return self.moves_by_index[move_name]

    @cached_property
    def moves_by_index(self) -> typing.Dict[str, Move]:
        return {move.name.lower(): move for move in self.moves.values()}

    @cached_property
    def moves(self) -> typing.Dict[int, Move]:
        moves_data = self.moves_data
        move_names = self.move_names_data

        moves = {}
        for index, move in moves_data.iterrows():
            move_pokemon = self.get_move_pokemon(index)
            move_type = self.types[move.loc["type_id"]]
            move_class = self.damage_classes[move.loc["damage_class_id"]]

            moves[index] = Move(
                id=index,
                name=move_names.loc[index, "name"],
                pokemon=move_pokemon,
                power=move.loc["power"],
                pp=move.loc["pp"],
                accuracy=move.loc["accuracy"],
                priority=move.loc["priority"],
                damage_class=move_class,
                type=move_type,
                data=self,
            )
        return moves

    @cached_property
    def types(self) -> typing.Dict[int, str]:
        type_names = self.type_names_data

        types = {index: type.loc["name"] for index, type in type_names.iterrows()}
        return types

    @cached_property
    def damage_classes(self) -> typing.Dict[int, str]:
        damage_classes = self.damage_classes_data

        return {
            index: row.loc["identifier"].capitalize()
            for index, row in damage_classes.iterrows()
        }

    def get_move_pokemon(self, move_id) -> typing.List[str]:
        pkm_grouped = self.pkm_grouped

        pokemon = {7: [], 8: []}
        for gen, grouped in pkm_grouped.items():
            pkm_names = self.pkm_names_data[gen]
            move_group = grouped.groups.get(move_id, None)

            if move_group is not None:
                for pkm_id in move_group:
                    pokemon[gen].append(pkm_names.loc[pkm_id, "name"])

        pokemon = {gen: list(set(pkm_list)) for gen, pkm_list in pokemon.items()}
        return pokemon


class PoketwoMoves(commands.Cog):
    """The cog for poketwo move related commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @cached_property
    def data(self) -> Data:
        self.bot.data = Data()
        return self.bot.data

    def format_message(self, move: Move):
        format = (
            f"__**{move.name}**__\n"
            f"**Type:** {move.type}\n"
            f"**Class:** {move.damage_class}\n\n"
            f"**Pokemon that learn it in *Poketwo - Gen 7 (Alola)***\n"
            f'```\n{", ".join(move.pokemon[7]) if len(move.pokemon[7]) > 0 else "None"}\n```\n'
            f"**Pokemon that learn it in *Gen 8 (Galar)***"
            f'```\n{", ".join(move.pokemon[8]) if len(move.pokemon[8]) > 0 else "None"}\n```'
        )
        return format

    @commands.command(
        name="moveinfo",
        aliases=("mi", "move", "mv"),
        brief="See extended info of a move.",
        help="See the name, type and the pokemon that have a certain move.",
    )
    async def moveinfo(self, ctx: commands.Context, *, move_name: str):
        try:
            move = self.data.move_by_name(move_name)
        except KeyError:
            return await ctx.send(f"No move named {move_name} exists!")

        await ctx.send(self.format_message(move))


async def setup(bot):
    await bot.add_cog(PoketwoMoves(bot))
