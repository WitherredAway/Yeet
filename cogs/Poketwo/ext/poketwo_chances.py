import asyncio
import os
import typing
from typing import Counter, Union, Optional
import json
import re
from functools import cached_property

import discord
from discord.ext import commands
import numpy as np
import pandas as pd
from cogs.Poketwo.utils import get_pokemon
import gists

if typing.TYPE_CHECKING:
    from main import Bot


ALL_GIST = "https://gist.github.com/1bc525b05f4cd52555a2a18c331e0cf9"
STARTERS_GIST = "https://gist.github.com/1bdee3b3fb2a29ae8f83ebdd70013456"
RARITY_GISTS = {
    "Mythical": "https://gist.github.com/ba3f32d61cfdaf857c8541d168c21698",
    "Legendary": "https://gist.github.com/af25f3f398fbc0441fd0248a5ca3faad",
    "Ultra_beast": "https://gist.github.com/ba3f1b7063e939d8119286bbeb8e8080",
}
FORM_GISTS = {
    "Alolan": "https://gist.github.com/7c3cdaaa36c38d2fb2bd716652b09d00",
    "Galarian": "https://gist.github.com/4fb6735b2241506105af52626953618b",
    "Hisuian": "https://gist.github.com/4bcf5ef86577b14aa464a3376adb430e",
}
REGION_GISTS = {
    "Kanto": "https://gist.github.com/2c48fc73eb1a9e94737634092e1c62e3",
    "Johto": "https://gist.github.com/4456e7da504e9ff5ddc653cd3bc4e76c",
    "Hoenn": "https://gist.github.com/ce4facd1f383676bb745cece67fbac50",
    "Sinnoh": "https://gist.github.com/e9a435742bea160eb588c8812e0730c4",
    "Unova": "https://gist.github.com/6af2072d0229c3f5582b32f20b65f2f5",
    "Kalos": "https://gist.github.com/849a6b64a35a505c7afb2eb276eda18d",
    "Alola": "https://gist.github.com/a55287b7bff61b90b3182bca602b062a",
    "Galar": "https://gist.github.com/f4d75c84e7ed4ce57273b6ef860a5a54",
    "Paldea": "https://gist.github.com/6526c45006956f48043ad061ebcc5ce3",
    "Hisui": "https://gist.github.com/46bbc638f81687aa42709a83078aa1f8",
}
TYPE_GISTS_GIST = (
    "https://gist.github.com/WitherredAway/286394d65db106061d8e76918dab9050"
)

EVENT_GIST = "https://gist.github.com/caf8fc84a8072cfcd1d07b2d18730d5e"


DELAY = 1
pattern = re.compile(
    r"""__\*\*(?P<title>.+) spawn-chances\*\*__ \(Includes all catchable forms\)
> All pokémon: <(?P<gist>.+)>
\*\*Total pokemon\*\*: (?P<total>\d+)
\*\*Total chance\*\*: (?P<chance_per>[\d.]+)% or (?P<chance>[\d\/]+)"""
)

STARTERS = [
    "Bulbasaur",
    "Charmander",
    "Squirtle",
    "Chikorita",
    "Cyndaquil",
    "Totodile",
    "Treecko",
    "Torchic",
    "Mudkip",
    "Turtwig",
    "Chimchar",
    "Piplup",
    "Snivy",
    "Tepig",
    "Oshawott",
    "Chespin",
    "Fennekin",
    "Froakie",
    "Rowlet",
    "Litten",
    "Popplio",
    "Grookey",
    "Scorbunny",
    "Sobble",
    "Sprigatito",
    "Fuecoco",
    "Quaxly",
]


