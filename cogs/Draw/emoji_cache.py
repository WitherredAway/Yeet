from __future__ import annotations

import typing
import discord

from typing import Dict, Optional, Union, List


if typing.TYPE_CHECKING:
    from main import Bot


class EmojiCache:
    def __init__(self, *, bot: Bot) -> None:
        self.bot = bot

        self.cache: Dict[str, Union[discord.Emoji, discord.PartialEmoji]] = {}

    def get_emoji(
        self, name: str
    ) -> Optional[Union[discord.Emoji, discord.PartialEmoji]]:
        return self.cache.get(name)

    def get_emoji_from_id(
        self, id: int
    ) -> Optional[Union[discord.Emoji, discord.PartialEmoji]]:
        for name, emoji in self.cache.items():
            if emoji.id == id:
                return emoji
        return None

    def add_emoji(self, emoji: Union[discord.Emoji, discord.PartialEmoji]) -> None:
        self.cache[emoji.name] = emoji

    def add_emojis(
        self, emoji_list: List[Union[discord.Emoji, discord.PartialEmoji]]
    ) -> None:
        for emoji in emoji_list:
            self.add_emoji(emoji)

    def remove_emoji(self, emoji: Union[discord.Emoji, discord.PartialEmoji]) -> bool:
        for name, emoji_cache in self.cache.items():
            if emoji is emoji_cache:
                del self.cache[name]
                return True
        else:
            if emoji.name in self.cache:
                del self.cache[emoji.name]
                return True
        return False

    def clear(self) -> None:
        self.cache.clear()
