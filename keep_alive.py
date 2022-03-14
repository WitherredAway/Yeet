from flask import Flask
from threading import Thread
import random


app = Flask("")


@app.route("/")
def home():
    return "Im in!"


def run():
    app.run(host="0.0.0.0", port=random.randint(7000, 8000))


def keep_alive():
    t = Thread(target=run)
    t.start()
