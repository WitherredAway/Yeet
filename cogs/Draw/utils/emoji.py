from typing import Optional, TypeVar, Union

import discord
from PIL import Image
from pilmoji import Pilmoji

from .constants import FONT


ADD_EMOJIS_EMOJI = "<:emojismiley:1056857231125123152>"
SET_CURSOR_EMOJI = "<:ABCD:1032565203608547328>"
ADD_COLOURS_EMOJI = "🏳️‍🌈"
MIX_COLOURS_EMOJI = "🔀"
AUTO_DRAW_EMOJI = "<:auto_draw:1032565224903016449>"
SELECT_EMOJI = "<:select_tool:1037847279169704028>"
SAVE_EMOJI = "<:save:1105025339861766195>"


def draw_emoji(emoji: str) -> Image:
    with Image.new("RGBA", (128, 128), (255, 255, 255, 0)) as image:
        with Pilmoji(image) as pilmoji:
            pilmoji.text(
                xy=(0, 0),
                text=emoji,
                fill=(0, 0, 0),
                font=FONT(1),
                spacing=0,
                emoji_scale_factor=130,
                emoji_position_offset=(-1, -1),
            )
        return image


class SentEmoji:
    def __init__(
        self,
        *,
        emoji: Union[discord.Emoji, discord.PartialEmoji],
        index: Optional[int] = None,
    ):
        self.emoji = emoji
        self.index = index

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} emoji={self.emoji!r} index={self.index} emoji_type={self.emoji_type}>"

    def __str__(self) -> str:
        return str(self.emoji)


A = TypeVar("A", bound="AddedEmoji")


class AddedEmoji(SentEmoji):
    def __init__(
        self,
        *,
        sent_emoji: SentEmoji,
        emoji: Union[discord.Emoji, discord.PartialEmoji],
        status: Optional[str] = None,
        name: Optional[str] = None,
    ):
        self.sent_emoji = sent_emoji
        self.emoji = emoji
        self.status = status
        self.name = name or emoji.name

        self.emoji.name = self.name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} sent_emoji={self.sent_emoji!r} emoji={self.emoji!r} status={self.status} name={self.name}>"

    @property
    def id(self) -> int:
        return self.emoji.id

    @id.setter
    def id(self, value: int):
        self.emoji.id = value

    @classmethod
    def from_option(
        cls,
        option: discord.SelectOption,
        *,
        sent_emoji: SentEmoji,
        status: Optional[str] = None,
    ) -> A:
        return cls(status=status, emoji=option.emoji, sent_emoji=sent_emoji)
