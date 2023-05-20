from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import copy
from dataclasses import dataclass
from functools import cached_property
import re
import typing
from typing import Callable, Optional, Union, Literal, List, Dict, Tuple

import emoji
import numpy as np
import discord
from discord.ext import commands
from PIL import Image
from helpers.context import CustomContext
from pilmoji import Pilmoji

from ..utils.utils import emoji_to_option_dict, image_to_file, value_to_option_dict
from helpers.constants import EMBED_FIELD_CHAR_LIMIT, u200b, NL
from .utils.constants import (
    FONT,
    ROW_ICONS_DICT,
    ROW_ICONS,
    COLUMN_ICONS_DICT,
    COLUMN_ICONS,
    CURSOR,
    TRANSPARENT_EMOJI,
    inv_CURSOR,
    LETTER_TO_NUMBER,
    ALPHABETS,
    NUMBERS,
    PADDING,
    base_colour_options,
    base_number_options,
    MIN_HEIGHT_OR_WIDTH,
    MAX_HEIGHT_OR_WIDTH,
)
from .utils.emoji import (
    ADD_EMOJIS_EMOJI,
    SAVE_EMOJI,
    SET_CURSOR_EMOJI,
    ADD_COLOURS_EMOJI,
    MIX_COLOURS_EMOJI,
    AUTO_DRAW_EMOJI,
    SELECT_EMOJI,
    SentEmoji,
    AddedEmoji,
)
from .utils.tools import (
    Tool,
    BrushTool,
    EraseTool,
    EyedropperTool,
    FillTool,
    ReplaceTool,
    DarkenTool,
    LightenTool,
)
from .utils.regexes import (
    FLAG_EMOJI_REGEX,
    HEX_REGEX,
    RGB_A_REGEX,
    CUSTOM_EMOJI_REGEX,
)
from .utils.errors import InvalidDrawMessageError
from .utils.colour import Colour

if typing.TYPE_CHECKING:
    from main import Bot


@dataclass
class Coords:
    x: int
    y: int

    def __post_init__(self):
        self.ix: int = self.x * -1
        self.iy: int = self.y * -1


