import pandas as pd

from cogs.utils.utils import normalize


def get_pokemon(name: str, *, pk: pd.DataFrame) -> str:
    name = normalize(name.replace("’", "'").replace("′", "'").casefold())
    return pk.loc[
        (pk["slug"].apply(normalize) == name)
        | (pk["name.ja"].apply(normalize) == name)
        | (pk["name.ja_r"].apply(normalize) == name)
        | (pk["name.ja_t"].apply(normalize) == name)
        | (pk["name.en"].apply(normalize) == name)
        | (pk["name.en2"].apply(normalize) == name)
        | (pk["name.de"].apply(normalize) == name)
        | (pk["name.fr"].apply(normalize) == name),
        "name.en",
    ].values[0]
