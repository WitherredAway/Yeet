from __future__ import annotations

import asyncio
from functools import cached_property
import io
from typing import Optional, Union, List, Tuple

import numpy as np
import discord
from PIL import Image


from .emoji import draw_emoji

from .regexes import HEX_REGEX


class Colour:
    # RGB_A accepts RGB values and an optional Alpha value
    def __init__(self, RGB_A: Tuple[int, int, int, Optional[int]]):
        self.RGBA = RGB_A if len(RGB_A) == 4 else (*RGB_A, 255)
        self.RGB = self.RGBA[:3]
        self.R, self.G, self.B, self.A = self.RGBA

        self.loop = asyncio.get_running_loop()

    @cached_property
    def hex(self) -> str:
        return "%02x%02x%02x%02x" % self.RGBA

    @cached_property
    def base_emoji(self) -> Image:
        return draw_emoji("🟪")

    async def to_bytes(self) -> bytes:
        return await self.loop.run_in_executor(None, self._to_bytes)

    def _to_bytes(self) -> bytes:
        image = self._to_image()
        with io.BytesIO() as image_bytes:
            image.save(image_bytes, "PNG")
            # image_bytes.seek(0)
            return image_bytes.getvalue()

    async def to_file(self) -> discord.File:
        return await self.loop.run_in_executor(None, self._to_file)

    def _to_file(self) -> discord.File:
        image_bytes = io.BytesIO(self._to_bytes())
        return discord.File(image_bytes, filename=f"{self.hex}.png")

    async def to_image(self, base_emoji: Optional[str] = None) -> Image:
        return await self.loop.run_in_executor(None, self._to_image, base_emoji)

    def _to_image(self, base_emoji: Optional[str] = None) -> Image:
        # If you pass in an emoji, it uses that as base
        # Else it uses the base_emoji property which uses 🟪
        base_emoji = draw_emoji(base_emoji) if base_emoji else self.base_emoji
        data = np.array(base_emoji)
        r, g, b, a = data.T

        data[..., :-1][a != 0] = self.RGB

        # Set the alpha relatively, to respect individual alpha values
        alpha_percent = self.A / 255
        data[..., -1] = alpha_percent * data[..., -1]

        image = Image.fromarray(data)

        return image

    async def to_emoji(self, guild: discord.Guild):
        return await guild.create_custom_emoji(
            name=self.hex, image=await self.to_bytes()
        )

    @classmethod
    async def from_emoji(
        cls, emoji: Union[str, discord.Emoji, discord.PartialEmoji]
    ) -> Colour:
        if isinstance(emoji, str):
            emoji: discord.PartialEmoji = discord.PartialEmoji.from_str(emoji)
        loop = asyncio.get_running_loop()
        image = await loop.run_in_executor(None, draw_emoji, str(emoji))
        colours = [
            colour
            for colour in sorted(
                image.getcolors(image.size[0] * image.size[1]),
                key=lambda c: c[0],
                reverse=True,
            )
            if colour[-1][-1] != 0
        ]

        return cls(colours[0][1])

    @classmethod
    async def from_attachment(
        cls, attachment: discord.Attachment, *, n_colours: Optional[int] = 5
    ) -> Colour:
        image = Image.open(io.BytesIO(await attachment.read()))
        colours: Tuple[int, Tuple[int, int, int]] = [
            colour
            for colour in sorted(
                image.getcolors(image.size[0] * image.size[1]),
                key=lambda c: c[0],
                reverse=True,
            )
            if colour[-1][-1] != 0
        ]

        colour_objs = []
        for i in range(n_colours):
            colour_objs.append(cls(colours[min(len(colours), i)][-1]))

        return colour_objs

    @classmethod
    def from_hex(cls, hex: str) -> Colour:
        if (match := HEX_REGEX.match(hex)) is None:
            raise ValueError("Invalid hex code provided")

        RGBA = (
            int(match.group("red"), 16),
            int(match.group("green"), 16),
            int(match.group("blue"), 16),
            int(match.group("alpha") or "ff", 16),
        )

        return cls(RGBA)

    @classmethod
    def mix_colours(cls, colours: List[Tuple[Union[int, Colour], ...]]) -> Colour:
        colours = [
            colour.RGBA if isinstance(colour, Colour) else colour for colour in colours
        ]
        total_weight = len(colours)

        return cls(
            tuple(round(sum(colour) / total_weight) for colour in zip(*colours)),
        )
