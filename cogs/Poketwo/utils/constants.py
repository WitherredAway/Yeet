import os


POKETWO_ID = 716390085896962058
POKEMON_GIST_URL = (
    # "https://raw.githubusercontent.com/poketwo/data/master/csv/pokemon.csv"
    os.getenv("POKEMON_GIST_URL")
)
IMAGE_URL = os.getenv("POKETWO_IMAGE_SERVER_API")

GENDER_RATES = {
    0: [100, 0],
    1: [87.5, 12.5],
    2: [75, 25],
    4: [50, 50],
    6: [25, 75],
    7: [12.5, 87.5],
    8: [0, 100],
}