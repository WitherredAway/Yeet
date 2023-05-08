from PIL import ImageFont

import discord

from helpers.constants import u200b
from cogs.utils.utils import invert_dict


TRANSPARENT_EMOJI = "<:e:1104930506698653706>"
TRANSPARENT_CURSOR_EMOJI = "<:tc:1104939609240113162>"


def base_colour_options():
    return [
        discord.SelectOption(label="Transparent", emoji=TRANSPARENT_EMOJI, value=TRANSPARENT_EMOJI),
        discord.SelectOption(label="Red", emoji="🟥", value="🟥"),
        discord.SelectOption(label="Orange", emoji="🟧", value="🟧"),
        discord.SelectOption(label="Yellow", emoji="🟨", value="🟨"),
        discord.SelectOption(label="Green", emoji="🟩", value="🟩"),
        discord.SelectOption(label="Blue", emoji="🟦", value="🟦"),
        discord.SelectOption(label="Purple", emoji="🟪", value="🟪"),
        discord.SelectOption(label="Brown", emoji="🟫", value="🟫"),
        discord.SelectOption(label="Black", emoji="⬛", value="⬛"),
        discord.SelectOption(label="White", emoji="⬜", value="⬜"),
    ]


MIN_HEIGHT_OR_WIDTH = 5
MAX_HEIGHT_OR_WIDTH = 17


def base_number_options():
    return [
        discord.SelectOption(label=f"{n}", value=n)
        for n in range(MIN_HEIGHT_OR_WIDTH, MAX_HEIGHT_OR_WIDTH + 1)
    ]


ROW_ICONS_DICT = {
    "🇦": "<:aa:799628816846815233>",
    "🇧": "<:bb:799628882713509891>",
    "🇨": "<:cc:799620822716383242>",
    "🇩": "<:dd:799621070319255572>",
    "🇪": "<:ee:799621103030894632>",
    "🇫": "<:ff:799621133174571008>",
    "🇬": "<:gg:799621170450137098>",
    "🇭": "<:hh:799621201621811221>",
    "🇮": "<:ii:799621235226050561>",
    "🇯": "<:jj:799621266842583091>",
    "🇰": "<:kk:799621296408887357>",
    "🇱": "<:ll:799621320408301638>",
    "🇲": "<:mm:799621344740114473>",
    "🇳": "<:nn:799621367297343488>",
    "🇴": "<:oo:799628923260370945>",
    "🇵": "<:pp:799621387219369985>",
    "🇶": "<:qq:799621417049260042>",
}

ROW_ICONS = tuple(ROW_ICONS_DICT.keys())

COLUMN_ICONS_DICT = {
    "0️⃣": "<:00:1000010892500537437>",
    "1️⃣": "<:111:1000010893981143040>",
    "2️⃣": "<:22:1000010895331692555>",
    "3️⃣": "<:33:1000010896946499614>",
    "4️⃣": "<:44:1000010898213195937>",
    "5️⃣": "<:55:1000010899714740224>",
    "6️⃣": "<:66:1000010901744791653>",
    "7️⃣": "<:77:1000010902726262857>",
    "8️⃣": "<:88:1000010904240402462>",
    "9️⃣": "<:99:1000010905276403773>",
    "🔟": "<:1010:1000011148537626624>",
    "<:11:1032564324281098240>": "<:1111:1000011153226874930>",
    "<:12:1032564339946823681>": "<:1212:1000011154262851634>",
    "<:13:1032564356380098630>": "<:1313:1000011155391131708>",
    "<:14:1032564734609862696>": "<:1414:1000011156787834970>",
    "<:15:1032564783850983464>": "<:1515:1000011158348120125>",
    "<:16:1032564935412174868>": "<:1616:1000011159623192616>",
}

COLUMN_ICONS = tuple(COLUMN_ICONS_DICT.keys())


CURSOR = {
    TRANSPARENT_EMOJI: TRANSPARENT_CURSOR_EMOJI,
    "🟥": "🔴",
    "🟧": "🟠",
    "🟨": "🟡",
    "🟩": "🟢",
    "🟦": "🔵",
    "🟪": "🟣",
    "🟫": "🟤",
    "⬛": "⚫",
    "⬜": "⚪",
}

BG_EMOJIS_RGBA = {
    TRANSPARENT_EMOJI: (0, 0, 0, 0),
    "🟥": (205, 58, 69, 255),
    "🟧": (231, 151, 53, 255),
    "🟨": (245, 207, 106, 255),
    "🟩": (134, 178, 98, 255),
    "🟦": (107, 172, 234, 255),
    "🟪": (168, 145, 211, 255),
    "🟫": (183, 110, 83, 255),
    "⬛": (42, 48, 55, 255),
    "⬜": (231, 232, 232, 255),
}


inv_CURSOR = invert_dict(CURSOR)


LETTER_TO_NUMBER = {
    "A": 0,
    "B": 1,
    "C": 2,
    "D": 3,
    "E": 4,
    "F": 5,
    "G": 6,
    "H": 7,
    "I": 8,
    "J": 9,
    "K": 10,
    "L": 11,
    "M": 12,
    "N": 13,
    "O": 14,
    "P": 15,
    "Q": 16,
}


ALPHABETS = tuple(LETTER_TO_NUMBER.keys())
NUMBERS = tuple(LETTER_TO_NUMBER.values())


FONT = lambda size: ImageFont.truetype("helpers/fonts/arial.ttf", size)

PADDING = (" " + u200b) * 6