class PoketwoChances(commands.Cog):
    """Commands related to the poketwo bot."""

    display_emoji = "🔣"

    @property
    def gists_client(self) -> gists.Client:
        return self.bot.wgists_client

    @cached_property
    def possible_abundance(self):
        return round(self.pk.loc[self.pk["catchable"] > 0, "abundance"].sum(), 4)

    async def update_chance_gist(
        self,
        df: pd.DataFrame,
        *,
        description: Optional[str] = "Spawn chances",
        gist: gists.Gist,
        keep_cols: Optional[typing.List[str]] = None,
    ) -> gists.Gist:
        df["Chance"] = np.nan
        df["Chance percentage"] = np.nan
        for idx in df.index:
            chance = self.possible_abundance / df.at[idx, "abundance"]
            df.at[idx, "Chance"] = "1/" + str(round(chance))
            df.at[idx, "Chance percentage"] = str(round(1 / chance * 100, 4)) + "%"

        df.sort_values("abundance", ascending=False, inplace=True)
        if keep_cols is None:
            keep_cols = []
        drop_cols = ["abundance", "catchable"]
        df.drop(columns=drop_cols, inplace=True)

        rename_cols = {"name.en": "Pokemon", "id": "Dex"}
        if "enabled" in keep_cols:
            rename_cols["enabled"] = "Currently catchable"
        df.rename(columns=rename_cols, inplace=True)

        df_groupby = df.set_index("Pokemon").groupby("Chance")
        df_groupby = [
            (int(chance.split("/")[-1]), pokemons)
            for chance, pokemons in df_groupby.groups.items()
        ]
        df_groupby.sort(key=lambda x: x[0])
        df_groupby = {
            f"{round(1 / chance * 100, 4)}% or 1/{chance} ({len(pokemons)})": sorted(
                pokemons
            )
            for chance, pokemons in df_groupby
        }

        df_grouped = pd.DataFrame.from_dict(df_groupby, orient="index")
        df_grouped = df_grouped.transpose()

        contents = """## Contents
- [Pokémon chances table](#file-pokemon_chances-csv)
- [Pokémon chances table, grouped by chance](#file-pokemon_chances_grouped-csv)"""

        files = [
            gists.File(name="contents.md", content=contents),
            gists.File(name="pokemon_chances.csv", content=df.to_csv(index=False)),
            gists.File(
                name="pokemon_chances_grouped.csv",
                content=df_grouped.to_csv(index=False),
            ),
        ]
        new_gist = gists.Gist.__new__(gists.Gist)
        new_gist.files = files
        new_gist.description = description

        if gist == new_gist:
            return
        await gist.edit(files=files, description=description)

    async def format_chances_message(
        self,
        title: str,
        pokemon_dataframe: pd.DataFrame,
        *,
        gist: Optional[Union[str, gists.Gist]] = None,
        list_pokemon: bool = True,
        keep_cols: Optional[typing.List[str]] = None,
    ) -> str:
        pkm_df = pokemon_dataframe
        total_abundance = round(pkm_df["abundance"][pkm_df["catchable"] > 0].sum())

        out_of = round(self.possible_abundance / total_abundance)
        per_cent = round(1 / out_of * 100, 4)
        total_chances = f"**Total chance**: {per_cent}% or 1/{out_of}"

        if isinstance(gist, str):
            gist = await self.gists_client.get_gist(gist)

        extra = "\n"
        if list_pokemon is True:
            await self.update_chance_gist(
                pkm_df,
                description=f"Spawn chances of {title} pokémon ({len(pkm_df)}). {total_chances}",
                gist=gist,
                keep_cols=keep_cols,
            )
            all_pokemon = f"> All pokémon: <{gist.url}>"
            extra = f" (Includes all catchable forms)\n{all_pokemon}\n**Total pokemon**: {len(pkm_df)}"

        result = f"__**{title} spawn-chances**__{extra}\n{total_chances}"
        return result

    @commands.group(
        aliases=("chances",),
        help="See the chances of a single pokémon.",
        invoke_without_command=True,
    )
    async def chance(self, ctx, *, pokemon: str):
        try:
            pkm_df = self.pk.loc[self.pk["name.en"] == get_pokemon(pokemon, pk=self.pk)]
        except IndexError:
            await ctx.send(f"`{pokemon}` is not a valid pokemon!")
            return await ctx.send_help(ctx.command)

        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        async with ctx.channel.typing():
            result = await self.format_chances_message(
                ", ".join([pkm_row["name.en"] for _, pkm_row in pkm_df.iterrows()]),
                pkm_df,
                list_pokemon=False,
            )
        await ctx.send(result)
        return result

    @chance.command(name="all", help="See the chances of all pokémon in a nice table")
    async def all(self, ctx):
        pkm_df = self.pk
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        async with ctx.channel.typing():
            result = await self.format_chances_message(
                "All", pkm_df, gist=ALL_GIST
            )
        await ctx.send(result)
        return result

    @chance.command(
        name="starters",
        aliases=("starter",),
        help="See the chances of starters.",
    )
    async def _starters(self, ctx):
        pkm_df = self.pk.loc[self.pk["name.en"].isin(STARTERS)]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]
        async with ctx.channel.typing():
            result = await self.format_chances_message(
                ", ".join([pkm_row["name.en"] for _, pkm_row in pkm_df.iterrows()]),
                pkm_df,
                gist=STARTERS_GIST,
            )
        await ctx.send(result)
        return result

    @chance.command(
        name="rarity",
        help="See the chances of a rarity and the pokémon that belong to that rarity.",
    )
    async def _rarity(self, ctx, rarity):
        options = RARITY_GISTS.keys()
        for option in options:
            if rarity.lower() in option.lower():
                rarity = option
                break
        else:
            return await ctx.send(
                f'Invalid rarity provided. Valid rarities: {", ".join(options)}.'
            )

        pkm_df = self.pk.loc[self.pk[rarity.lower()] == 1]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        async with ctx.channel.typing():
            result = await self.format_chances_message(
                rarity, pkm_df, gist=RARITY_GISTS.get(rarity)
            )
        await ctx.send(result)
        return result

    @chance.command(
        name="form",
        help="See the chances of a form and the individual pokémon. Options: Alolan, Galarian & Hisuian.",
    )
    async def _form(self, ctx, form):
        options = FORM_GISTS.keys()
        for option in options:
            if form.lower() in option.lower():
                form = option
                break
        else:
            return await ctx.send(
                f'Invalid form provided. Options: {", ".join(options)}'
            )

        pkm_df = self.pk.loc[self.pk["slug"].str.endswith(form.lower()[:5])]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        async with ctx.channel.typing():
            result = await self.format_chances_message(
                form, pkm_df, gist=FORM_GISTS.get(form)
            )
        await ctx.send(result)
        return result

    @chance.command(
        name="region",
        aliases=("gen",),
        brief="See the chances of the pokémon from a region.",
        help="See the chances of the pokémon from a region. Options: Kanto/1, Johto/2, Hoenn/3, Sinnoh/4, Unova/5, Kalos/6, Alola/7, Galar/8, Hisui",
    )
    async def _region(self, ctx, region: Union[int, str]):
        options = list(REGION_GISTS.keys())
        if isinstance(region, int):
            if region < len(options):
                region = options[region - 1]
            else:
                return await ctx.send(f"Invalid generation provided. Options: 1-{len(options) - 1}")
        else:
            region = region.capitalize()

        pkm_df = self.pk.loc[self.pk["region"] == region.lower()]
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance"]]

        if len(pkm_df) == 0:
            return await ctx.send(
                f'Invalid region provided. Options: {", ".join(options)}'
            )

        async with ctx.channel.typing():
            result = await self.format_chances_message(
                f"{region} region", pkm_df, gist=REGION_GISTS.get(region)
            )
        await ctx.send(result)
        return result

    async def get_types_gist(self, type_1: str, type_2: str):
        types_gist = await self.gists_client.get_gist(TYPE_GISTS_GIST.split("/")[-1])
        file = types_gist.files[0]
        types_gists_json = json.loads(file.content)

        types_identifier = f"{type_1}-{type_2}"
        gist_link = types_gists_json.get(types_identifier, False)
        if gist_link is False:  # Check which identifier is correct
            gist_link = types_gists_json.get(f"{type_2}-{type_1}", None)

        if gist_link is None:
            gist_link = (
                await self.gists_client.create_gist(
                    files=[
                        gists.File(name="pokemon_chances.csv", content="."),
                        gists.File(name="pokemon_chances_grouped.csv", content="."),
                    ],
                    public=False,
                )
            )
            types_gists_json[types_identifier] = gist_link.url
            file.content = json.dumps(types_gists_json, indent=4)
            await types_gist.edit(files=[file])
        return gist_link

    @chance.command(
        name="type",
        aliases=("types", "ty", "t"),
        brief="See the chances of pokémon with certain type(s)",
        help="See the chances of pokémon with certain type(s). Types: Normal, Fire, Water, Grass, Flying, Fighting, Poison, Electric, Ground, Rock, Psychic, Ice, Bug, Ghost, Steel, Dragon, Dark and Fairy.",
    )
    async def _type(self, ctx, type_1: str, type_2: str = None):
        type_1 = type_1.capitalize()
        types = [type_1]
        if not type_2:
            msg = type_1
            pkm_df = self.pk.loc[
                (self.pk["type.0"] == type_1) | (self.pk["type.1"] == type_1)
            ]
        else:
            type_2 = type_2.capitalize()
            types.append(type_2)
            msg = " & ".join((type_1, type_2))
            pkm_df = self.pk.loc[
                ((self.pk["type.0"] == type_1) & (self.pk["type.1"] == type_2))
                | ((self.pk["type.0"] == type_2) & (self.pk["type.1"] == type_1))
            ]

        if len(pkm_df) == 0:
            return await ctx.send(
                f'Invalid type(s) provided `{"` and `".join(types)}`.'
            )
        pkm_df = pkm_df.loc[pkm_df["catchable"] > 0]
        if len(pkm_df) == 0:
            return await ctx.send(
                f'No catchable pokémon found with type(s) `{"` and `".join(types)}`'
            )
        pkm_df.rename(columns={"type.0": "Type 1", "type.1": "Type 2"}, inplace=True)
        pkm_df = pkm_df.loc[
            :, ["id", "name.en", "Type 1", "Type 2", "catchable", "abundance"]
        ]

        async with ctx.channel.typing():
            result = await self.format_chances_message(
                f"{msg} Type(s)",
                pkm_df,
                gist=await self.get_types_gist(type_1, type_2),
            )
        await ctx.send(result)
        return result

    @chance.command(
        name="event", aliases=("ev",), help="Chances of pokemon of the current event"
    )
    async def event(self, ctx):
        pkm_df = self.pk.loc[self.pk["event"] > 0]
        if len(pkm_df) == 0:
            await ctx.send("No currently catchable event pokemon")
            return ""
        pkm_df = pkm_df.loc[:, ["id", "name.en", "catchable", "abundance", "enabled"]]
        pkm_df["enabled"] = pkm_df["enabled"] > 0

        async with ctx.channel.typing():
            result = await self.format_chances_message(
                "Event", pkm_df, keep_cols=["enabled"], gist=EVENT_GIST
            )
        await ctx.send(result)
        return result

    @commands.is_owner()
    @chance.command()
    async def update_all(self, ctx: commands.Context):
        bot = ctx.bot

        chance = bot.get_command("chance")

        chance_all = chance.get_command("all")
        all = pattern.match(await ctx.invoke(chance_all))

        chance_starters = chance.get_command("starters")
        starters = pattern.match(await ctx.invoke(chance_starters))

        rarity = chance.get_command("rarity")
        mythical = pattern.match(await ctx.invoke(rarity, "Mythical"))
        await asyncio.sleep(DELAY)
        legendary = pattern.match(await ctx.invoke(rarity, "Legendary"))
        await asyncio.sleep(DELAY)
        ub = pattern.match(await ctx.invoke(rarity, "Ultra_beast"))
        await asyncio.sleep(DELAY)

        cmd = chance.get_command("form")
        alolan = pattern.match(await ctx.invoke(cmd, "al"))
        await asyncio.sleep(DELAY)
        galarian = pattern.match(await ctx.invoke(cmd, "gal"))
        await asyncio.sleep(DELAY)
        hisuian = pattern.match(await ctx.invoke(cmd, "his"))
        await asyncio.sleep(DELAY)

        cmd = chance.get_command("region")
        regions = []
        for region in list(REGION_GISTS.keys())[:-1]:
            regions.append(pattern.match(await ctx.invoke(cmd, region)))
            await asyncio.sleep(DELAY)
        hisui = pattern.match(await ctx.invoke(cmd, "hisui"))

        cmd = chance.get_command("event")
        event = pattern.match(await ctx.invoke(cmd))
        event_msg = (
            f'**Current event pokemon chances** (?tag `ev%`) = {event.group("chance_per")}%'
            if event is not None
            else ""
        )

        regions_msg = "\n".join(
            [
                f"""**{idx + 1}\. {region.group("title")}** [`{region.group("total")}`] = {region.group("chance_per")}% ({region.group("chance")})
- <{REGION_GISTS[region.group("title").split(" ")[0]]}>"""
                for idx, region in enumerate(regions)
            ]
        )

        chance_msg = f"""__**Spawn chances:**__
> __Recent updates (Last update: {discord.utils.format_dt(discord.utils.utcnow(), "f")})__
> - Updated chances

{event_msg}

**All pokémon** - <{ALL_GIST}>

**Starter pokémon** = {starters.group("chance_per")}% ({starters.group("chance")})

**Mythical pokémon** (?tag `my%`) = {mythical.group("chance_per")}%
**Legendary pokémon** (?tag `leg%`) = {legendary.group("chance_per")}%
**Ultra beast pokémon** (?tag `ub%`) = {ub.group("chance_per")}%

**Alolan pokémon** (?tag `al%`) = {alolan.group("chance_per")}%
**Galarian pokémon** (?tag `gal%`) = {galarian.group("chance_per")}%
**Hisuian pokémon** (?tag `his%`) = {hisuian.group("chance_per")}%

**Regions** - ?tag `reg%`

✨ **Shiny** (Chance of shiny on catch without any modifiers such as shiny-charm or shinyhunt) = 0.024% (1/4096)
✨📿 **Shiny with shiny-charm but no shinyhunt streak** = 0.029% (1/3413.3)
✨🔢 **Shiny with shinyhunt streak** = `?tag shhr`"""

        await ctx.send(chance_msg)

        reg_msg = f"""__**Regional spawn-chances**__ (Includes all catchable forms)

{regions_msg}
**4\.1\. Hisui** [`{hisui.group("total")}`] = {hisui.group("chance_per")}% ({hisui.group("chance")})
- <{REGION_GISTS[hisui.group("title").split(" ")[0]]}>"""

        await ctx.send(reg_msg)


async def setup(bot):
    await bot.add_cog(PoketwoChances(bot))
