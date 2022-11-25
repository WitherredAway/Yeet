from __future__ import annotations

import typing
from typing import Optional, Tuple

import discord
from discord.ext import commands
import numpy as np

from .constants import CURSOR
if typing.TYPE_CHECKING:
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
        self.board: Board = self.view.board
        self.bot: commands.Bot = self.view.bot

    @property
    def name(self) -> str:
        return None

    @property
    def emoji(self) -> str:
        return None

    def use(self):
        """The method that is called when the tool is used"""
        pass

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        self.use()
        await self.view.edit_draw(interaction)


class BrushTool(Tool):
    @property
    def name(self) -> str:
        return "Brush"

    @property
    def emoji(self) -> str:
        return "<:draw:1032565261846454272>"

    def use(self):
        """The method that is called when the tool is used"""
        self.board.draw(self.board.cursor)


class EraseTool(Tool):
    @property
    def name(self) -> str:
        return "Eraser"

    @property
    def emoji(self) -> str:
        return "<:erase:927526530052132894>"

    def use(self):
        """The method that is called when the tool is used"""
        self.board.draw(self.board.background)


class EyedropperTool(Tool):
    @property
    def name(self) -> str:
        return "Eyedropper"

    @property
    def emoji(self) -> str:
        return "<:eyedropper:1033248590988066886>"

    def use(self):
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
        self.board.cursor = option.value
        self.view.colour_menu.placeholder = option.label


class FillTool(Tool):
    @property
    def name(self) -> str:
        return "Fill"

    @property
    def emoji(self) -> str:
        return "<:fill:930832869692149790>"

    def use(self, *, initial_coords: Optional[Tuple[int, int]] = None):
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

        self.board.draw(coords=coords)  # Draw all the cells


class ReplaceTool(Tool):
    @property
    def name(self) -> str:
        return "Replace"

    @property
    def emoji(self) -> str:
        return "<:replace:1032565283929456670>"

    def use(self):
        """The method that is called when the tool is used"""
        colour = self.board.cursor
        to_replace = self.board.cursor_pixel
        
        self.board.draw(colour, coords=np.array(np.where(self.board.board == to_replace)).T)
