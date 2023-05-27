import typing
from typing import List, Optional, TypeVar
from dataclasses import dataclass
from functools import cached_property
from cogs.RDanny.utils.paginator import BotPages
from cogs.utils.utils import enumerate_list, make_progress_bar
import gists

from discord.ext import commands, menus
import pandas as pd

from helpers.constants import CODE_BLOCK_FMT, EMBED_DESC_CHAR_LIMIT

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
        self.pk = self.bot.original_pk.set_index("id")

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
        pkm_names = self.pk

        move_group = (
            grouped.get_group(move_id) if move_id in grouped.groups else None
        )
        if move_group is not None:
            for pkm_id, row in move_group.iterrows():
                if not (pkm_names.loc[pkm_id, "enabled"] > 0):
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


PER_PAGE = 30

class PokemonPageSource(menus.ListPageSource):
    def __init__(self, move: Move, per_page=PER_PAGE):
        self.move = move
        entries = enumerate_list(move.pokemon)
        super().__init__(entries, per_page=per_page)

    async def format_page(self, menu: BotPages, entries):
        move = self.move
        embed = menu.ctx.bot.Embed(title=move.name)
        joined = "\n".join(entries) if len(entries) > 0 else "None"
        joined = CODE_BLOCK_FMT % joined

        last_entry = int(entries[-1].split('\u200b')[0])  #!IMPORTANT this depends on enumeration of entries
        format = (
            f"**Type:** {move.type}\n"
            f"**Class:** {move.damage_class}\n\n"
            f"**Leveling learnset in *Gen 8 (Galar)*** [`{last_entry}/{len(self.entries)}`]\n"
            f"{make_progress_bar(last_entry, len(self.entries), length=15)}\n"
            f"%s"
        )

        final = format % joined

        embed.description = final
        embed.set_footer(text=f"Use the `@Pokétwo#8236 moveset <pokemon>` command to see how each pokemon obtains the move.")
        return embed


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

        source = PokemonPageSource(move)
        menu = BotPages(source, ctx=ctx, check_embeds=True, compact=True)
        await menu.start()

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
