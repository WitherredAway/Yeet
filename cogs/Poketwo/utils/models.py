"""
Copyright (C) 2020-present oliver-ni / Pokétwo

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 3 of
the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see <https://www.gnu.org/licenses>.
"""
import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
from urllib.parse import urljoin

import pandas as pd

from cogs.Poketwo.utils.utils import deaccent

from .constants import GENDER_RATES


class UnregisteredError(Exception):
    pass


class UnregisteredDataManager:
    pass

# Stats


@dataclass
class Stats:
    hp: int
    atk: int
    defn: int
    satk: int
    sdef: int
    spd: int


# Species


@dataclass
class Species:
    id: int
    enabled: bool
    names: List[Tuple[str, str]]
    slug: str
    base_stats: Stats
    height: int
    weight: int
    dex_number: int
    catchable: bool
    types: List[str]
    abundance: int
    gender_rate: int
    has_gender_differences: int
    description: str = None
    mega_id: int = None
    mega_x_id: int = None
    mega_y_id: int = None
    mythical: bool = False
    legendary: bool = False
    ultra_beast: bool = False
    event: bool = False
    is_form: bool = False
    form_item: int = None
    region: str = None
    art_credit: str = None

    instance: Any = UnregisteredDataManager()

    def __post_init__(self):
        if len(self.names) > 0:
            self.name = next(filter(lambda x: x[0] == "🇬🇧", self.names))[1]
        else:
            self.name = self.slug

    def __str__(self):
        return self.name

    def __eq__(self, other) -> bool:
        if isinstance(other, Species):
            return self.id == other.id
        return False

    def __hash__(self) -> hash:
        return hash(self.id)

    @cached_property
    def gender_ratios(self):
        return GENDER_RATES[self.gender_rate]

    @cached_property
    def default_gender(self) -> Literal["Unknown", "Male", "Female"] | None:
        if self.gender_rate == -1:
            return "Unknown"

        if 100 in self.gender_ratios:  # If species is exclusively one gender
            always_male = self.gender_ratios[0] == 100
            if always_male:
                return "Male"
            else:
                return "Female"
        else:  # If both male and female are possible
            return None  # There is no default

    @cached_property
    def mega(self):
        if self.mega_id is None:
            return None

        return self.instance.pokemon[self.mega_id]

    @cached_property
    def mega_x(self):
        if self.mega_x_id is None:
            return None

        return self.instance.pokemon[self.mega_x_id]

    @cached_property
    def mega_y(self):
        if self.mega_y_id is None:
            return None

        return self.instance.pokemon[self.mega_y_id]

    @cached_property
    def image_url(self):
        return self.instance.asset(f"/images/{self.id}.png")

    @cached_property
    def shiny_image_url(self):
        return self.instance.asset(f"/shiny/{self.id}.png")

    @cached_property
    def image_url_female(self):
        if self.has_gender_differences == 1:
            return self.instance.asset(f"/images/{self.id}F.png")

    @cached_property
    def shiny_image_url_female(self):
        if self.has_gender_differences == 1:
            return self.instance.asset(f"/shiny/{self.id}F.png")

    @cached_property
    def correct_guesses(self):
        extra = []

        if self.is_form or self.event:
            extra.extend(self.instance.pokemon[self.dex_number].correct_guesses)

        if "nidoran" in self.slug:
            extra.append("nidoran")

        # Elsa Galarian Ponyta
        if self.id == 50053:
            extra.extend(self.instance.pokemon[10159].correct_guesses)

        # Halloween Alolan Ninetales
        if self.id == 50076:
            extra.extend(self.instance.pokemon[10104].correct_guesses)

        # Pride Gardevoir & Delphox
        if self.id == 50107:
            # can't set two dex_numbers
            extra.extend(self.instance.pokemon[655].correct_guesses)
            extra.append("pride gardevoir")
            extra.append("pride delphox")

        # Pyjama Plusle & Minun
        if self.id == 50149:
            # can't set two dex_numbers
            extra.extend(self.instance.pokemon[312].correct_guesses)
            extra.append("christmas minun")

        # Santa Hisuian Zorua
        if self.id == 50145:
            extra.extend(self.instance.pokemon[10230].correct_guesses)
            extra.append("christmas zorua")

        # Reindeer Deerling
        if self.id == 50147:
            extra.append("christmas deerling")

        return extra + [deaccent(x.lower()) for _, x in self.names] + [self.slug]

    @cached_property
    def evolution_text(self):
        if self.is_form and self.form_item is not None:
            species = self.instance.pokemon[self.dex_number]
            return f"{self.name} transforms from {species}."

        if self.evolution_from is not None and self.evolution_to is not None:
            return (
                f"{self.name} {self.evolution_from.text} and {self.evolution_to.text}."
            )
        elif self.evolution_from is not None:
            return f"{self.name} {self.evolution_from.text}."
        elif self.evolution_to is not None:
            return f"{self.name} {self.evolution_to.text}."
        else:
            return None

    def __repr__(self):
        return f"<Species: {self.name}>"

    def get_image_url(
        self,
        shiny: Optional[bool] = False,
        gender: Optional[Literal["unknown", "male", "female"]] = None
    ) -> str:

        if gender is not None:
            gender = gender.lower()

        attr_parts = ["image_url"]

        if shiny:
            attr_parts.insert(0, "shiny")

        if self.has_gender_differences:
            match gender:
                case "female":
                    attr_parts.append(gender)

        attr = "_".join(attr_parts)
        return getattr(self, attr)


