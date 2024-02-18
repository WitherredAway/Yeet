import csv
from io import StringIO
from typing import IO, Any, Dict, List
import unicodedata
import pandas as pd


def deaccent(text):
    text = str(text).casefold()

    norm = unicodedata.normalize("NFD", text)
    result = "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFKC", result)


def get_pokemon(name: str, *, pk: pd.DataFrame) -> str:
    name = deaccent(name.replace("’", "'").replace("′", "'").casefold())
    return pk.loc[
        (pk["slug"].apply(deaccent) == name)
        | (pk["name.ja"].apply(deaccent) == name)
        | (pk["name.ja_r"].apply(deaccent) == name)
        | (pk["name.ja_t"].apply(deaccent) == name)
        | (pk["name.en"].apply(deaccent) == name)
        | (pk["name.en2"].apply(deaccent) == name)
        | (pk["name.de"].apply(deaccent) == name)
        | (pk["name.fr"].apply(deaccent) == name),
        "name.en",
    ].values[0]


def isnumber(v):
    try:
        int(v)
    except ValueError:
        return False
    return True


def get_data_from(stream: IO[str]) -> List[Dict[str, Any]]:
    reader = csv.DictReader(stream)
    data = list(
        {k: int(v) if isnumber(v) else v for k, v in row.items() if v != ""}
        for row in reader
    )
    return data