class StartView(discord.ui.View):
    def __init__(
        self,
        *,
        ctx: commands.Context,
        board: Union[Board, Tuple[int, int, str]],
        tool_options: Optional[List[discord.SelectOption]] = None,
        colour_options: Optional[List[discord.SelectOption]] = None,
    ):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bot: Bot = self.ctx.bot

        self._board = board
        if isinstance(self._board, Board):
            self.height: int = self._board.height
            self.width: int = self._board.width
            self.background: str = self._board.background
        elif isinstance(self._board, Tuple):
            self.height, self.width, self.background = self._board

        self.tool_options = tool_options
        self.colour_options = colour_options

        self.update_buttons()

    @property
    def initial_message(self) -> str:
        return f"Create new draw board with `height = {self.height}`, `width = {self.width}` and `background = {TRANSPARENT_KEY if self.background == TRANSPARENT_EMOJI else self.background}`?"

    @property
    def board(self) -> Board:
        if isinstance(self._board, Tuple):
            return Board(
                height=self.height, width=self.width, background=self.background
            )
        return self._board.modify(
            height=self.height, width=self.width, background=self.background
        )

    @classmethod
    def from_board_obj(cls, ctx: commands.Context, board: Board) -> StartView:
        height = board.height
        width = board.width
        background = board.background

        cls = cls(ctx=ctx, height=height, width=width, background=background)

        return cls

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

    async def start(self):
        embed = self.bot.Embed(description=str(self.board))
        embed.set_footer(
            text="Custom emojis may not appear here due to a discord limitation, but will render once you create the board."
        )
        self.response = await self.ctx.send(
            self.initial_message,
            embed=embed,
            view=self,
        )

    def set_default(self, select_menu: discord.SelectMenu, default_option_value):
        for option in select_menu.options:
            if option.value == str(default_option_value):
                option.default = True
            else:
                option.default = False

    def update_buttons(self):
        self.set_default(self.background_select, self.background)
        self.set_default(self.height_select, self.height)
        self.set_default(self.width_select, self.width)

    async def update(self):
        self.update_buttons()
        await self.response.edit(
            content=self.initial_message,
            embed=self.bot.Embed(description=str(self.board)),
            view=self,
        )

    @discord.ui.select(options=base_colour_options(), placeholder="Background")
    async def background_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()

        if self.background == select.values[0]:
            return
        self.background = select.values[0]
        await self.update()

    @discord.ui.select(options=base_number_options("height"), placeholder="Height")
    async def height_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()

        if self.height == int(select.values[0]):
            return
        self.height = int(select.values[0])
        await self.update()

    @discord.ui.select(options=base_number_options("width"), placeholder="Width")
    async def width_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        await interaction.response.defer()

        if self.width == int(select.values[0]):
            return
        self.width = int(select.values[0])
        await self.update()

    async def send_message(
        self, interaction: discord.Interaction, *, draw_view: DrawView
    ) -> discord.WebhookMessage:
        try:
            response: discord.Message = await interaction.followup.send(
                embed=draw_view.embed, view=draw_view
            )
            # print(f'[{datetime.datetime.strftime(datetime.datetime.utcnow() + datetime.timedelta(), "%H:%M:%S")}]: Edited')
        except discord.HTTPException as error:
            if match := re.search(
                "In components\.\d+\.components\.\d+\.options\.(?P<option>\d+)\.emoji\.id: Invalid emoji",
                error.text,
            ):  # If the emoji of one of the options of the select menu is unavailable
                removed_option = draw_view.colour_menu.options.pop(
                    int(match.group("option"))
                )
                content = f"The {removed_option.emoji} emoji was not found for some reason, so the option was removed aswell. Please try again."

                if interaction is None:
                    await self.response.channel.send(
                        content=content,
                    )
                else:
                    await interaction.followup.send(
                        content=content,
                        ephemeral=True,
                    )
                await self.send_message(interaction, draw_view=draw_view)
            else:
                if interaction is None:
                    await self.response.channel.send(error)
                else:
                    await interaction.followup.send(error)
                raise error

        return response

    @discord.ui.button(label="Create", style=discord.ButtonStyle.green)
    async def create(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()

        draw_view = DrawView(
            self.board,
            ctx=self.ctx,
            tool_options=self.tool_options,
            colour_options=self.colour_options,
        )
        response = await self.send_message(interaction, draw_view=draw_view)
        draw_view.response = response
        await response.edit(
            embed=draw_view.embed, view=draw_view
        )  # This is necessary because custom emojis only render when a followup is edited ◉_◉
        await self.response.delete()
        self.stop()

        await draw_view.start()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        await self.response.delete()
        self.stop()


class Notification:
    def __init__(
        self,
        content: Optional[str] = "",
        *,
        emoji: Optional[
            Union[discord.PartialEmoji, discord.Emoji]
        ] = discord.PartialEmoji.from_str("🔔"),
        view: DrawView,
    ):
        self.emoji: Union[discord.PartialEmoji, discord.Emoji] = emoji
        self.content: str = content
        self.view = view

    async def edit(
        self,
        content: Optional[str] = None,
        *,
        interaction: Optional[discord.Interaction] = None,
        emoji: Optional[Union[discord.PartialEmoji, discord.Emoji]] = None,
    ):
        if emoji is not None:
            self.emoji = emoji
        else:
            emoji = self.emoji
        self.content = content

        if interaction is not None:
            await self.view.edit_message(interaction)

    def get_truncated_content(self, length: Optional[int] = None):
        if length is None:
            trunc = self.content.split("\n")[0]
        else:
            trunc = self.content[:length]
        return trunc + (" ..." if len(self.content) > len(trunc) else "")


TRANSPARENT_KEY = "transparent"
EMOJI_SIZE = 128


class Board:
    def __init__(
        self,
        *,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: Optional[
            Literal["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜", "transparent"]
        ] = TRANSPARENT_KEY,
    ) -> None:
        self.height: int = height
        self.width: int = width
        self.background: str = (
            TRANSPARENT_EMOJI if background == TRANSPARENT_KEY else background
        )

        self.initial_board: np.ndarray = np.full(
            (self.height, self.width), self.background, dtype="object"
        )
        self.board_history: List[np.ndarray] = [self.initial_board.copy()]
        self.board_index: int = 0
        self.set_attributes()

        # This is for select tool.
        self.initial_coords: Tuple[int, int]
        self.final_coords: Tuple[int, int]

        self.clear_cursors()

    def set_attributes(self):
        self.row_labels: Tuple[str] = ROW_ICONS[: self.height]
        self.col_labels: Tuple[str] = COLUMN_ICONS[: self.width]
        self.centre: Tuple[int, int] = (
            len(self.row_labels) // 2,
            len(self.col_labels) // 2,
        )
        self.centre_row, self.centre_col = self.centre

        self.cursor: str = self.background
        self.cursor_row, self.cursor_col = self.centre
        self.cursor_row_max = len(self.row_labels) - 1
        self.cursor_col_max = len(self.col_labels) - 1
        self.cursor_coords: List[Tuple[int, int]] = [(self.cursor_row, self.cursor_col)]

    def __str__(self) -> str:
        """Method that gives a formatted version of the board with row/col labels"""

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
            f"\n{NL.join([f'{row_labels[idx]}{PADDING}{u200b.join(row)}' for idx, row in enumerate(self.board)])}"
        )

    @property
    def str(self) -> str:
        """Method that gives a formatted version of the board without row/col labels"""

        return f"{NL.join([f'{u200b.join(row)}' for row in self.board])}"

    @property
    def board(self) -> np.ndarray:
        return self.board_history[self.board_index]

    @board.setter
    def board(self, board: np.ndarray):
        self.board_history.append(board)
        self.board_index += 1

    @property
    def backup_board(self) -> np.ndarray:
        return self.board_history[self.board_index - 1]

    def modify(
        self,
        *,
        height: Optional[int] = None,
        width: Optional[int] = None,
        background: Optional[str] = None,
    ) -> Board:
        """Method to modify attributes of board while conserving the centre (aka extends of crops board equally on opposite sides)"""

        height = height or self.height
        width = width or self.width
        background = background or self.background

        if all(
            (self.height == height, self.width == width, self.background == background)
        ):  # Return if none of the attributes have been changed
            return self

        overlay = self.board
        base = np.full((height, width), background, dtype="object")

        # Coordinates of the centre of the overlay board
        overlay_centre = Coords(overlay.shape[1] // 2, overlay.shape[0] // 2)
        # Coordinates of the centre of the base board
        base_centre = Coords(base.shape[1] // 2, base.shape[0] // 2)
        # Difference between the centres
        centre_diff = Coords(
            base_centre.x - overlay_centre.x, base_centre.y - overlay_centre.y
        )

        # Coordinates where the overlay board should crop from
        # x = overlay's centre's width MINUS base's centre's width, if greater than 0, else 0
        # y = overlay's centre's height MINUS base's centre's height, if greater than 0, else 0
        # Meaning that if base is larger than overlay, it will include from the start of overlay
        overlay_from = Coords(max(centre_diff.ix, 0), max(centre_diff.iy, 0))
        # Coordinates where the overlay board should crop to
        # x = base's total width MINUS its centre's x-coord PLUS overlay's centre's x-coord
        # y = base's total height MINUS its centre's y-coord PLUS overlay's centre's y-coord
        # This formula gives an optimal value to crop the overlay board *to*, for both
        # smaller and larger overlay boards
        overlay_to = Coords(
            (base.shape[1] - base_centre.x) + overlay_centre.x,
            (base.shape[0] - base_centre.y) + overlay_centre.y,
        )

        # Coordinates where the base board should paste from
        # x = base's centre's width MINUS overlay's centre's width, if bigger than 0, else 0
        # y = base's centre's height MINUS overlay's centre's height, if bigger than 0, else 0
        # Meaning that if overlay is larger than base, it will start pasting from the start of base
        base_overlay_from = Coords(max(centre_diff.x, 0), max(centre_diff.y, 0))
        # Coordinates where the base board should paste to
        # x = whichever is less b/w base board's width and overlay board's width PLUS x-coord of beginning (for respective offset)
        # y = whichever is less b/w base board's height and overlay board's height PLUS y-coord of beginning (for respective offset)
        base_overlay_to = Coords(
            min(overlay.shape[1], base.shape[1]) + base_overlay_from.x,
            min(overlay.shape[0], base.shape[0]) + base_overlay_from.y,
        )

        # Crops overlay board if necessary (i.e. if base < overlay)
        overlay = overlay[overlay_from.y : overlay_to.y, overlay_from.x : overlay_to.x]
        # Pastes cropped overlay board on top of the selected portion of base board
        base[
            base_overlay_from.y : base_overlay_to.y,
            base_overlay_from.x : base_overlay_to.x,
        ] = overlay
        return Board.from_board(base, background=background)

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

        colour_emoji = discord.PartialEmoji.from_str(colour)
        colour_pixel = (
            colour_emoji.id if colour_emoji.is_custom_emoji() else colour_emoji.name
        )

        cursor_matches = []
        for row, col in coords:
            board_emoji = discord.PartialEmoji.from_str(self.board[row, col])
            board_pixel = (
                board_emoji.id if board_emoji.is_custom_emoji() else board_emoji.name
            )
            if board_pixel == colour_pixel:
                cursor_matches.append(True)
            else:
                cursor_matches.append(False)
        if all(cursor_matches):
            return False

        colour_emoji = discord.PartialEmoji.from_str(colour)
        if colour_emoji.is_custom_emoji():
            colour_emoji.name = "e"
        colour = str(colour_emoji)

        self.board_history = self.board_history[: self.board_index + 1]
        self.board = self.board.copy()

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

    def save(self) -> Image.Image:
        line_spacing = -4
        node_spacing = -2

        w = self.width * (EMOJI_SIZE + node_spacing * 2) - node_spacing * 2
        h = self.height * (EMOJI_SIZE + line_spacing) - line_spacing
        with Image.new("RGBA", (w, h), (255, 255, 255, 0)) as image:
            with Pilmoji(image) as pilmoji:
                pilmoji.text(
                    xy=(0, 0),
                    text=self.str,
                    fill=(0, 0, 0),
                    font=FONT(EMOJI_SIZE),
                    spacing=line_spacing,
                    node_spacing=node_spacing,
                )
            return image

    @classmethod
    def from_board(
        cls, board: np.ndarray, *, background: Optional[str] = TRANSPARENT_EMOJI
    ):
        height = len(board)
        width = len(board[0])

        board_obj = cls(height=height, width=width, background=background)
        board_obj.board_history = [board]

        return board_obj

    @classmethod
    def from_str(cls, string: str, *, background: Optional[str] = None) -> Board:
        lines = string.split("\n")[2:]
        board = []
        for line in lines:
            board.append(line.split(PADDING)[-1].split("\u200b"))
        board = cls.from_board(np.array(board, dtype="object"), background=background)
        board.clear_cursors()
        return board


class ToolMenu(discord.ui.Select):
    def __init__(
        self,
        view: DrawView,
        *,
        options: Optional[List[discord.SelectOption]] = None,
    ):
        self.tool_list: List[Tool] = [
            BrushTool(view),
            EraseTool(view),
            EyedropperTool(view),
            FillTool(view),
            ReplaceTool(view),
            DarkenTool(view),
            LightenTool(view),
        ]

        default_options: List[discord.SelectOption] = [
            discord.SelectOption(
                label=tool.name,
                emoji=tool.emoji,
                value=tool.name.lower(),
                description=f"{tool.description}{' (Used automatically)' if tool.autouse is True else ''}",
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

    def value_to_option(
        self, value: Union[str, int]
    ) -> Union[None, discord.SelectOption]:
        return value_to_option_dict(self).get(value)

    def set_default(self, def_option: discord.SelectOption):
        for option in self.options:
            option.default = False
        def_option.default = True

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        value = self.values[0]
        tool = self.tools[value]

        # If the tool selected is one of these,
        # use it directly instead of equipping
        edit: bool = True  # This var is to decide whether or not to edit the message, depending on if the tool was used successfully
        if tool.autouse is True:
            edit = await tool.use(interaction=interaction)
        # Else, equip the tool (to the primary tool button slot)
        else:
            self.view.primary_tool = tool
            self.view.load_items()
            self.set_default(self.value_to_option(value))

        if edit:
            await self.view.edit_message(interaction)


class ColourMenu(discord.ui.Select):
    def __init__(
        self,
        *,
        options: Optional[List[discord.SelectOption]] = None,
        background: str,
    ):
        default_options: List[discord.SelectOption] = [
            *base_colour_options(),
            discord.SelectOption(
                label="Mix Colours", emoji=MIX_COLOURS_EMOJI, value="mix"
            ),
            discord.SelectOption(
                label="Add Colour(s)",
                emoji=ADD_COLOURS_EMOJI,
                value="colour",
            ),
            discord.SelectOption(
                label="Add Emoji(s)",
                emoji=ADD_EMOJIS_EMOJI,
                value="emoji",
            ),
        ]
        options = options if options else default_options
        self.END_INDEX = len(default_options)  # The ending index of default options
        for option in options:
            if str(option.emoji) == background and not option.label.endswith(" (bg)"):
                option.label += " (bg)"

        super().__init__(
            placeholder="🎨 Palette",
            options=options,
        )

        self.view: DrawView

    def value_to_option(
        self, value: Union[str, int]
    ) -> Union[None, discord.SelectOption]:
        return value_to_option_dict(self).get(value)

    def emoji_to_option(
        self, emoji: Union[discord.Emoji, discord.PartialEmoji]
    ) -> Union[None, discord.SelectOption]:
        if isinstance(emoji, discord.Emoji):
            identifier = emoji.id
        else:
            identifier = emoji.name if emoji.is_unicode_emoji() else emoji.id

        return emoji_to_option_dict(self).get(identifier)

    def append_option(
        self, option: discord.SelectOption
    ) -> Tuple[bool, Union[discord.SelectOption, None]]:
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
        added_emojis: Dict[Union[int, str], AddedEmoji] = {}
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
            return await notification.edit("Aborted.", interaction=interaction)

        if any(
            ("Added" in added_emoji.status for added_emoji in added_emojis.values())
        ):
            self.board.cursor = self.options[-1].value
            self.set_default(self.options[-1])

        await notification.edit(
            ("\n".join(response))[
                : EMBED_FIELD_CHAR_LIMIT - len(self.view.embed.fields[0].value)
            ]
        )
        await self.view.edit_message(interaction)

    def extract_emojis(self, content: str) -> List[SentEmoji]:
        # Get any unicode emojis from the content
        # and list them as SentEmoji objects
        unicode_emojis = [
            SentEmoji(
                emoji=discord.PartialEmoji.from_str(self.view.board.un_cursor(emoji)),
                index=content.index(emoji),
            )
            for emoji in emoji.distinct_emoji_list(content)
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
        return list(sent_emojis)

    def set_default(self, def_option: discord.SelectOption):
        for option in self.options:
            option.default = False
        def_option.default = True

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        def check(msg):
            return msg.author == interaction.user

        # These need to be defined here because the class does not have a view when initiated
        self.ctx = self.view.ctx
        self.bot = self.view.bot
        self.board = self.view.board

        # Set max values to 1 everytime the menu is used
        initial_max_values = self.max_values
        self.max_values = 1

        # If the Add Colour option was selected. Always takes first priority
        if "colour" in self.values:
            notification, msg = await self.view.wait_for(
                (
                    "Please type all the colours you want to add. They can be either or all of:"
                    "\n• The hex codes (e.g. `ff64c4` or `ff64c4ff` to include alpha) **separated by space**,"
                    "\n• The RGB(A) values separated by space or comma or both (e.g. `(255 100 196)` or `(255, 100, 196, 125)`) of each colour **surrounded by brackets**"
                    "\n• Any emoji whose main colour you want to extract (e.g. 🐸 will give 77b255)"
                    "\n• Any image file (first 5 abundant colours will be extracted)."
                ),
                emoji=ADD_COLOURS_EMOJI,
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

                emoji = await self.bot.upload_emoji(
                    colour, draw_view=self.view, interaction=interaction
                )

                sent_emojis.append(SentEmoji(emoji=emoji, index=match.start()))

            emoji_matches = self.extract_emojis(content)
            for match in emoji_matches:
                colour = await Colour.from_emoji(match.emoji)
                emoji = await self.bot.upload_emoji(
                    colour, draw_view=self.view, interaction=interaction
                )

                sent_emojis.append(SentEmoji(emoji=emoji, index=match.index))

            if msg.attachments:
                # Extract from first attachment
                attachment_colours = await Colour.from_attachment(msg.attachments[0])
                for colour in attachment_colours:
                    emoji = await self.bot.upload_emoji(
                        colour, draw_view=self.view, interaction=interaction
                    )

                    sent_emojis.append(
                        SentEmoji(
                            emoji=emoji,
                            index=max([e.index for e in sent_emojis] + [0]) + 1,
                        )
                    )

            sent_emojis.sort(key=lambda emoji: emoji.index)

            added_emojis = self.append_sent_emojis(sent_emojis)

            await self.added_emojis_respond(
                added_emojis, notification=notification, interaction=interaction
            )

        # First it checks if the Add Emoji option was selected. Takes second priority
        elif "emoji" in self.values:
            notification, msg = await self.view.wait_for(
                "Please send a message containing the emojis you want to add to your palette. E.g. `😎 I like turtles 🐢`",
                emoji=ADD_EMOJIS_EMOJI,
                interaction=interaction,
                check=check,
            )
            if msg is None:
                return

            content = msg.content

            sent_emojis = self.extract_emojis(content)
            added_emojis = self.append_sent_emojis(sent_emojis)

            await self.added_emojis_respond(
                added_emojis, notification=notification, interaction=interaction
            )

        # If user has chosen to Mix Colours
        elif "mix" in self.values:
            if initial_max_values > 1:
                self.max_values = 1
                await self.view.create_notification(
                    f"Mixing disabled.",
                    emoji=MIX_COLOURS_EMOJI,
                    interaction=interaction,
                )
            else:
                self.max_values = len(self.options)
                await self.view.create_notification(
                    f"Mixing enabled. You can now select multiple colours/emojis to mix their primary colours.",
                    emoji=MIX_COLOURS_EMOJI,
                    interaction=interaction,
                )
            return

        # If multiple options were selected
        elif len(self.values) > 1:
            selected_options = [self.value_to_option(value) for value in self.values]

            selected_emojis = [str(option.emoji) for option in selected_options]
            notification = await self.view.create_notification(
                f'Mixing colours {" and ".join(selected_emojis)} ...',
                emoji=MIX_COLOURS_EMOJI,
                interaction=interaction,
            )

            colours = [await Colour.from_emoji(emoji) for emoji in selected_emojis]

            mixed_colour = Colour.mix_colours(colours)

            emoji = discord.PartialEmoji.from_str(
                str(
                    await self.bot.upload_emoji(
                        mixed_colour, draw_view=self.view, interaction=interaction
                    )
                )
            )

            option = discord.SelectOption(
                label=mixed_colour.hex,
                emoji=emoji,
                value=str(emoji),
            )
            replaced, returned_option = self.append_option(option)

            self.board.cursor = option.value
            self.set_default(option)

            await notification.edit(
                f'Mixed colours:\n{" + ".join(selected_emojis)} = {emoji}'
                + (f" (replaced {returned_option.emoji})." if replaced else "")
            )
            await self.view.edit_message(interaction)

        # If only one option was selected
        elif self.board.cursor != (value := self.values[0]):
            self.board.cursor = value
            self.set_default(self.value_to_option(value))

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
        self.bot: Bot = self.ctx.bot

        self.tool_menu: ToolMenu = ToolMenu(self, options=tool_options)
        self.colour_menu: ColourMenu = ColourMenu(
            options=colour_options, background=board.background
        )
        self.primary_tool: Tool = self.tool_menu.tools["brush"]

        self.reaction_menu: bool = True
        self.auto: bool = False
        self.select: bool = False

        self.disabled: bool = False
        self.secondary_page: bool = False
        self.load_items()

        self.response: discord.Message = None
        self.lock: asyncio.Lock = self.bot.lock

        self.notifications: List[Notification] = [Notification(view=self)]

    @property
    def embed(self):
        embed = self.bot.Embed(title=f"{self.ctx.author}'s drawing board.")

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
        if any((len(n.content) != 0 for n in self.notifications)):
            embed.add_field(
                name="Notifications",
                value="\n\n".join(
                    [
                        (
                            f"{str(n.emoji)} "
                            + (
                                n.content if idx == 0 else n.get_truncated_content()
                            ).replace("\n", "\n> ")
                        )  # Put each notification into seperate quotes
                        if len(n.content) != 0
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

    def reaction_check(self, reaction: discord.Reaction, user: discord.User):
        return reaction.message.id == self.response.id and user.id == self.ctx.author.id

    async def start(self):
        response = self.response

        await response.add_reaction(AUTO_DRAW_EMOJI)
        await response.add_reaction(SELECT_EMOJI)

        while self.reaction_menu is True:
            ### This block wait_for's for both addition and removal of reactions
            done, pending = await asyncio.wait(
                [
                    self.bot.loop.create_task(
                        self.bot.wait_for(
                            "reaction_add", check=self.reaction_check, timeout=None
                        )
                    ),
                    self.bot.loop.create_task(
                        self.bot.wait_for(
                            "reaction_remove", check=self.reaction_check, timeout=None
                        )
                    ),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            reaction, user = done.pop().result()
            for future in done:
                future.exception()
            for future in pending:
                future.cancel()
            ###

            if str(reaction.emoji) == AUTO_DRAW_EMOJI:
                self.auto = not self.auto

            if str(reaction.emoji) == SELECT_EMOJI:
                if self.select is False:
                    self.board.initial_coords = (
                        self.board.cursor_row,
                        self.board.cursor_col,
                    )
                    (
                        self.board.initial_row,
                        self.board.initial_col,
                    ) = self.board.initial_coords
                    self.select = not self.select
                elif self.select is True:
                    self.board.clear_cursors()
                    self.select = not self.select
                    await self.edit_message()

    async def create_notification(
        self,
        content: Optional[str] = None,
        *,
        emoji: Optional[
            Union[discord.PartialEmoji, discord.Emoji]
        ] = discord.PartialEmoji.from_str("🔔"),
        interaction: Optional[discord.Interaction] = None,
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

        self.reaction_menu = False

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
        emoji: Optional[Union[str, discord.PartialEmoji, discord.Emoji]] = None,
        interaction: discord.Interaction,
        check: Callable = lambda x: x,
        delete_msg: bool = True,
    ) -> Tuple[Notification, discord.Message]:
        if isinstance(emoji, str):
            emoji = discord.PartialEmoji.from_str(emoji)

        notification = None
        msg = None
        if self.lock.locked():
            await interaction.followup.send(
                "Another message is being waited for, please wait until that process is complete.",
                ephemeral=True,
            )
            return notification, msg

        async with self.disable(interaction=interaction, first_edit=False):
            if content is not None:
                notification = await self.create_notification(
                    content + "\nSend anything else to abort.",
                    emoji=emoji,
                    interaction=interaction,
                )
            else:
                notification = await self.create_notification(content, emoji=emoji)

            async with self.lock:
                try:
                    msg = await self.bot.wait_for("message", timeout=30, check=check)
                except asyncio.TimeoutError:
                    await notification.edit(
                        "Timed out, aborted.", interaction=interaction
                    )
                else:
                    if delete_msg is True:
                        await msg.delete()
        if msg is None:  # If timed out, update after re-enabling
            await self.edit_message(interaction)
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
            self.add_item(self.set_cursor)
            self.add_item(self.right)
            self.add_item(self.placeholder_button)

            self.add_item(self.primary_tool)
            self.add_item(self.down_left)
            self.add_item(self.down)
            self.add_item(self.down_right)
            self.add_item(self.save_btn)

        elif self.secondary_page is True:
            self.add_item(self.stop_button)
            self.add_item(self.up_left)
            self.add_item(self.up)
            self.add_item(self.up_right)
            self.add_item(self.secondary_page_button)

            self.add_item(self.clear)
            self.add_item(self.left)
            self.add_item(self.set_cursor)
            self.add_item(self.right)
            self.add_item(self.placeholder_button)

            self.add_item(self.primary_tool)
            self.add_item(self.down_left)
            self.add_item(self.down)
            self.add_item(self.down_right)
            self.add_item(self.save_btn)

        self.update_buttons()

    def update_buttons(self):
        self.secondary_page_button.style = (
            discord.ButtonStyle.green
            if self.secondary_page
            else discord.ButtonStyle.grey
        )

        self.undo.disabled = self.board.board_index == 0 or self.disabled
        self.undo.label = f"{self.board.board_index} ↶"
        self.redo.disabled = (
            self.board.board_index == len(self.board.board_history) - 1
        ) or self.disabled
        self.redo.label = (
            f"↷ {(len(self.board.board_history) - 1) - self.board.board_index}"
        )

    @asynccontextmanager
    async def disable(
        self,
        *,
        interaction: discord.Interaction,
        first_edit: Optional[bool] = True,
        second_edit: Optional[bool] = False,
    ):
        disabled = []
        try:
            for child in self.children:
                if child.disabled is True:
                    disabled.append(child)
                    continue
                child.disabled = True
            self.disabled = True
            if first_edit is True:
                await self.edit_message(interaction)
            yield True
        finally:
            for child in self.children:
                if child not in disabled:
                    child.disabled = False
            self.disabled = False
            if second_edit is True:
                await self.edit_message(interaction)

    async def edit_message(self, interaction: Optional[discord.Interaction] = None):
        self.update_buttons()
        try:
            if interaction is None:
                await self.response.edit(embed=self.embed, view=self)
            else:
                await interaction.edit_original_message(embed=self.embed, view=self)

            # print(f'[{datetime.datetime.strftime(datetime.datetime.utcnow() + datetime.timedelta(), "%H:%M:%S")}]: Edited')
        except discord.HTTPException as error:
            if match := re.search(
                "In embeds\.\d+\.description: Must be 4096 or fewer in length\.",
                error.text,
            ):  # If the description reaches char limit
                content = f"Max characters reached ({len(self.embed.description)}). Please remove some custom emojis from the board.\nCustom emojis take up more than 20 characters each, while most unicode/default ones take up 1!\nMaximum is 4096 characters due to discord limitations."

                if interaction is None:
                    await self.response.channel.send(
                        content=content,
                    )
                else:
                    await interaction.followup.send(
                        content=content,
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
                content = f"The {removed_option.emoji} emoji was not found for some reason, so the option was removed aswell. Please try again."
                self.board.cursor = self.board.background

                if interaction is None:
                    await self.response.channel.send(
                        content=content,
                    )
                else:
                    await interaction.followup.send(
                        content=content,
                        ephemeral=True,
                    )
                await self.edit_message(interaction)
            else:
                if interaction is None:
                    await self.response.channel.send(error)
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
            await self.primary_tool.use(interaction=interaction)
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

    @discord.ui.button(emoji=SET_CURSOR_EMOJI, style=discord.ButtonStyle.blurple)
    async def set_cursor(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        def check(m):
            return m.author == interaction.user

        notification, msg = await self.wait_for(
            'Please type the cell you want to move the cursor to. e.g. "A1", "a1", "A10", "A", "10", etc.',
            emoji=SET_CURSOR_EMOJI,
            interaction=interaction,
            check=check,
        )
        if msg is None:
            return
        cell = msg.content.upper()

        ABC = ALPHABETS[: self.board.cursor_row_max + 1]
        NUM = NUMBERS[: self.board.cursor_col_max + 1]

        # There is absolutely no reason to use regex here but fuck it we ball
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

    @discord.ui.button(
        emoji="<:right:1032565019352764438>", style=discord.ButtonStyle.blurple
    )
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 0
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

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

    @discord.ui.button(emoji=SAVE_EMOJI, style=discord.ButtonStyle.green)
    async def save_btn(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer(thinking=True)
        image = await self.bot.loop.run_in_executor(None, self.board.save)
        filename = "image"
        file = image_to_file(image, filename=filename)

        embed = self.bot.Embed(title=f"{interaction.user}'s masterpiece ✨")
        embed.set_image(url=f"attachment://{filename}.png")
        await interaction.followup.send(embed=embed, file=file)


class Draw(commands.Cog):
    """Make pixel art on discord!"""

    def __init__(self, bot: Bot):
        self.bot = bot

    display_emoji = "🖌️"

    @commands.bot_has_permissions(external_emojis=True)
    @commands.group(
        name="draw",
        aliases=("paint", "pixelart"),
        case_insensitive=True,
        brief="Make pixel art on discord!",
        help="WIP",
        description="Create pixel art using buttons and dropdown menus",
        invoke_without_command=True,
    )
    async def draw(
        self,
        ctx: CustomContext,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: Literal[
            "🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜", "transparent"
        ] = TRANSPARENT_KEY,
    ) -> None:
        if MIN_HEIGHT_OR_WIDTH > height > MAX_HEIGHT_OR_WIDTH:
            return await ctx.send("Height must be atleast 5 and atmost 17")

        if MIN_HEIGHT_OR_WIDTH > width > MAX_HEIGHT_OR_WIDTH:
            return await ctx.send("Width must be atleast 5 and atmost 17")

        if background == TRANSPARENT_KEY:
            background = TRANSPARENT_EMOJI
        board = (height, width, background)

        start_view = StartView(ctx=ctx, board=board)
        await start_view.start()

    async def board_from_message(
        self, ctx: CustomContext, *, message: discord.Message
    ) -> Union[Tuple[Board, ToolMenu, ColourMenu], None]:
        if message.author.id not in (self.bot.TEST_BOT_ID, self.bot.MAIN_BOT_ID):
            raise InvalidDrawMessageError("Not a message from the bot.")
        if len(message.embeds) == 0:
            raise InvalidDrawMessageError("Not a drawing embed.")
        if "drawing board" not in message.embeds[0].title:
            raise InvalidDrawMessageError("Not a drawing embed.")

        description = message.embeds[0].description

        old_view = discord.ui.View.from_message(message, timeout=0)
        if len(old_view.children) > 2:
            tool_options = old_view.children[0].options
            colour_options = old_view.children[1].options
        else:
            tool_options = None
            colour_options = old_view.children[0].options

        for option in colour_options:
            if option.label.endswith(" (bg)"):
                background = str(option.emoji)

        board = Board.from_str(description, background=background)
        return board, tool_options, colour_options

    @draw.command(
        name="copy",
        brief="Copy a drawing.",
        help="Copy a drawing from an embed by replying to the message or using message link.",
        description="Allows you to copy a drawing that was done with the `draw` command. This will also copy the palette! You can copy by replying to such a message or by providing the message link (or ID).",
    )
    async def copy(
        self,
        ctx: CustomContext,
        message_link: Optional[discord.Message] = None,
    ):
        message = message_link
        if ref := ctx.message.reference:
            message = ref.resolved
        elif message_link is None or not isinstance(message_link, discord.Message):
            return await ctx.send_help(ctx.command)

        board, tool_options, colour_options = await self.board_from_message(
            ctx, message=message
        )
        if not isinstance(board, Board):
            return

        start_view = StartView(
            ctx=ctx,
            board=board,
            tool_options=tool_options,
            colour_options=colour_options,
        )
        await start_view.start()

    @draw.command(
        name="save",
        aliases=("export",),
        brief="Quickly save/export a drawing",
        help="Quickly save/export a drawing by replying to a drawing message or using message link.",
    )
    async def save(
        self, ctx: CustomContext, message_link: Optional[discord.Message] = None
    ):
        await ctx.typing()
        message = message_link
        if ref := ctx.message.reference:
            message = ref.resolved
        elif message_link is None or not isinstance(message_link, discord.Message):
            return await ctx.send_help(ctx.command)

        board, _, _ = await self.board_from_message(ctx, message=message)
        if not isinstance(board, Board):
            return

        image = await self.bot.loop.run_in_executor(None, board.save)
        filename = "image"
        file = image_to_file(image, filename=filename)

        embed = self.bot.Embed(
            title=message.embeds[0].title.replace("drawing board.", "masterpiece ✨")
        )
        embed.set_image(url=f"attachment://{filename}.png")
        await ctx.reply(embed=embed, file=file)


async def setup(bot):
    await bot.add_cog(Draw(bot))