def get_pokemon(instance, data: List[Dict[str, Any]]) -> Dict[int, Species]:
    species = {x["id"]: x for x in data}

    pokemon = {}

    for row in species.values():
        types = []
        if "type.0" in row:
            types.append(row["type.0"])
        if "type.1" in row:
            types.append(row["type.1"])

        names = []

        if "name.ja" in row:
            names.append(("🇯🇵", row["name.ja"]))

        if "name.ja_r" in row:
            names.append(("🇯🇵", row["name.ja_r"]))

        if "name.ja_t" in row and row["name.ja_t"] != row.get("name.ja_r"):
            names.append(("🇯🇵", row["name.ja_t"]))

        if "name.en" in row:
            names.append(("🇬🇧", row["name.en"]))

        if "name.en2" in row:
            names.append(("🇬🇧", row["name.en2"]))

        if "name.de" in row:
            names.append(("🇩🇪", row["name.de"]))

        if "name.fr" in row:
            names.append(("🇫🇷", row["name.fr"]))

        pokemon[row["id"]] = Species(
            id=row["id"],
            enabled="enabled" in row,
            names=names,
            slug=row["slug"],
            base_stats=Stats(
                row["base.hp"],
                row["base.atk"],
                row["base.def"],
                row["base.satk"],
                row["base.sdef"],
                row["base.spd"],
            ),
            types=types,
            height=int(row["height"]) / 10,
            weight=int(row["weight"]) / 10,
            mega_id=row["evo.mega"] if "evo.mega" in row else None,
            mega_x_id=row["evo.mega_x"] if "evo.mega_x" in row else None,
            mega_y_id=row["evo.mega_y"] if "evo.mega_y" in row else None,
            catchable="catchable" in row,
            dex_number=row["dex_number"],
            abundance=row["abundance"] if "abundance" in row else 0,
            gender_rate=row["gender_rate"] if "gender_rate" in row else -1,
            has_gender_differences=row["has_gender_differences"] if "has_gender_differences" in row else 0,
            description=row.get("description", None),
            mythical="mythical" in row,
            legendary="legendary" in row,
            ultra_beast="ultra_beast" in row,
            event="event" in row,
            is_form="is_form" in row,
            form_item=row["form_item"] if "form_item" in row else None,
            region=row["region"],
            art_credit=row.get("credit"),
            instance=instance,
        )

    return pokemon


