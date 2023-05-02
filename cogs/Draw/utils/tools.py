from __future__ import annotations

import typing
from typing import Optional, Tuple

import discord
import numpy as np

from .constants import CURSOR
from .colour import Colour

if typing.TYPE_CHECKING:
    from main import Bot
    from ..draw import Board, DrawView


class Tool(discord.ui.Button):
    """A template class for each of the tools"""

    def __init__(self, view: DrawView, *, primary: Optional[bool] = True):
        super().__init__(
            emoji=self.emoji,
            style=discord.ButtonStyle.green
            if primary is True
            else discord.ButtonStyle.grey,
        )

        self._view: DrawView = view
        self.view: DrawView
        self.board: Board = self.view.board
        self.bot: Bot = self.view.bot

    @property
    def name(self) -> str:
        return None

    @property
    def emoji(self) -> str:
        return None

    @property
    def description(self) -> str:
        return None

    @property
    def autouse(self) -> bool:
        return False

    async def use(self, *, interaction: discord.Interaction) -> bool:
        """The method that is called when the tool is used"""
        pass

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if await self.use(interaction=interaction):
            await self.view.edit_message(interaction)


class BrushTool(Tool):
    @property
    def name(self) -> str:
        return "Brush"

    @property
    def emoji(self) -> str:
        return "<:brush:1056853866563506176>"

    @property
    def description(self) -> str:
        return "Draw where the cursor is"

    async def use(self, *, interaction: discord.Interaction) -> bool:
        """The method that is called when the tool is used"""
        return self.board.draw(self.board.cursor)


class EraseTool(Tool):
    @property
    def name(self) -> str:
        return "Eraser"

    @property
    def emoji(self) -> str:
        return "<:eraser:1056853917973094420>"

    @property
    def description(self) -> str:
        return "Erase where the cursor is"

    async def use(self, *, interaction: discord.Interaction) -> bool:
        """The method that is called when the tool is used"""
        return self.board.draw(self.board.background)


class EyedropperTool(Tool):
    @property
    def name(self) -> str:
        return "Eyedropper"

    @property
    def emoji(self) -> str:
        return "<:eyedropper:1056854084004630568>"

    @property
    def description(self) -> str:
        return "Pick and add colour to Palette"

    @property
    def autouse(self) -> bool:
        return True

    async def use(self, *, interaction: discord.Interaction) -> bool:
        """The method that is called when the tool is used"""
        cursor_pixel = self.board.cursor_pixel
        emoji = discord.PartialEmoji.from_str(self.board.un_cursor(cursor_pixel))

        # Check if the option already exists
        option = self.view.colour_menu.emoji_to_option(emoji)
        if option is None:
            eyedropped_options = [
                option
                for option in self.view.colour_menu.options
                if option.label.startswith("Eyedropped option")
            ]

            # Try to find the emoji so that we can use its real name as label
            if (fetched_emoji := self.bot.get_emoji(emoji.id)) is not None:
                label = fetched_emoji.name
            # If the emoji's name is the shortened name (i.e. it is a custom emoji input through the program)
            elif emoji.name == "e":
                label = f"Eyedropped option #{len(eyedropped_options + 1)}"

            option = discord.SelectOption(
                label=label,
                emoji=emoji,
                value=str(emoji),
            )

            self.view.colour_menu.append_option(option)

        if self.board.cursor == option.value:
            return False
        else:
            self.board.cursor = option.value
            self.view.colour_menu.set_default(option)
            return True


