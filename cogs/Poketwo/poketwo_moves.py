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


MOVES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/moves.csv"
POKEMON_MOVES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_moves.csv"
POKETWO_MOVES = (
    "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon_moves.csv"
)
MOVE_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/move_names.csv"
POKEMON_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_species_names.csv"
POKEMON_FORMS = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_forms.csv"
POKEMON_FORM_NAMES = "https://raw.githubusercontent.com/poketwo/pokedex/master/pokedex/data/csv/pokemon_form_names.csv"
POKETWO_NAMES = "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"

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
    pokemon_objs: typing.Dict[int, typing.List[Pokemon]]
    power: int
    pp: int
    accuracy: int
    priority: int
    damage_class: str
    type: str

    data: D

    @cached_property
    def pokemon(self) -> typing.Dict[int, typing.List[str]]:
        pokemon = {}
        for gen, pokemon_obj_list in self.pokemon_objs.items():
            # This is a dict first so that there can only be one
            # instead of set(), to keep the order
            pokemon_dict = {
                pkm.name: pkm.id
                for pkm in sorted(pokemon_obj_list, key=lambda p: p.name)
            }
            pokemon[gen] = list(pokemon_dict.keys())

        return pokemon


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

        # poketwo_moves.csv, poketwo's gen7 data
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
            usecols=["pokemon_form_id", "local_language_id", "pokemon_name"],
        )
        self.pkm_form_names_data.query(
            "local_language_id == @ENGLISH_ID & pokemon_name == pokemon_name",
            inplace=True,
        )
        self.pkm_form_names_data.columns = ["local_language_id", "name"]

        # pokemon_forms.csv
        self.pkm_forms_data = pd.read_csv(
            POKEMON_FORMS,
            index_col=0,
            usecols=["id", "pokemon_id"],
        )

        # Here the 'pokemon_id' column in pkm_forms_data
        # replaces the corresponding index column of pkm_form_names_data
        self.pkm_form_names_data = self.pkm_form_names_data.reset_index()
        self.pkm_form_names_data = self.pkm_form_names_data.assign(
            pokemon_form_id=self.pkm_form_names_data.pokemon_form_id.map(
                self.pkm_forms_data.pokemon_id
            ).combine_first(self.pkm_form_names_data.pokemon_form_id)
        ).set_index("pokemon_form_id")

        # pokemon_species_names.csv
        self.pkm_names_data_8 = pd.read_csv(
            POKEMON_NAMES,
            index_col=0,
            usecols=["pokemon_species_id", "local_language_id", "name"],
        )
        self.pkm_names_data_8.query("local_language_id == @ENGLISH_ID", inplace=True)

        con = pd.concat([self.pkm_names_data_8, self.pkm_form_names_data])
        con = con[
            ~con.index.duplicated(keep="first")
        ]  # Keep the first instance of duplicate indices

        self.pkm_names_data_8 = con

        # pokemon.csv, poketwo's gen7 data
        self.pkm_names_data_7 = pd.read_csv(
            POKETWO_NAMES,
            index_col=0,
            usecols=["id", "name.en"],
        )
        self.pkm_names_data_7.columns = ["name"]

        self.pkm_names_data = {7: self.pkm_names_data_7, 8: self.pkm_names_data_8}

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
        pkm_grouped = self.pkm_grouped

        pokemon = {7: [], 8: []}
        for gen, grouped in pkm_grouped.items():
            pkm_names = self.pkm_names_data[gen]

            move_group = (
                grouped.get_group(move_id) if move_id in grouped.groups else None
            )
            if move_group is not None:
                for pkm_id, row in move_group.iterrows():
                    if gen == 7:
                        if not (self.pk.loc[pkm_id, "enabled"] > 0):
                            continue
                    pkm_name = pkm_names.loc[pkm_id, "name"]

                    pokemon[gen].append(
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
        gen_7_pokemon = move.pokemon[7]
        len_gen_7 = len(gen_7_pokemon)
        gen_7_list = ", ".join(gen_7_pokemon) if len_gen_7 > 0 else "None"

        gen_8_pokemon = move.pokemon[8]
        len_gen_8 = len(gen_8_pokemon)
        gen_8_list = ", ".join(gen_8_pokemon) if len_gen_8 > 0 else "None"

        if (len(gen_7_list) + len(gen_8_list)) > 1819:  # Character limit
            gen_7_pokemon = sorted(
                [[pkm.name, pkm.level] for pkm in move.pokemon_objs[7]],
                key=lambda p: p[1],
            )
            gen_7_df = pd.DataFrame(
                gen_7_pokemon,
                columns=["Pokemon (Poketwo - Gen 7)", "Required level"],
            )

            gen_8_pokemon = sorted(
                [[pkm.name, pkm.level] for pkm in move.pokemon_objs[8]],
                key=lambda p: p[1],
            )
            gen_8_df = pd.DataFrame(
                gen_8_pokemon,
                columns=["Pokemon (Gen 8)", "Required level"],
            )

            files = [
                gists.File(
                    name="gen_7_table.csv", content=gen_7_df.to_csv(index=False)
                ),
                gists.File(
                    name="gen_8_table.csv", content=gen_8_df.to_csv(index=False)
                ),
            ]
            description = f"Pokemon that learn the move {move.name} by leveling."
            gist = await self.bot.gists_client.create_gist(
                files=files, description=description, public=False
            )

            gen_7_list = (
                f"<{gist.url}#file-gen_7_table-csv>"  # Header of the gen 7 file
            )
            gen_8_list = (
                f"<{gist.url}#file-gen_8_table-csv>"  # Header of the gen 8 file
            )
        else:
            gen_7_list = CODE_BLOCK_FMT % gen_7_list
            gen_8_list = CODE_BLOCK_FMT % gen_8_list

        format = (
            f"__**{move.name}**__\n"
            f"**Type:** {move.type}\n"
            f"**Class:** {move.damage_class}\n\n"
            f"**Leveling learnset, in *Poketwo - Gen 7 (Alola)*** [`{len_gen_7}`]\n"
            f"{gen_7_list}\n"
            f"**Leveling learnset, in *Gen 8 (Galar)*** [`{len_gen_8}`]\n"
            f"{gen_8_list}"
        )
        return format

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
