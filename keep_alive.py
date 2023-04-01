import os
from flask import Flask
from threading import Thread
import random
import json

from replit import db


app = Flask("")


@app.route("/")
def home():
    return "Im in!"


style = """color: #b6bac0; background-color: #313338; text-align: center; font-family: 'Arial Black'; font-style: normal;"""

@app.route("/afd/random")
def afd_random_pokemon():
    afd_random = db["afd_random"]
    unclaimed = json.loads(afd_random)
    if len(unclaimed) == 0:
        return "No remaining pokemon."

    dex, pkm_dict = random.choice(list(unclaimed.items()))

    name = pkm_dict["name"]
    image_url = pkm_dict["image_url"]

    return f'''
<body style="{style}">
    <h1 style="color: #74c49b; font-size: 50px;">Random Unclaimed AFD Pokemon Picker</h1>
    Total Unclaimed Pokemon: {len(unclaimed)}
    <div style="background-color: #232428; border-radius: 10px; border: 1px solid black; padding: 10px;">
        <p style="color: #b6bac0;">Your random pokemon: 
        <br>
        <sub>(will not be removed from the list until claimed on the sheet)<sub></p>
        <h2 style="font-size: 30px; text-decoration: underline;">{name}</h2>
        <img src={image_url}>
    </div>
    <p style="font-size: 10px;">P.S. I know this looks bad</p>
</body>
'''


def run():
    app.run(host="0.0.0.0", port=6969)


def keep_alive():
    # Make it so it only runs on replit
    if not os.getenv("REPL_ID"):
        return
    t = Thread(target=run)
    t.start()