@dataclass
class DataManager:
    def __init__(self, csv_data: csv.DictReader):
        self.csv_data = csv_data
        self.pokemon = get_pokemon(self, csv_data)

    @cached_property
    def df(self) -> pd.DataFrame:
        return pd.DataFrame.from_records(self.csv_data)

    @cached_property
    def df_catchable(self) -> pd.DataFrame:
        return self.df[self.df["catchable"] > 0]

    def asset(self, path):
        base_url = getattr(self, "assets_base_url", "https://cdn.poketwo.net")
        return urljoin(base_url, path)

    def all_pokemon(self, predicate: Optional[Callable[[Species], bool]] = None) -> List[Species]:
        base_predicate = lambda s: s.enabled
        all_pokemon = list(filter(base_predicate, self.pokemon.values()))
        if predicate is not None:
            all_pokemon = list(filter(predicate, all_pokemon))

        return all_pokemon

    @cached_property
    def list_alolan(self):
        return [
            10091,
            10092,
            10093,
            10100,
            10101,
            10102,
            10103,
            10104,
            10105,
            10106,
            10107,
            10108,
            10109,
            10110,
            10111,
            10112,
            10113,
            10114,
            10115,
            50076,
        ]

    @cached_property
    def list_galarian(self):
        return [
            10158,
            10159,
            10160,
            10161,
            10162,
            10163,
            10164,
            10165,
            10166,
            10167,
            10168,
            10169,
            10170,
            10171,
            10172,
            10173,
            10174,
            10175,
            10176,
            10177,
            50053,
        ]

    @cached_property
    def list_hisuian(self):
        return [
            10221,
            10222,
            10223,
            10224,
            10225,
            10226,
            10227,
            10228,
            10229,
            10230,
            10231,
            10232,
            10233,
            10234,
            10235,
            10236,
            10237,
            10238,
            10239,
            50145,
        ]

    @cached_property
    def list_paldean(self):
        return [
            10250,
            10251,
            10252,
            10253,
        ]

    @cached_property
    def list_paradox(self):
        return [
            984,
            985,
            986,
            987,
            988,
            989,
            990,
            991,
            992,
            993,
            994,
            995,
            1005,
            1006,
            1007,
            1008,
            1009,
            1010,
        ]

    @cached_property
    def list_mythical(self):
        return [v.id for v in self.pokemon.values() if v.mythical]

    @cached_property
    def list_legendary(self):
        return [v.id for v in self.pokemon.values() if v.legendary]

    @cached_property
    def list_ub(self):
        return [v.id for v in self.pokemon.values() if v.ultra_beast]

    @cached_property
    def list_event(self):
        return [v.id for v in self.pokemon.values() if v.event]

    @cached_property
    def list_mega(self):
        return (
            [v.mega_id for v in self.pokemon.values() if v.mega_id is not None]
            + [v.mega_x_id for v in self.pokemon.values() if v.mega_x_id is not None]
            + [v.mega_y_id for v in self.pokemon.values() if v.mega_y_id is not None]
        )

    @cached_property
    def species_id_by_type_index(self):
        ret = defaultdict(list)
        for pokemon in self.pokemon.values():
            for type in pokemon.types:
                ret[type.lower()].append(pokemon.id)
        return dict(ret)

    def list_type(self, type: str):
        return self.species_id_by_type_index.get(type.lower(), [])

    @cached_property
    def species_id_by_region_index(self):
        ret = defaultdict(list)
        for pokemon in self.pokemon.values():
            ret[pokemon.region.lower()].append(pokemon.id)
        return dict(ret)

    def list_region(self, region: str):
        return self.species_id_by_region_index.get(region.lower(), [])

    @cached_property
    def species_by_dex_number_index(self):
        ret = defaultdict(list)
        for pokemon in self.pokemon.values():
            ret[pokemon.id].append(pokemon)
            if pokemon.id != pokemon.dex_number:
                ret[pokemon.dex_number].append(pokemon)
        return dict(ret)

    def all_species_by_number(self, number: int) -> Species:
        return self.species_by_dex_number_index.get(number, [])

    def all_species_by_name(self, name: str) -> Species:
        return self.species_by_name_index.get(
            deaccent(name.lower().replace("′", "'")), []
        )

    def find_all_matches(self, name: str) -> Species:
        return [
            y.id
            for x in self.all_species_by_name(name)
            for y in self.all_species_by_number(x.id)
        ]

    def species_by_number(self, number: int) -> Species:
        try:
            return self.pokemon[number]
        except KeyError:
            return None

    @cached_property
    def species_by_name_index(self):
        ret = defaultdict(list)
        for pokemon in self.pokemon.values():
            for name in pokemon.correct_guesses:
                ret[name].append(pokemon)
        return dict(ret)

    def species_by_name(self, name: str) -> Species:
        try:
            st = deaccent(name.lower().replace("′", "'"))
            return self.species_by_name_index[st][0]
        except (KeyError, IndexError):
            return None

    def random_spawn(self, rarity="normal"):
        if rarity == "mythical":
            pool = [x for x in self.all_pokemon() if x.catchable and x.mythical]
        elif rarity == "legendary":
            pool = [x for x in self.all_pokemon() if x.catchable and x.legendary]
        elif rarity == "ultra_beast":
            pool = [x for x in self.all_pokemon() if x.catchable and x.ultra_beast]
        else:
            pool = [x for x in self.all_pokemon() if x.catchable]

        x = random.choices(pool, weights=[x.abundance for x in pool], k=1)[0]

        return x

    @cached_property
    def spawn_weights(self):
        return [p.abundance for p in self.pokemon.values()]
