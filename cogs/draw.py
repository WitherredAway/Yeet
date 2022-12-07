from __future__ import annotations

import asyncio
import copy
from typing import Callable, Optional, Union, Literal, List, Dict, Tuple, TypeVar
import io
from functools import cached_property
import re

import emojis
import numpy as np
import discord
from discord.ext import commands
from PIL import Image

from constants import u200b, NEW_LINE
from .draw_utils.constants import (
    ROW_ICONS_DICT,
    ROW_ICONS,
    COLUMN_ICONS_DICT,
    COLUMN_ICONS,
    CURSOR,
    inv_CURSOR,
    LETTER_TO_NUMBER,
    ALPHABETS,
    NUMBERS,
    PADDING,
    BASE_COLOUR_OPTIONS,
    BASE_NUMBER_OPTIONS,
    MIN_HEIGHT_OR_WIDTH,
    MAX_HEIGHT_OR_WIDTH,
)
from .draw_utils.emoji import (
    draw_emoji,
    SentEmoji,
    AddedEmoji,
)
from .draw_utils.tools import (
    Tool,
    BrushTool,
    EraseTool,
    EyedropperTool,
    FillTool,
    ReplaceTool,
)


EMBED_DESC_CHAR_LIMIT = 4096
EMBED_FIELD_CHAR_LIMIT = 1024


CHANNEL = "[a-f0-9]{2}"
HEX_REGEX = re.compile(
    rf"\b(?P<red>{CHANNEL})(?P<green>{CHANNEL})(?P<blue>{CHANNEL})(?P<alpha>{CHANNEL})?\b"
)

ZERO_TO_255 = "0*25[0-5]|0*2[0-4][0-9]|0*1[0-9]{2}|0*[1-9][0-9]|0*[0-9]"
RGB_A_REGEX = re.compile(
    rf"\((?P<red>{ZERO_TO_255}) *,? +(?P<green>{ZERO_TO_255}) *,? +(?P<blue>{ZERO_TO_255})(?: *,? +(?P<alpha>{ZERO_TO_255}))?\)"
)

FLAG_EMOJI_REGEX = re.compile("[\U0001F1E6-\U0001F1FF]")

CUSTOM_EMOJI_REGEX = re.compile("<a?:[a-zA-Z0-9_]+:\d+>")