class FillTool(Tool):
    @property
    def name(self) -> str:
        return "Fill"

    @property
    def emoji(self) -> str:
        return "<:fill:1056853974394867792>"

    @property
    def description(self) -> str:
        return "Fill closed area"

    @property
    def autouse(self) -> bool:
        return True

    async def use(
        self,
        *,
        interaction: discord.Interaction,
        initial_coords: Optional[Tuple[int, int]] = None,
    ) -> bool:
        """The method that is called when the tool is used"""
        colour = self.board.cursor
        if self.board.cursor_pixel == colour:
            return

        # Use Breadth-First Search algorithm to fill an area
        initial_coords = initial_coords or (
            self.board.cursor_row,
            self.board.cursor_col,
        )
        initial_pixel = self.board.get_pixel(*initial_coords)

        coords = []
        queue = [initial_coords]
        i = 0

        while i < len(queue):
            row, col = queue[i]
            i += 1
            # Skip to next cell in the queue if
            # the row is less than 0 or greater than the max row possible,
            # the col is less than 0 or greater than the max col possible or
            # the current pixel (or its cursor version) is not the same as the pixel to replace (or its cursor version)
            if (
                any((row < 0, row > self.board.cursor_row_max))
                or any((col < 0, col > self.board.cursor_col_max))
                or any(
                    (
                        self.board.get_pixel(row, col) != initial_pixel,
                        CURSOR.get(
                            self.board.get_pixel(row, col),
                            self.board.get_pixel(row, col),
                        )
                        != CURSOR.get(initial_pixel, initial_pixel),
                    )
                )
                or (row, col) in coords
            ):
                continue

            coords.append((row, col))

            # Enqueue the four surrounding cells of the current cell
            queue.append((row + 1, col))
            queue.append((row - 1, col))
            queue.append((row, col + 1))
            queue.append((row, col - 1))

        return self.board.draw(coords=coords)  # Draw all the cells


class ReplaceTool(Tool):
    @property
    def name(self) -> str:
        return "Replace"

    @property
    def emoji(self) -> str:
        return "<:replace:1056854037066154034>"

    @property
    def description(self) -> str:
        return "Replace all pixels"

    @property
    def autouse(self) -> bool:
        return True

    async def use(self, *, interaction: discord.Interaction) -> bool:
        """The method that is called when the tool is used"""
        colour = self.board.cursor
        to_replace = self.board.cursor_pixel

        return self.board.draw(
            colour, coords=np.array(np.where(self.board.board == to_replace)).T
        )


CHANGE_AMOUNT = 17  # Change amount for Lighten & Darken tools to allow exactly 15 changes from 0 or 255, respectively


class DarkenTool(Tool):
    @property
    def name(self) -> str:
        return "Darken"

    @property
    def emoji(self) -> str:
        return "🔅"

    @property
    def description(self) -> str:
        return "Darken pixel(s) by 17 RGB values"

    @staticmethod
    def edit(value: int) -> int:
        return max(
            value - CHANGE_AMOUNT, 0
        )  # The max func makes sure it doesn't go below 0 when decreasing, for example, black

    async def use(self, *, interaction: discord.Interaction) -> bool:
        """The method that is called when the tool is used"""
        cursors = self.board.cursor_coords

        for cursor in cursors:
            emoji = discord.PartialEmoji.from_str(
                self.board.un_cursor(self.board.board[cursor])
            )
            colour = None
            if (fetched_emoji := self.bot.get_emoji(emoji.id)) is not None:
                try:
                    colour = Colour.from_hex(fetched_emoji.name)
                except ValueError:  # It is not a colour emoji
                    pass

            if colour is None:
                colour = await Colour.from_emoji(str(emoji))

            RGB_A = (
                self.edit(colour.R),
                self.edit(colour.G),
                self.edit(colour.B),
                colour.A,
            )
            modified_colour = Colour(RGB_A)

            modified_emoji = await self.bot.upload_emoji(
                modified_colour, draw_view=self.view, interaction=interaction
            )
            return self.board.draw(str(modified_emoji), coords=[cursor])


class LightenTool(DarkenTool):
    @property
    def name(self) -> str:
        return "Lighten"

    @property
    def emoji(self) -> str:
        return "🔆"

    @property
    def description(self) -> str:
        return "Lighten pixel(s) by 17 RGB values"

    @staticmethod
    def edit(value: int) -> int:
        return min(
            value + CHANGE_AMOUNT, 255
        )  # The min func makes sure it doesn't go above 255 when increasing, for example, white
