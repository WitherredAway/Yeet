import typing
from typing import Optional, TypeVar
from dataclasses import dataclass
from functools import cached_property
import gists

from discord.ext import commands
import pandas as pd

from helpers.constants import CODE_BLOCK_FMT

if typing.TYPE_CHECKING:
    from main import Bot


D = TypeVar("D", bound="Data")


MOVES = "https://raw.githubusercontent.com/poketwo/data/master/csv/moves.csv"
POKEMON_MOVES = (
    "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon_moves.csv"
)
MOVE_NAMES = "https://raw.githubusercontent.com/poketwo/data/master/csv/move_names.csv"
POKEMON_NAMES = "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"

ENGLISH_ID = 9


TYPES = {
    1: "Normal",
    2: "Fighting",
    3: "Flying",
    4: "Poison",
    5: "Ground",
    6: "Rock",
    7: "Bug",
    8: "Ghost",
    9: "Steel",
    10: "Fire",
    11: "Water",
    12: "Grass",
    13: "Electric",
    14: "Psychic",
    15: "Ice",
    16: "Dragon",
    17: "Dark",
    18: "Fairy",
    10001: "???",
    10002: "Shadow",
}

DAMAGE_CLASSES = {1: "Status", 2: "Physical", 3: "Special"}


@dataclass
class Pokemon:
    id: int
    name: str
    level: int


@dataclass
class Move:
    id: int
    name: str
    pokemon_objs: typing.List[Pokemon]
    power: int
    pp: int
    accuracy: int
    priority: int
    damage_class: str
    type: str

    data: D

    @cached_property
    def pokemon(self) -> typing.Dict[int, typing.List[str]]:
        # THis is a dict first to prevent duplicate pokemon while staying ordered
        pokemon = {
            pkm.name: pkm.id
            for pkm in sorted(self.pokemon_objs, key=lambda p: p.name)
        }

        return list(pokemon.keys())


class Data:
    def __init__(self, bot):
        self.bot: Bot = bot
        self.pk = self.bot.original_pk

    async def init(self):
        await self.bot.loop.run_in_executor(None, self.fetch_data)

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
        )
        self.pkm_moves_data.query(
            "pokemon_move_method_id == 1 & version_group_id == 20", inplace=True
        )

        self.pkm_grouped = self.pkm_moves_data.groupby("move_id")

        # pokemon_species_names.csv
        self.pkm_names_data = pd.read_csv(
            POKEMON_NAMES,
            index_col=0,
            usecols=["id", "name.en"],
        )

    @cached_property
    def moves(self) -> typing.Dict[int, Move]:
        moves_data = self.moves_data
        move_names = self.move_names_data

        moves = []
        for index, move in moves_data.iterrows():
            move_pokemon = self.get_move_pokemon(index)
            move_type = self.types[move.loc["type_id"]]
            move_class = self.damage_classes[move.loc["damage_class_id"]]

            moves.append(
                Move(
                    id=index,
                    name=move_names.loc[index, "name"],
                    pokemon_objs=move_pokemon,
                    power=move.loc["power"],
                    pp=move.loc["pp"],
                    accuracy=move.loc["accuracy"],
                    priority=move.loc["priority"],
                    damage_class=move_class,
                    type=move_type,
                    data=self,
                )
            )
        return moves

    def move_by_name(self, move_name: str) -> Move:
        move_name = move_name.lower()

        moves_data = self.moves_data
        move_names = self.move_names_data

        index = (move_names.loc[move_names["name"].str.lower() == move_name]).index[0]
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
        grouped = self.pkm_grouped

        pokemon = []
        pkm_names = self.pkm_names_data

        move_group = (
            grouped.get_group(move_id) if move_id in grouped.groups else None
        )
        if move_group is not None:
            for pkm_id, row in move_group.iterrows():
                if (self.pk.loc[self.pk["id"] == pkm_id, "enabled"].values[0] > 0) is False:
                    continue
                pkm_name = pkm_names.loc[pkm_id, "name.en"]

                pokemon.append(
                    Pokemon(
                        id=int(pkm_id),
                        name=str(pkm_name),
                        level=int(row.loc["level"]),
                    )
                )

        return pokemon


class PoketwoMoves(commands.Cog):
    """The cog for poketwo move related commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    display_emoji = "🔠"

    async def data(self) -> Data:
        if not hasattr(self.bot, "p2_data"):
            self.bot.p2_data = Data(self.bot)
            await self.bot.p2_data.init()
        return self.bot.p2_data

    async def format_movesets_message(self, move: Move):
        pokemon = move.pokemon
        joined = ", ".join(pokemon) if len(pokemon) > 0 else "None"
        joined = CODE_BLOCK_FMT % joined

        format = (
            f"__**{move.name}**__\n"
            f"**Type:** {move.type}\n"
            f"**Class:** {move.damage_class}\n\n"
            f"**Leveling learnset, in *Gen 8 (Galar)*** [`{len(pokemon)}`]\n"
            f"%s"
        )

        final = format % joined
        if len(final) > 2000:  # Character limit

            pokemon = sorted(
                [[pkm.name, pkm.level] for pkm in move.pokemon_objs],
                key=lambda p: p[1],
            )
            gen_8_df = pd.DataFrame(
                pokemon,
                columns=["Pokemon (Gen 8)", "Required level"],
            )

            files = [
                gists.File(
                    name="gen_8_table.csv", content=gen_8_df.to_csv(index=False)
                ),
            ]
            description = f"Pokemon that learn the move {move.name} by leveling."
            gist = await self.bot.gists_client.create_gist(
                files=files, description=description, public=False
            )

            final = format % f"<{gist.url}#file-gen_8_table-csv>"  # Header of the gen 8 file

        return final

    @commands.group(
        name="moveinfo",
        aliases=("mi", "move", "mv"),
        brief="See extended info of a move.",
        help="See the class, type and the pokemon that have a certain move.",
        invoke_without_command=True,
    )
    async def moveinfo(self, ctx: commands.Context, *, move_name: str):
        async with ctx.typing():
            data = await self.data()
            try:
                move = data.move_by_name(move_name)
            except IndexError:
                return await ctx.send(f"No move named `{move_name}` exists!")
        await ctx.send(await self.format_movesets_message(move))

    @moveinfo.command(
        name="resync",
        aliases=("sync",),
        brief="Resync data",
        description="Resync the data that the moveinfo command uses.",
    )
    async def resync(self, ctx):
        async with ctx.channel.typing():
            del self.bot.p2_data
            await self.data()
        await ctx.send("Resynced data!")


async def setup(bot):
    await bot.add_cog(PoketwoMoves(bot))