class StartView(discord.ui.View):
    def __init__(
        self,
        *,
        ctx: commands.Context,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: Optional[
            Literal["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜"]
        ] = "⬜",
    ):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.height = height
        self.width = width
        self.background = background

    @property
    def initial_message(self):
        return f"Create new draw board with `height = {self.height}`, `width = {self.width}` and `background = {self.background}`?"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, use the `{self.ctx.command}` command to create your own instance.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        await self.response.edit(view=None)
        self.stop()

    @discord.ui.select(options=BASE_COLOUR_OPTIONS, placeholder="Background")
    async def background_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()

        self.background = select.values[0]
        await self.response.edit(content=self.initial_message)

    @discord.ui.select(options=BASE_NUMBER_OPTIONS, placeholder="Height")
    async def height_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()

        self.height = int(select.values[0])
        await self.response.edit(content=self.initial_message)

    @discord.ui.select(options=BASE_NUMBER_OPTIONS, placeholder="Width")
    async def width_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()

        self.width = int(select.values[0])
        await self.response.edit(content=self.initial_message)

    @discord.ui.button(label="Create", style=discord.ButtonStyle.green)
    async def create(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()
        board = Board(height=self.height, width=self.width, background=self.background)
        self.draw_view = DrawView(board, ctx=self.ctx)

        response = await interaction.followup.send(
            embed=self.draw_view.embed, view=self.draw_view
        )
        self.draw_view.response = response
        await response.edit(
            embed=self.draw_view.embed, view=self.draw_view
        )  # This is necessary because custom emojis only render when a followup is edited ◉_◉

        await self.response.delete()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        await self.response.delete()
        self.stop()


class Notification:
    def __init__(
        self,
        content: Optional[str] = None,
        *,
        view: DrawView,
        emoji: Optional[
            Union[discord.PartialEmoji, discord.Emoji]
        ] = discord.PartialEmoji.from_str("🔔"),
    ):
        self.emoji: Union[discord.PartialEmoji, discord.Emoji] = emoji
        self.content: str = content
        self.view = view

    async def edit(
        self,
        content: Optional[str] = None,
        *,
        interaction: Optional[discord.Interaction] = None,
        emoji: Optional[
            Union[discord.PartialEmoji, discord.Emoji]
        ] = discord.PartialEmoji.from_str("🔔"),
    ):
        if emoji is not None:
            self.emoji = emoji
        self.content = content

        if interaction is not None:
            await self.view.edit_message(interaction)

    def truncated_content(self, length: Optional[int] = None):
        if length is None:
            trunc = self.content.split("\n")[0]
        else:
            trunc = self.content[:length]
        return trunc + (" ..." if len(self.content) > len(trunc) else "")


class Board:
    def __init__(
        self,
        *,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: Optional[
            Literal["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜"]
        ] = "⬜",
    ) -> None:
        self.height: int = height
        self.width: int = width
        self.background: str = background

        self.initial_board: np.array = np.full(
            (height, width), background, dtype="object"
        )
        self.board_history: List[np.array] = [self.initial_board.copy()]
        self.board_index: int = 0

        self.row_labels: Tuple[str] = ROW_ICONS[:height]
        self.col_labels: Tuple[str] = COLUMN_ICONS[:width]

        self.cursor: str = self.background
        self.cursor_row: int = int(len(self.row_labels) / 2)
        self.cursor_row_max = len(self.row_labels) - 1
        self.cursor_col: int = int(len(self.col_labels) / 2)
        self.cursor_col_max = len(self.col_labels) - 1
        self.cursor_coords: List[Tuple[int, int]] = [(self.cursor_row, self.cursor_col)]

        # This is for select tool.
        self.initial_coords: Tuple[int, int]
        self.final_coords: Tuple[int, int]

        self.clear_cursors()

    def __str__(self) -> str:
        cursor_rows = tuple(row for row, col in self.cursor_coords)
        cursor_cols = tuple(col for row, col in self.cursor_coords)
        row_labels = [
            (row if idx not in cursor_rows else ROW_ICONS_DICT[row])
            for idx, row in enumerate(self.row_labels)
        ]
        col_labels = [
            (col if idx not in cursor_cols else COLUMN_ICONS_DICT[col])
            for idx, col in enumerate(self.col_labels)
        ]

        return (
            f"{self.cursor}{PADDING}{u200b.join(col_labels)}\n"
            f"\n{NEW_LINE.join([f'{row_labels[idx]}{PADDING}{u200b.join(row)}' for idx, row in enumerate(self.board)])}"
        )

    @property
    def board(self) -> np.array:
        return self.board_history[self.board_index]

    @property
    def backup_board(self) -> np.array:
        return self.board_history[self.board_index - 1]

    @property
    def cursor_pixel(self):
        return self.un_cursor(self.board[self.cursor_row, self.cursor_col])

    @cursor_pixel.setter
    def cursor_pixel(self, value: str):
        if not isinstance(value, str):
            raise TypeError("Value must be a string")
        self.board[self.cursor_row, self.cursor_col] = value

    def get_pixel(
        self,
        row: Optional[int] = None,
        col: Optional[int] = None,
    ):
        row = row if row is not None else self.cursor_row
        col = col if col is not None else self.cursor_col

        return self.un_cursor(self.board[row, col])

    @classmethod
    def from_board(cls, board: np.array, *, background: Optional[str] = "⬜"):
        height = len(board)
        width = len(board[0])

        board_obj = cls(height=height, width=width, background=background)
        board_obj.board_history = [board]

        return board_obj

    def clear(self):
        self.draw(
            self.background, coords=np.array(np.where(self.board != self.background)).T
        )
        self.clear_cursors()

    def un_cursor(self, value):
        return inv_CURSOR.get(value, value)

    def draw(
        self,
        colour: Optional[str] = None,
        *,
        coords: Optional[List[Tuple[int, int]]] = None,
    ) -> bool:
        colour = colour or self.cursor
        coords = coords if coords is not None else self.cursor_coords

        if all((self.board[row, col] == colour for row, col in coords)):
            return False

        colour_emoji = discord.PartialEmoji.from_str(colour)
        if colour_emoji.is_custom_emoji():
            colour_emoji.name = "e"
        colour = str(colour_emoji)

        self.board_history = self.board_history[: self.board_index + 1]
        self.board_history.append(self.board.copy())
        self.board_index += 1

        for row, col in coords:
            self.board[row, col] = colour

        # 3am debug statement
        # print(
        #     "\n-------------------------\n".join(
        #         [
        #             NEW_LINE.join([f'{"".join(row)}' for row in board])
        #             for board in self.history
        #         ]
        #     ),
        #     f"-------{len(self.history)}-------",
        #     sep="\n",
        # )

        return True

    def clear_cursors(self, *, empty: Optional[bool] = False):
        for x, row in enumerate(self.board):
            for y, _ in enumerate(row):
                cell_tuple = (x, y)
                self.board[cell_tuple] = self.un_cursor(self.board[cell_tuple])

        self.cursor_coords = (
            [(self.cursor_row, self.cursor_col)] if empty is False else []
        )

    def move_cursor(
        self,
        row_move: Optional[int] = 0,
        col_move: Optional[int] = 0,
        select: Optional[bool] = False,
    ):
        self.clear_cursors()
        self.cursor_row = (self.cursor_row + row_move) % (self.cursor_row_max + 1)
        self.cursor_col = (self.cursor_col + col_move) % (self.cursor_col_max + 1)

        if select is True:
            self.final_coords = (self.cursor_row, self.cursor_col)
            self.final_row, self.final_col = self.final_coords

            self.cursor_coords = [
                (row, col)
                for col in range(
                    min(self.initial_col, self.final_col),
                    max(self.initial_col, self.final_col) + 1,
                )
                for row in range(
                    min(self.initial_row, self.final_row),
                    max(self.initial_row, self.final_row) + 1,
                )
            ]
        else:
            self.cursor_coords = [(self.cursor_row, self.cursor_col)]
            return


class ToolMenu(discord.ui.Select):
    def __init__(
        self,
        view: DrawView,
        *,
        options: Optional[List[discord.SelectOption]] = None,
    ):
        self.tool_list = [
            BrushTool(view),
            EraseTool(view),
            EyedropperTool(view),
            FillTool(view),
            ReplaceTool(view),
        ]

        default_options: List[discord.SelectOption] = [
            discord.SelectOption(
                label=tool.name, emoji=tool.emoji, value=tool.name.lower()
            )
            for tool in self.tool_list
        ]
        options = options if options else default_options
        self.END_INDEX = len(default_options)  # The ending index of default options

        super().__init__(
            placeholder="🖌️ Tools",
            max_values=1,
            options=options,
        )

        self._view: DrawView = view
        self.view: DrawView

    @property
    def tools(self) -> Dict[str, Tool]:
        return {tool.name.lower(): tool for tool in self.tool_list}

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        value = self.values[0]
        tool = self.tools[value]

        # If the tool selected is one of these,
        # use it directly instead of equipping
        edit: bool = True  # This var is to decide whether or not to edit the message, depending on if the tool was used successfully
        if value in ["eyedropper", "fill", "replace"]:
            edit = tool.use()
        # Else, equip the tool (to the primary tool button slot)
        else:
            self.view.primary_tool = tool
            self.view.load_items()

        if edit:
            await self.view.edit_message(interaction)


class Colour:
    # RGB_A accepts RGB values and an optional Alpha value
    def __init__(self, RGB_A: Tuple[int]):
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

    async def to_bytes(self) -> io.BytesIO():
        return await self.loop.run_in_executor(None, self._to_bytes)

    def _to_bytes(self) -> io.BytesIO():
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
    async def from_emoji(cls, emoji: str) -> Colour:
        loop = asyncio.get_running_loop()
        image = await loop.run_in_executor(None, draw_emoji, emoji)
        colors = [
            color
            for color in sorted(
                image.getcolors(image.size[0] * image.size[1]),
                key=lambda c: c[0],
                reverse=True,
            )
            if color[1][-1] > 0
        ]

        return cls(colors[0][1])

    @classmethod
    def mix_colours(cls, colours: List[Tuple[int, Colour]]) -> Colour:
        colours = [
            colour.RGBA if isinstance(colour, Colour) else colour for colour in colours
        ]
        total_weight = len(colours)

        return cls(
            tuple(round(sum(colour) / total_weight) for colour in zip(*colours)),
        )


class ColourMenu(discord.ui.Select):
    def __init__(
        self,
        *,
        options: Optional[List[discord.SelectOption]] = None,
        background: str,
    ):
        default_options: List[discord.SelectOption] = [
            *BASE_COLOUR_OPTIONS,
            discord.SelectOption(
                label="Add Colour(s)",
                emoji="🏳️‍🌈",
                value="colour",
            ),
            discord.SelectOption(
                label="Add Emoji(s)",
                emoji="<:emojismiley:1032565214606012416>",
                value="emoji",
            ),
        ]
        options = options if options else default_options
        self.END_INDEX = len(default_options)  # The ending index of default options
        for option in options:
            if str(option.emoji) == background and not option.label.endswith(" (base)"):
                option.label += " (base)"

        super().__init__(
            placeholder="🎨 Palette",
            min_values=1,
            max_values=len(options),
            options=options,
        )

        self.view: DrawView

    @property
    def value_to_option_dict(self) -> Dict[str, discord.SelectOption]:
        return {option.value: option for option in self.options}

    @property
    def emoji_to_option_dict(self) -> Dict[Union[str, int], discord.SelectOption]:
        return {
            option.emoji.name
            if option.emoji.is_unicode_emoji()
            else option.emoji.id: option
            for option in self.options
        }

    def value_to_option(
        self, value: Union[str, int]
    ) -> Union[None, discord.SelectOption]:
        return self.value_to_option_dict.get(value)

    def emoji_to_option(
        self, emoji: Union[discord.Emoji, discord.PartialEmoji]
    ) -> Union[None, discord.SelectOption]:
        if isinstance(emoji, discord.Emoji):
            identifier = emoji.id
        else:
            identifier = emoji.name if emoji.is_unicode_emoji() else emoji.id

        return self.emoji_to_option_dict.get(identifier)

    async def upload_emoji(self, colour: Colour) -> discord.Emoji:
        # Look if emoji already exists
        for guild in self.bot.EMOJI_SERVERS:
            guild_emojis = await guild.fetch_emojis()
            for guild_emoji in guild_emojis:
                if colour.hex == guild_emoji.name:
                    return guild_emoji

        # Emoji does not exist already, proceed to create
        for guild in self.bot.EMOJI_SERVERS:
            try:
                emoji = await colour.to_emoji(guild)
            except discord.HTTPException:
                continue
            else:
                return emoji
        else:  # If it exits without returning aka there was no space available
            emoji_delete = await self.bot.EMOJI_SERVERS[0].fetch_emojis()[
                0
            ]  # Get first emoji from the first emoji server
            await emoji_delete.delete()  # Delete the emoji to make space for the new one
            await self.upload_emoji(colour)  # Run again

    def append_option(
        self, option: discord.SelectOption
    ) -> Tuple[bool, Union[discord.PartialEmoji, None]]:
        if (found_option := self.emoji_to_option(option.emoji)) is not None:
            return False, found_option

        replaced_option = None
        if len(self.options) == 25:
            replaced_option = self.options.pop(self.END_INDEX)
            replaced_option.emoji.name = replaced_option.label

        super().append_option(option)
        return replaced_option is not None, replaced_option

    def append_sent_emojis(
        self, sent_emojis: List[SentEmoji]
    ) -> Dict[Union[int, str], AddedEmoji]:
        added_emojis = {}
        for sent_emoji in sent_emojis:
            emoji: Union[discord.Emoji, discord.PartialEmoji] = sent_emoji.emoji

            if self.emoji_to_option(emoji):
                added_emoji = AddedEmoji(
                    sent_emoji=sent_emoji, emoji=emoji, status="Already exists."
                )

            else:
                added_emoji = AddedEmoji(
                    sent_emoji=sent_emoji,
                    emoji=emoji,
                    status="Added.",
                    name=emoji.name,
                )

            added_emojis[
                emoji.id
                if isinstance(emoji, discord.Emoji)
                else (emoji.name if emoji.is_unicode_emoji() else emoji.id)
            ] = added_emoji

        replaced_emojis = {}
        for added_emoji in added_emojis.values():
            if added_emoji.status != "Added.":
                continue

            option = discord.SelectOption(
                label=added_emoji.name,
                emoji=added_emoji.emoji,
                value=str(added_emoji.emoji),
            )
            replaced, returned_option = self.append_option(option)
            if replaced:
                replaced_emoji = returned_option.emoji
                replaced_emojis[
                    replaced_emoji.id if replaced_emoji.id else replaced_emoji.name
                ] = AddedEmoji.from_option(
                    returned_option,
                    status=f"Replaced by {added_emoji}.",
                    sent_emoji=SentEmoji(emoji=replaced_emoji),
                )
                added_emoji.status = f"Added (replaced {replaced_emoji})."

        # added_emojis.update(replaced_emojis)
        added_emojis = {
            k: v for k, v in added_emojis.items() if k not in replaced_emojis
        }
        return added_emojis

    async def added_emojis_respond(
        self,
        added_emojis: Dict[Union[int, str], AddedEmoji],
        *,
        notification: Notification,
        interaction: discord.Interaction,
    ):
        response = [
            f"{added_emoji.emoji} - {added_emoji.status}"
            for added_emoji in added_emojis.values()
        ]
        if len(response) == 0:
            return await notification.edit("Aborted", interaction=interaction)

        if any(
            ("Added" in added_emoji.status for added_emoji in added_emojis.values())
        ):
            self.board.cursor = self.options[-1].value
            self.placeholder = self.options[-1].label

        await notification.edit(
            ("\n".join(response))[
                : EMBED_FIELD_CHAR_LIMIT - len(self.view.embed.fields[0].value)
            ]
        )
        await self.view.edit_message(interaction)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # These need to be defined here because the class does not have a view when initiated
        self.ctx = self.view.ctx
        self.bot = self.view.bot
        self.board = self.view.board

        # If the Add Colour option was selected. Always takes first priority
        if "colour" in self.values:

            def check(m):
                return m.author == interaction.user

            notification, msg = await self.view.wait_for(
                (
                    "Please type all the colours you want to add. They can be either or all of:"
                    "\n• The hex codes (e.g. `ff64c4` or `ff64c4ff` to include alpha) **seperated by space**,"
                    "\n• The RGB(A) values separated by space or comma or both (e.g. `(255 100 196)` or `(255, 100, 196, 125)`) of each colour **surrounded by brackets**"
                    "\n"
                    "\n__**Example**__:"
                    "\n*This entire block is a single message with valid hex codes/rgb(a) values*"
                    "\n```"
                    "\n647bab"
                    "\nf08234ff"
                    "\n(221 93 141) (112, 162, 64, 255)"
                    "\n(223 224 226)"
                    "\n```"
                ),
                interaction=interaction,
                check=check,
            )
            if msg is None:
                return

            content = msg.content.lower().strip()

            # Get any hex codes from the content
            hex_matches = [match for match in HEX_REGEX.finditer(content)]

            # Get any RGB/A values from the content
            rgb_a_matches = [match for match in RGB_A_REGEX.finditer(content)]

            total_matches = hex_matches + rgb_a_matches

            ## Organize all the matches into SentEmoji objects
            sent_emojis = []
            for match in total_matches:
                base = 16 if match in hex_matches else 10

                red = int(match.group("red"), base)
                green = int(match.group("green"), base)
                blue = int(match.group("blue"), base)
                alpha = int(
                    match.group("alpha") or ("ff" if match in hex_matches else "255"),
                    base,
                )

                colour = Colour((red, green, blue, alpha))

                emoji = await self.upload_emoji(colour)

                sent_emojis.append(SentEmoji(emoji=emoji, index=match.start()))
            sent_emojis.sort(key=lambda emoji: emoji.index)
            ##

            added_emojis = self.append_sent_emojis(sent_emojis)

            await self.added_emojis_respond(
                added_emojis, notification=notification, interaction=interaction
            )

        # First it checks if the Add Emoji option was selected. Takes second priority
        elif "emoji" in self.values:

            def check(m):
                return m.author == interaction.user

            notification, msg = await self.view.wait_for(
                "Please send a message containing the emojis you want to add to your palette. E.g. `😎 I like turtles 🐢`",
                interaction=interaction,
                check=check,
            )
            if msg is None:
                return

            content = msg.content
            # Get any unicode emojis from the content
            # and list them as SentEmoji objects
            unicode_emojis = [
                SentEmoji(
                    emoji=discord.PartialEmoji.from_str(
                        self.view.board.un_cursor(emoji)
                    ),
                    index=content.index(emoji),
                )
                for emoji in emojis.get(content)
            ]
            # Get any flag/regional indicator emojis from the content
            # and list them as SentEmoji objects
            flag_emojis = [
                SentEmoji(
                    emoji=discord.PartialEmoji.from_str(emoji.group(0)),
                    index=emoji.start(),
                )
                for emoji in FLAG_EMOJI_REGEX.finditer(content)
            ]
            # Get any custom emojis from the content
            # and list them as SentEmoji objects
            custom_emojis = [
                SentEmoji(
                    emoji=discord.PartialEmoji.from_str(emoji.group(0)),
                    index=emoji.start(),
                )
                for emoji in CUSTOM_EMOJI_REGEX.finditer(content)
            ]

            ## Organize all the matches into SentEmoji objects
            sent_emojis = sorted(
                unicode_emojis + flag_emojis + custom_emojis,
                key=lambda emoji: emoji.index,
            )
            ##

            added_emojis = self.append_sent_emojis(sent_emojis)

            await self.added_emojis_respond(
                added_emojis, notification=notification, interaction=interaction
            )

        # If multiple options were selected
        elif len(self.values) > 1:
            selected_options = [self.value_to_option(value) for value in self.values]

            selected_emojis = [str(option.emoji) for option in selected_options]
            notification = await self.view.create_notification(
                f'Mixing colours {" and ".join(selected_emojis)} ...',
                interaction=interaction,
            )

            colours = [await Colour.from_emoji(emoji) for emoji in selected_emojis]

            mixed_colour = Colour.mix_colours(colours)

            emoji = discord.PartialEmoji.from_str(
                str(await self.upload_emoji(mixed_colour))
            )

            option = discord.SelectOption(
                label=mixed_colour.hex,
                emoji=emoji,
                value=str(emoji),
            )
            replaced, returned_option = self.append_option(option)

            self.board.cursor = option.value
            self.placeholder = option.label

            await notification.edit(
                f'Mixed colours:\n{" + ".join(selected_emojis)} = {emoji}'
                + (f" (replaced {returned_option.emoji})." if replaced else "")
            )
            await self.view.edit_message(interaction)

        # If only one option was selected
        elif self.board.cursor != (value := self.values[0]):
            self.board.cursor = value
            self.placeholder = self.value_to_option(value).label

            await self.view.edit_message(interaction)


class DrawView(discord.ui.View):
    def __init__(
        self,
        board: Board,
        *,
        ctx: commands.Context,
        tool_options: Optional[List[discord.SelectOption]] = None,
        colour_options: Optional[List[discord.SelectOption]] = None,
    ):
        super().__init__(timeout=600)
        self.board: Board = board

        self.ctx: commands.Context = ctx
        self.bot: commands.Bot = self.ctx.bot

        self.tool_menu: ToolMenu = ToolMenu(self, options=tool_options)
        self.colour_menu: ColourMenu = ColourMenu(
            options=colour_options, background=board.background
        )
        self.primary_tool: Tool = self.tool_menu.tools["brush"]

        self.secondary_page: bool = False
        self.auto: bool = False
        self.select: bool = False
        self.load_items()

        self.response: discord.Message = None
        self.lock: asyncio.Lock = self.bot.lock

        self.notifications: List[Notification] = [Notification(view=self)]

    @property
    def embed(self):
        embed = discord.Embed(title=f"{self.ctx.author}'s drawing board.")

        # Render the cursors on a board copy
        board = copy.deepcopy(self.board)
        for row, col in board.cursor_coords:
            cell = board.board[row, col]
            board.board[row, col] = CURSOR.get(cell, cell)

        # The actual board
        embed.description = str(board)

        # This section adds the notification field only if any one
        # of the notifications is not empty. In such a case, it only
        # shows the notification(s) that is not empty
        if any((n.content is not None for n in self.notifications)):
            embed.add_field(
                name="Notifications",
                value="\n\n".join(
                    [
                        (
                            f"{str(n.emoji)} "
                            + (
                                n.content if idx == 0 else n.truncated_content()
                            ).replace("\n", "\n> ")
                        )  # Put each notification into seperate quotes
                        if n.content is not None
                        else ""  # Show only non-empty notifications
                        for idx, n in enumerate(self.notifications)
                    ]
                ),
            )

        embed.set_footer(
            text=(
                f"The board looks wack? Try decreasing its size! Do {self.ctx.clean_prefix}help draw for more info."
                if any((len(board.row_labels) >= 10, len(board.col_labels) >= 10))
                else f"You can customize this board! Do {self.ctx.clean_prefix}help draw for more info."
            )
        )
        return embed

    async def create_notification(
        self,
        content: Optional[str] = None,
        *,
        interaction: Optional[discord.Interaction] = None,
        emoji: Optional[
            Union[discord.PartialEmoji, discord.Emoji]
        ] = discord.PartialEmoji.from_str("🔔"),
    ) -> Notification:
        self.notifications = self.notifications[:2]

        notification = Notification(content, emoji=emoji, view=self)
        self.notifications.insert(0, notification)

        if interaction is not None:
            await self.edit_message(interaction)

        return notification

    def stop_view(self):
        self.tool_menu.disabled = True
        self.colour_menu.disabled = True

        self.clear_items()
        self.add_item(self.tool_menu)
        self.add_item(self.colour_menu)
        self.board.clear_cursors(empty=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, use the `{self.ctx.command}` command to create your own instance.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        self.stop_view()
        self.add_item(
            discord.ui.Button(
                label=f"This interaction has timed out. Use `{self.ctx.prefix}{self.ctx.command} copy` for a new one.",
                style=discord.ButtonStyle.gray,
                disabled=True,
            )
        )
        await self.response.edit(embed=self.embed, view=self)
        self.stop()

    async def wait_for(
        self,
        content: Optional[str] = None,
        *,
        interaction: discord.Interaction,
        check: Callable = lambda x: x,
        delete_msg: bool = True,
    ) -> Tuple[Notification, discord.Message]:
        notification = None
        msg = None
        if self.lock.locked():
            await interaction.followup.send(
                "Another message is being waited for, please wait until that process is complete.",
                ephemeral=True,
            )
            return notification, msg

        if content is not None:
            notification = await self.create_notification(
                content, interaction=interaction
            )
        else:
            notification = await self.create_notification()
        async with self.lock:
            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                await notification.edit("Timed out.", interaction=interaction)
            else:
                if delete_msg is True:
                    await msg.delete()
            return notification, msg

    @property
    def placeholder_button(self) -> discord.ui.Button:
        button = discord.ui.Button(
            label="\u200b",
            style=discord.ButtonStyle.gray,
            custom_id=str(len(self.children)),
        )
        button.callback = lambda interaction: interaction.response.defer()

        return button

    def load_items(self):
        self.clear_items()
        self.add_item(self.tool_menu)
        self.add_item(self.colour_menu)

        # This is necessary for "paginating" the view and different buttons
        if self.secondary_page is False:
            self.add_item(self.undo)
            self.add_item(self.up_left)
            self.add_item(self.up)
            self.add_item(self.up_right)
            self.add_item(self.secondary_page_button)

            self.add_item(self.redo)
            self.add_item(self.left)
            self.add_item(self.auto_draw)
            self.add_item(self.right)
            self.add_item(self.select_button)

            self.add_item(self.primary_tool)
            self.add_item(self.down_left)
            self.add_item(self.down)
            self.add_item(self.down_right)
            self.add_item(self.set_cursor)

        elif self.secondary_page is True:
            self.add_item(self.stop_button)
            self.add_item(self.up_left)
            self.add_item(self.up)
            self.add_item(self.up_right)
            self.add_item(self.secondary_page_button)

            self.add_item(self.clear)
            self.add_item(self.left)
            self.add_item(self.auto_draw)
            self.add_item(self.right)
            self.add_item(self.select_button)

            self.add_item(self.primary_tool)
            self.add_item(self.down_left)
            self.add_item(self.down)
            self.add_item(self.down_right)
            self.add_item(self.set_cursor)

        self.update_buttons()

    def update_buttons(self):
        self.secondary_page_button.style = (
            discord.ButtonStyle.green
            if self.secondary_page
            else discord.ButtonStyle.grey
        )
        self.auto_draw.style = (
            discord.ButtonStyle.green if self.auto else discord.ButtonStyle.grey
        )
        self.select_button.style = (
            discord.ButtonStyle.green if self.select else discord.ButtonStyle.grey
        )

        self.undo.disabled = self.board.board_index == 0
        self.undo.label = f"{self.board.board_index} ↶"
        self.redo.disabled = self.board.board_index == len(self.board.board_history) - 1
        self.redo.label = (
            f"↷ {(len(self.board.board_history) - 1) - self.board.board_index}"
        )

    async def edit_message(self, interaction: discord.Interaction):
        self.update_buttons()
        try:
            await interaction.edit_original_message(embed=self.embed, view=self)
        except discord.HTTPException as error:
            if match := re.search(
                "In embeds\.\d+\.description: Must be 4096 or fewer in length\.",
                error.text,
            ):  # If the description reaches char limit
                await interaction.followup.send(
                    content=f"Max characters reached ({len(self.embed.description)}). Please remove some custom emojis from the board.\nCustom emojis take up more than 20 characters each, while most unicode/default ones take up 1!\nMaximum is 4096 characters due to discord limitations.",
                    ephemeral=True,
                )
                self.board.board_index -= 1
                self.board.board_history = self.board.board_history[
                    : self.board.board_index + 1
                ]
                await self.edit_message(interaction)
            elif match := re.search(
                "In components\.\d+\.components\.\d+\.options\.(?P<option>\d+)\.emoji\.id: Invalid emoji",
                error.text,
            ):  # If the emoji of one of the options of the select menu is unavailable
                removed_option = self.colour_menu.options.pop(
                    int(match.group("option"))
                )
                self.board.cursor = self.board.background
                await interaction.followup.send(
                    content=f"The {removed_option.emoji} emoji was not found for some reason, so the option was removed aswell. Please try again.",
                    ephemeral=True,
                )
                await self.edit_message(interaction)
            else:
                await interaction.followup.send(error)
                raise error

    async def move_cursor(
        self,
        interaction: discord.Interaction,
        row_move: Optional[int] = 0,
        col_move: Optional[int] = 0,
    ):
        self.board.move_cursor(row_move, col_move, self.select)

        if self.auto:
            self.primary_tool.use()
        await self.edit_message(interaction)

    # ------ BUTTONS ------

    # 1st row
    @discord.ui.button(label="↶", style=discord.ButtonStyle.grey)
    async def undo(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()
        if self.board.board_index > 0:
            self.board.board_index -= 1
        await self.edit_message(interaction)

    @discord.ui.button(
        emoji="<:stop:1032565237242667048>", style=discord.ButtonStyle.danger
    )
    async def stop_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.stop_view()
        await self.edit_message(interaction)
        self.stop()

    @discord.ui.button(
        emoji="<:up_left:1032565175930343484>", style=discord.ButtonStyle.blurple
    )
    async def up_left(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = -1
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:up:1032564978676400148>", style=discord.ButtonStyle.blurple
    )
    async def up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = -1
        col_move = 0
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:up_right:1032564997869543464>", style=discord.ButtonStyle.blurple
    )
    async def up_right(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = -1
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(label="2nd", style=discord.ButtonStyle.grey)
    async def secondary_page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.secondary_page = not self.secondary_page

        self.load_items()
        await self.edit_message(interaction)

    # 2nd Row
    @discord.ui.button(label="↷", style=discord.ButtonStyle.grey)
    async def redo(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()
        if self.board.board_index < len(self.board.board_history) - 1:
            self.board.board_index += 1
        await self.edit_message(interaction)

    @discord.ui.button(
        emoji="<:clear:1032565244658204702>", style=discord.ButtonStyle.danger
    )
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.secondary_page = False
        self.auto = False
        self.select = False
        self.board.clear()
        self.load_items()
        await self.edit_message(interaction)

    @discord.ui.button(
        emoji="<:left:1032565106934022185>", style=discord.ButtonStyle.blurple
    )
    async def left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 0
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:auto_draw:1032565224903016449>", style=discord.ButtonStyle.gray
    )
    async def auto_draw(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.auto = not self.auto
        await self.edit_message(interaction)

    @discord.ui.button(
        emoji="<:right:1032565019352764438>", style=discord.ButtonStyle.blurple
    )
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 0
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:select_tool:1037847279169704028> ", style=discord.ButtonStyle.gray
    )
    async def select_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        if self.select is False:
            self.board.initial_coords = (self.board.cursor_row, self.board.cursor_col)
            self.board.initial_row, self.board.initial_col = self.board.initial_coords
        elif self.select is True:
            self.board.clear_cursors()
        self.select = not self.select
        await self.edit_message(interaction)

    # 3rd / Last Row
    @discord.ui.button(
        emoji="<:down_left:1032565090223935518>", style=discord.ButtonStyle.blurple
    )
    async def down_left(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = 1
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:down:1032565072981131324>", style=discord.ButtonStyle.blurple
    )
    async def down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 1
        col_move = 0
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:down_right:1032565043604230214>", style=discord.ButtonStyle.blurple
    )
    async def down_right(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        row_move = 1
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:ABCD:1032565203608547328>", style=discord.ButtonStyle.blurple
    )
    async def set_cursor(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        def check(m):
            return m.author == interaction.user

        notification, msg = await self.wait_for(
            'Please type the cell you want to move the cursor to. e.g. "A1", "a1", "A10", "A", "10", etc.',
            interaction=interaction,
            check=check,
        )
        if msg is None:
            return
        cell = msg.content.upper()

        ABC = ALPHABETS[: self.board.cursor_row_max + 1]
        NUM = NUMBERS[: self.board.cursor_col_max + 1]

        # There is absolutely no reason to use regex here but YOLO
        CELL_REGEX = f"^(?P<row>[A-{ABC[-1]}])(?P<col>[0-9]|(?:1[0-{NUM[-1] % 10}]))$"
        ROW_OR_COL_REGEX = (
            f"(?:^(?P<row>[A-{ABC[-1]}])$)|(?:^(?P<col>[0-9]|(?:1[0-{NUM[-1] % 10}]))$)"
        )

        match = re.match(CELL_REGEX, cell)
        if match is not None:
            row_key = match.group("row")
            col_key = int(match.group("col"))
        else:
            match = re.match(ROW_OR_COL_REGEX, cell)
            if match is not None:
                row_key = match.group("row")
                row_key = row_key if row_key is not None else ABC[self.board.cursor_row]

                col_key = match.group("col")
                col_key = int(col_key) if col_key is not None else self.board.cursor_col
            else:
                row_key = col_key = None

        if row_key not in ABC or col_key not in NUM:
            return await notification.edit("Aborted.", interaction=interaction)

        row_move = LETTER_TO_NUMBER[row_key] - self.board.cursor_row
        col_move = col_key - self.board.cursor_col
        await notification.edit(
            f"Moved cursor to **{cell}** ({LETTER_TO_NUMBER[row_key]}, {col_key})",
        )
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)


class Draw(commands.Cog):
    """Category with commands to bring out your inner artist."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    display_emoji = "🖌️"

    @commands.bot_has_permissions(external_emojis=True)
    @commands.group(
        name="draw",
        aliases=("drawing", "paint", "painting"),
        case_insensitive=True,
        brief="Make pixel art on discord!",
        help="wip",
        description="Command which you can use to make pixel art using buttons and dropdown menus.",
        invoke_without_command=True,
    )
    async def draw(
        self,
        ctx: commands.Context,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: Optional[
            Literal["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜"]
        ] = "⬜",
    ) -> None:
        if MIN_HEIGHT_OR_WIDTH > height > MAX_HEIGHT_OR_WIDTH:
            return await ctx.send("Height must be atleast 5 and atmost 17")

        if MIN_HEIGHT_OR_WIDTH > width > MAX_HEIGHT_OR_WIDTH:
            return await ctx.send("Width must be atleast 5 and atmost 17")

        start_view = StartView(
            ctx=ctx, height=height, width=width, background=background
        )
        response = await ctx.send(
            start_view.initial_message,
            view=start_view,
        )
        start_view.response = response

    @draw.command(
        name="copy",
        brief="Copy a drawing.",
        help="Copy a drawing from an embed by replying to the message or using message link.",
        description="Allows you to copy a drawing that was done with the `draw` command. This will also copy the palette! You can copy by replying to such a message or by providing the message link (or ID).",
    )
    async def copy(
        self,
        ctx: commands.Context,
        message_link: Optional[discord.Message] = None,
    ):
        message = message_link
        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        elif message_link is None or not isinstance(message_link, discord.Message):
            return await ctx.send_help(ctx.command)

        if len(message.embeds) == 0 or message.author != ctx.bot.user:
            return await ctx.send(
                "Invalid message, make sure it's a draw embed and a message from the bot."
            )
        if "drawing board" not in message.embeds[0].title:
            return await ctx.send(
                "Invalid message, make sure it's a draw embed and a message from the bot."
            )

        description = message.embeds[0].description
        lines = description.split("\n")[2:]
        board = []
        for line in lines:
            board.append(line.split(PADDING)[-1].split("\u200b"))
        board = np.array(board, dtype="object")

        old_view = discord.ui.View.from_message(message, timeout=0)
        if len(old_view.children) > 1:
            tool_options = old_view.children[0].options
            colour_options = old_view.children[1].options
        else:
            tool_options = None
            colour_options = old_view.children[0].options

        for option in colour_options:
            if option.label.endswith(" (base)"):
                bg = str(option.emoji)

        board_obj = Board.from_board(board=board, background=bg)
        board_obj.clear_cursors()
        draw_view = DrawView(
            board_obj, ctx=ctx, tool_options=tool_options, colour_options=colour_options
        )
        draw_view.board.cursor = description.split(PADDING)[0]

        start_view = StartView(ctx=ctx, draw_view=draw_view)
        response = await ctx.send(
            content="Create a copy of this board? (Due to discord limitations, custom emojis may not render here)",
            embed=draw_view.embed,
            view=start_view,
        )
        start_view.response = response


async def setup(bot):
    await bot.add_cog(Draw(bot))
