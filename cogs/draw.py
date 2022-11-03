import asyncio
from typing import Callable, Optional, Union, Literal, List, Dict, Tuple, TypeVar
import io
from functools import cached_property
import re
import copy

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
)
from .draw_utils.emoji import (
    draw_emoji,
    SentEmoji,
    AddedEmoji,
)


D = TypeVar("D", bound="DrawView")


class StartView(discord.ui.View):
    def __init__(self, *, ctx: commands.Context, draw_view: D):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.draw_view = draw_view

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

    @discord.ui.button(label="Create", style=discord.ButtonStyle.green)
    async def create(self, interaction: discord.Interaction, button: discord.Button):
        await interaction.response.defer()

        response = await interaction.followup.send(
            embed=self.draw_view.embed, view=self.draw_view
        )
        self.draw_view.response = response
        await response.edit(
            embed=self.draw_view.embed, view=self.draw_view
        )  # This is necessary because custom emojis only render when a followup is edited ◉_◉

        await self.response.edit(view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        await self.response.edit(view=None)
        self.stop()


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
        background: Literal["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜"] = "⬜",
    ) -> None:
        bg = background
        if height < 5 or height > 17:
            return await ctx.send("Height must be atleast 5 and atmost 17")

        if width < 5 or width > 17:
            return await ctx.send("Width must be atleast 5 and atmost 17")

        board = Board(height=height, width=width, background=background)
        draw_view = DrawView(board, ctx=ctx)

        start_view = StartView(ctx=ctx, draw_view=draw_view)
        response = await ctx.send(
            f"Create new draw board with `{height = }`, `{width = }` and `{bg = }`?",
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

        options = discord.ui.View.from_message(message, timeout=0).children[0].options
        for option in options:
            if option.label.endswith(" (base)"):
                bg = str(option.emoji)

        board_obj = Board.from_board(board=board, background=bg)
        draw_view = DrawView(board_obj, ctx=ctx, selectmenu_options=options)
        draw_view.board.cursor = description.split(PADDING)[0]

        start_view = StartView(ctx=ctx, draw_view=draw_view)
        response = await ctx.send(
            content="Create a copy of this board? (Due to discord limitations, custom emojis may not render here)",
            embed=draw_view.embed,
            view=start_view,
        )
        start_view.response = response


B = TypeVar("B", bound="Board")


class Board:
    def __init__(
        self,
        *,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: Literal["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜"] = "⬜",
    ) -> None:
        self.height: int = height
        self.width: int = width
        self.background: str = background

        self.initial_board: np.array = np.full(
            (height, width), background, dtype="object"
        )
        self.board: np.array = self.initial_board.copy()
        self.backup_board: np.array = self.initial_board.copy()
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
        self.draw_cursor()

        self.auto = False
        self.select = False

    @classmethod
    def from_board(cls, board: np.array, *, background: Optional[str] = "⬜"):
        height = len(board)
        width = len(board[0])

        board_obj = cls(height=height, width=width, background=background)
        board_obj.board = board

        return board_obj

    def clear(self):
        self.board[:] = self.background
        self.clear_cursors()
        self.draw_cursor()

    def un_cursor(self, value):
        return inv_CURSOR.get(value, value)

    def draw_cursor(
        self,
        row: Optional[int] = None,
        col: Optional[int] = None,
        *,
        colour: Optional[str] = None,
    ):
        row = row if row is not None else self.cursor_row
        col = col if col is not None else self.cursor_col
        colour = colour if colour is not None else self.board[row, col]

        self.board[row, col] = CURSOR.get(colour, colour)

    def clear_cursors(self, *, empty: Optional[bool] = False):
        for x, row in enumerate(self.board):
            for y, _ in enumerate(row):
                cell_tuple = (x, y)
                self.board[cell_tuple] = self.un_cursor(self.board[cell_tuple])

        self.cursor_coords = (
            [(self.cursor_row, self.cursor_col)] if empty is False else []
        )

    def move_cursor(self, row_move: Optional[int] = 0, col_move: Optional[int] = 0):
        self.clear_cursors()
        self.cursor_row = (self.cursor_row + row_move) % (self.cursor_row_max + 1)
        self.cursor_col = (self.cursor_col + col_move) % (self.cursor_col_max + 1)

        if self.select is not True:
            self.cursor_coords = [(self.cursor_row, self.cursor_col)]
            return

        self.final_coord = (self.cursor_row, self.cursor_col)
        self.final_row, self.final_col = self.final_coord

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

    def draw(
        self,
        colour: Optional[Union[str, bool]] = None,
        *,
        fill_replace: Optional[bool] = False,
    ):
        if self.auto is True and colour is None:
            colour = self.cursor

        if fill_replace is True:
            colour = self.cursor
            to_replace = self.un_cursor(self.board[self.cursor_row, self.cursor_col])
            self.board[self.board == to_replace] = colour

        if colour is not False:
            for row, col in self.cursor_coords:
                self.draw_cursor(row, col, colour=colour)
        self.backup_board = self.board.copy()


C = TypeVar("C", bound="Colour")


class Colour:
    # RGB_A accepts RGB values and an optional Alpha value
    def __init__(self, RGB_A: Tuple[int], *, bot: commands.Bot):
        self.RGBA = RGB_A if len(RGB_A) == 4 else (*RGB_A, 255)
        self.RGB = self.RGBA[:3]
        self.R, self.G, self.B, self.A = self.RGBA

        self.bot = bot
        self.loop = self.bot.loop

    @cached_property
    def hex(self) -> str:
        return "%02x%02x%02x" % self.RGB

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
    async def from_emoji(cls, emoji: str, *, bot: commands.Bot) -> C:
        image = await bot.loop.run_in_executor(None, draw_emoji, emoji)
        colors = [
            color
            for color in sorted(
                image.getcolors(image.size[0] * image.size[1]),
                key=lambda c: c[0],
                reverse=True,
            )
            if color[1][-1] > 0
        ]

        return cls(colors[0][1], bot=bot)

    @classmethod
    def mix_colours(cls, colours: List[Tuple[int, C]], *, bot: commands.Bot) -> C:
        colours = [
            colour.RGBA if isinstance(colour, Colour) else colour for colour in colours
        ]
        total_weight = len(colours)

        return cls(
            tuple(round(sum(colour) / total_weight) for colour in zip(*colours)),
            bot=bot,
        )


class DrawSelectMenu(discord.ui.Select):
    def __init__(
        self,
        *,
        options: Optional[List[discord.SelectOption]] = None,
        background: str,
    ):
        default_options = [
            discord.SelectOption(label="Red", emoji="🟥", value="🟥"),
            discord.SelectOption(label="Orange", emoji="🟧", value="🟧"),
            discord.SelectOption(label="Yellow", emoji="🟨", value="🟨"),
            discord.SelectOption(label="Green", emoji="🟩", value="🟩"),
            discord.SelectOption(label="Blue", emoji="🟦", value="🟦"),
            discord.SelectOption(label="Purple", emoji="🟪", value="🟪"),
            discord.SelectOption(label="Brown", emoji="🟫", value="🟫"),
            discord.SelectOption(label="Black", emoji="⬛", value="⬛"),
            discord.SelectOption(label="White", emoji="⬜", value="⬜"),
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
        return self.emoji_to_option_dict.get(
            emoji.name if emoji.is_unicode_emoji() else emoji.id
        )

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
    ) -> Union[discord.PartialEmoji, None]:
        replaced_option = None
        if self.emoji_to_option(option.emoji) is not None:
            return replaced_option

        if len(self.options) == 25:
            replaced_option = self.options.pop(self.END_INDEX)
            replaced_option.emoji.name = replaced_option.label

        super().append_option(option)
        return replaced_option

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # These need to be defined here because it does not have a view when initiated
        self.ctx = self.view.ctx
        self.bot = self.view.bot
        self.board = self.view.board
        if "emoji" in self.values:

            def check(m):
                return m.author == interaction.user

            res, msg = await self.view.wait_for(
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
                SentEmoji(emoji=emoji, index=content.index(emoji))
                for emoji in emojis.get(content)
            ]
            # Get any flag/regional indicator emojis from the content
            # and list them as SentEmoji objects
            flag_emojis = [
                SentEmoji(
                    emoji=emoji.group(0),
                    index=emoji.start(),
                )
                for emoji in re.finditer("[\U0001F1E6-\U0001F1FF]", content)
            ]
            # Get any custom emojis from the content
            # and list them as SentEmoji objects
            custom_emojis = [
                SentEmoji(emoji=emoji.group(0), index=emoji.start())
                for emoji in re.finditer(r"<a?:[a-zA-Z0-9_]+:\d+>", content)
            ]

            # Gather all the emojis and sort them by index
            sent_emojis = sorted(
                unicode_emojis + flag_emojis + custom_emojis,
                key=lambda emoji: emoji.index,
            )

            added_emojis = {}
            for num, sent_emoji in enumerate(sent_emojis):
                emoji_check = discord.PartialEmoji.from_str(sent_emoji.emoji)
                emoji = copy.copy(emoji_check)

                if self.emoji_to_option(emoji):
                    added_emoji = AddedEmoji(
                        sent_emoji=sent_emoji, emoji=emoji, status="Already exists."
                    )

                else:
                    added_emoji = AddedEmoji(
                        sent_emoji=sent_emoji,
                        emoji=emoji,
                        status="Added.",
                        name="e" if emoji.is_custom_emoji() else emoji.name,
                    )

                added_emojis[
                    emoji.name if emoji.is_unicode_emoji() else emoji.id
                ] = added_emoji

            replaced_emojis = {}
            for added_emoji in added_emojis.values():
                if added_emoji.status != "Added.":
                    continue

                option = discord.SelectOption(
                    label=added_emoji.original_name,
                    emoji=added_emoji.emoji,
                    value=str(added_emoji.emoji),
                )
                replaced_option = self.append_option(option)
                if replaced_option is not None:
                    replaced_emoji = replaced_option.emoji
                    replaced_emojis[
                        replaced_emoji.id if replaced_emoji.id else replaced_emoji.name
                    ] = AddedEmoji.from_option(
                        replaced_option,
                        status=f"Replaced by {added_emoji}.",
                        sent_emoji=SentEmoji(emoji=replaced_emoji),
                    )
                    added_emoji.status = f"Added (replaced {replaced_emoji})."

            # added_emojis.update(replaced_emojis)
            added_emojis = {
                k: v for k, v in added_emojis.items() if k not in replaced_emojis
            }

            if len(self.options[self.END_INDEX :]) > 0:
                self.board.cursor = self.options[-1].value

            response = [
                f"%s - {added_emoji.status}" % added_emoji.emoji
                for added_emoji in added_emojis.values()
            ]
            if len(response) == 0:
                return await res.edit(content="Aborted")

            await self.view.edit_draw(interaction, False)
            await res.edit(content=("\n".join(response))[:2000])

        # If multiple options were selected
        elif len(self.values) > 1:
            selected_options = [self.value_to_option(value) for value in self.values]

            selected_emojis = [str(option.emoji) for option in selected_options]
            res = await interaction.followup.send(
                f'Mixing colours {" and ".join(selected_emojis)} ...'
            )

            colours = [
                await Colour.from_emoji(emoji, bot=self.bot)
                for emoji in selected_emojis
            ]

            mixed_colour = Colour.mix_colours(colours, bot=self.bot)

            emoji = discord.PartialEmoji.from_str(
                str(await self.upload_emoji(mixed_colour))
            )

            option = self.emoji_to_option(emoji)
            if option is not None:
                self.board.cursor = option.value
            else:
                option = discord.SelectOption(
                    label=" + ".join(
                        [
                            str(option.emoji)
                            if option.emoji.is_unicode_emoji()
                            else option.emoji.name
                            for option in selected_options
                        ]
                    ),  # mixed_colour.hex,
                    emoji=emoji,
                    value=str(emoji),
                )
                replaced_option = self.append_option(option)
                self.board.cursor = self.options[-1].value

            await self.view.edit_draw(interaction, False)
            await res.edit(
                content=f'Mixed colours:\n{" + ".join(selected_emojis)} = {emoji}'
                + (
                    f" (replaced {replaced_option.emoji})."
                    if replaced_option is not None
                    else ""
                )
            )

        elif self.board.cursor != self.values[0]:
            self.board.cursor = self.values[0]
            await self.view.edit_draw(interaction, False)


class DrawView(discord.ui.View):
    def __init__(
        self,
        board: Board,
        *,
        ctx: commands.Context,
        selectmenu_options: Optional[List[discord.SelectOption]] = None,
    ):
        super().__init__(timeout=600)
        self.secondary = False

        self.selectmenu: DrawSelectMenu = DrawSelectMenu(
            options=selectmenu_options, background=board.background
        )
        self.load_items()

        self.board: Board = board

        self.ctx: commands.Context = ctx
        self.bot: commands.Bot = self.ctx.bot
        self.response: discord.Message = None
        self.lock = self.bot.lock

    @property
    def embed(self):
        embed = discord.Embed(title=f"{self.ctx.author}'s drawing board.")

        cursor_rows = tuple(row for row, col in self.board.cursor_coords)
        cursor_cols = tuple(col for row, col in self.board.cursor_coords)
        row_labels = [
            (row if idx not in cursor_rows else ROW_ICONS_DICT[row])
            for idx, row in enumerate(self.board.row_labels)
        ]
        col_labels = [
            (col if idx not in cursor_cols else COLUMN_ICONS_DICT[col])
            for idx, col in enumerate(self.board.col_labels)
        ]

        # The actual board
        embed.description = (
            f"{self.board.cursor}{PADDING}{u200b.join(col_labels)}\n"
            f"\n{NEW_LINE.join([f'{row_labels[idx]}{PADDING}{u200b.join(row)}' for idx, row in enumerate(self.board.board)])}"
        )

        embed.set_footer(
            text=(
                f"The board looks wack? Try decreasing its size! Do {self.ctx.clean_prefix}help draw for more info."
                if any(
                    (len(self.board.row_labels) >= 10, len(self.board.col_labels) >= 10)
                )
                else f"You can customize this board! Do {self.ctx.clean_prefix}help draw for more info."
            )
        )
        return embed

    def stop_view(self):
        self.selectmenu.disabled = True

        self.clear_items()
        self.add_item(self.selectmenu)
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
                label=f"This interaction has timed out. Use {self.ctx.prefix}{self.ctx.command} for a new one.",
                style=discord.ButtonStyle.gray,
                disabled=True,
            )
        )
        await self.response.edit(embed=self.embed, view=self)
        self.stop()

    async def wait_for(
        self,
        content: str = "",
        *,
        interaction: discord.Interaction,
        check: Callable = lambda x: x,
        delete_msg: bool = True,
        ephemeral: bool = False,
    ):
        res = None
        msg = None
        if self.lock.locked():
            await interaction.followup.send(
                "Another message is being waited for, please wait until that process is complete.",
                ephemeral=True,
            )
            return res, msg

        res = await interaction.followup.send(content=content, ephemeral=ephemeral)
        async with self.lock:
            try:
                msg = await self.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                await res.edit(content="Timed out.")
            else:
                if delete_msg is True:
                    await msg.delete()
            return res, msg

    def load_items(self):
        self.clear_items()
        self.add_item(self.selectmenu)

        # This is necessary for "paginating" the view and different buttons
        if self.secondary is False:
            self.add_item(self.stop_button)
            self.add_item(self.secondary_button)
            self.add_item(self.placeholder_button)
            self.add_item(self.select_button)
            self.add_item(self.fill_bucket)

            self.add_item(self.eyedropper)
            self.add_item(self.up_left)
            self.add_item(self.up)
            self.add_item(self.up_right)
            self.add_item(self.placeholder_button)

            self.add_item(self.erase)
            self.add_item(self.left)
            self.add_item(self.auto_draw)
            self.add_item(self.right)
            self.add_item(self.placeholder_button)

            self.add_item(self.draw)
            self.add_item(self.down_left)
            self.add_item(self.down)
            self.add_item(self.down_right)
            self.add_item(self.set_cursor)

        elif self.secondary is True:
            self.add_item(self.stop_button)
            self.add_item(self.secondary_button)
            self.add_item(self.placeholder_button)
            self.add_item(self.select_button)
            self.add_item(self.fill_replace)

            self.add_item(self.eyedropper)
            self.add_item(self.up_left)
            self.add_item(self.up)
            self.add_item(self.up_right)
            self.add_item(self.placeholder_button)

            self.add_item(self.clear)
            self.add_item(self.left)
            self.add_item(self.auto_draw)
            self.add_item(self.right)
            self.add_item(self.placeholder_button)

            self.add_item(self.draw)
            self.add_item(self.down_left)
            self.add_item(self.down)
            self.add_item(self.down_right)
            self.add_item(self.set_cursor)

    @property
    def placeholder_button(self) -> discord.ui.Button:
        button = discord.ui.Button(
            label="\u200b",
            style=discord.ButtonStyle.gray,
            custom_id=str(len(self.children)),
        )
        button.callback = lambda interaction: interaction.response.defer()

        return button

    async def edit_draw(
        self,
        interaction: discord.Interaction,
        colour: Optional[Union[str, bool]] = None,
        *,
        fill_replace: Optional[bool] = False,
    ):
        if all(
            (
                colour is not None,
                all(
                    self.board[row, col] == CURSOR.get(colour, colour)
                    for row, col in self.cursor_cells
                ),
                self.auto is False,
            )
        ):
            return

        self.board.draw(colour, fill_replace=fill_replace)
        await self.edit_message(interaction)

    async def edit_message(self, interaction: discord.Interaction):
        try:
            await interaction.edit_original_message(embed=self.embed, view=self)
        except discord.HTTPException as error:
            if match := re.search(
                "In embeds\.\d+\.description: Must be 4096 or fewer in length\.",
                error.text,
            ):  # If the description reaches char limit
                self.board = self.board.backup_board
                await interaction.followup.send(
                    content="Max characters reached. Please remove some custom emojis from the board.\nCustom emojis take up more than 20 characters each, while most unicode/default ones take up 1!\nMaximum is 4096 characters due to discord limitations.",
                    ephemeral=True,
                )
                await self.edit_message(interaction)
            elif match := re.search(
                "In components\.\d+\.components\.\d+\.options\.(?P<option>\d+)\.emoji\.id: Invalid emoji",
                error.text,
            ):  # If the emoji of one of the options of the select menu is unavailable
                removed_option = self.selectmenu.options.pop(int(match.group("option")))
                self.board.cursor = self.board.background
                await interaction.followup.send(
                    content=f"The {removed_option.emoji} emoji was removed for some reason, so the option was removed aswell. Please try again.",
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
        self.board.move_cursor(row_move, col_move)
        await self.edit_draw(interaction)

    def toggle(
        self,
        obj,
        attribute: str,
        button: discord.ui.Button,
        *,
        switch_to: Optional[bool] = None,
    ):
        attr_value = getattr(obj, attribute)
        switch_to = switch_to if switch_to is not None else not attr_value
        setattr(obj, attribute, switch_to)

        if switch_to is True:
            button.style = discord.ButtonStyle.green
        elif switch_to is False:
            button.style = discord.ButtonStyle.grey

    # ------ buttons ------

    # 1st row
    @discord.ui.button(
        emoji="<:stop:1032565237242667048>", style=discord.ButtonStyle.danger
    )
    async def stop_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.stop_view()
        await self.edit_draw(interaction)
        self.stop()

    @discord.ui.button(
        emoji="<:clear:1032565244658204702>", style=discord.ButtonStyle.danger
    )
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.toggle(self, "secondary", self.secondary_button, switch_to=False)
        self.toggle(self.board, "auto", self.auto_draw, switch_to=False)
        self.toggle(self.board, "select", self.select_button, switch_to=False)
        self.board.clear()
        self.load_items()
        await self.edit_draw(interaction)

    @discord.ui.button(label="2nd", style=discord.ButtonStyle.grey)
    async def secondary_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.toggle(self, "secondary", button)

        self.load_items()
        await self.edit_draw(interaction)

    @discord.ui.button(
        emoji="<:select_tool:1037847279169704028> ", style=discord.ButtonStyle.gray
    )
    async def select_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        if self.board.select is False:
            self.board.initial_coord = (self.board.cursor_row, self.board.cursor_col)
            self.board.initial_row, self.board.initial_col = self.board.initial_coord
        elif self.board.select is True:
            self.board.clear_cursors()
            self.board.draw_cursor()
        self.toggle(self.board, "select", button)
        await self.edit_draw(interaction)

    @discord.ui.button(
        emoji="<:fill:930832869692149790>", style=discord.ButtonStyle.grey
    )
    async def fill_bucket(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:fill_replace:1032565283929456670>", style=discord.ButtonStyle.grey
    )
    async def fill_replace(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.edit_draw(interaction, self.board.cursor, fill_replace=True)

    # 2nd row
    @discord.ui.button(
        emoji="<:eyedropper:1033248590988066886>", style=discord.ButtonStyle.grey
    )
    async def eyedropper(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        cursor_pixel = self.board.cursor_pixel
        emoji = discord.PartialEmoji.from_str(self.board.un_cursor(cursor_pixel))

        # Check if the option already exists
        option = self.selectmenu.emoji_to_option(emoji)
        eyedropped_options = [
            option
            for option in self.selectmenu.options
            if option.label.startswith("Eyedropped option")
        ]
        if option is None:
            option = discord.SelectOption(
                label=f"Eyedropped option #{len(eyedropped_options)}",
                emoji=emoji,
                value=str(emoji),
            )

        self.selectmenu.append_option(option)
        self.board.cursor = option.value
        return await self.edit_draw(interaction, False)

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

    # 3rd row
    @discord.ui.button(
        emoji="<:erase:927526530052132894>", style=discord.ButtonStyle.gray
    )
    async def erase(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.edit_draw(interaction, self.board.background)

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
        self.toggle(self.board, "auto", button)
        await self.edit_draw(interaction, False)

    @discord.ui.button(
        emoji="<:right:1032565019352764438>", style=discord.ButtonStyle.blurple
    )
    async def right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        row_move = 0
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    # 4th / last row
    @discord.ui.button(
        emoji="<:draw:1032565261846454272>", style=discord.ButtonStyle.green
    )
    async def draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.edit_draw(interaction, self.board.cursor)

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

        res, msg = await self.wait_for(
            'Please type the cell you want to move the cursor to. e.g. "A1", "a1", "A10", "A", "10", etc.',
            interaction=interaction,
            check=check,
            ephemeral=True,
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
            return await res.edit(content="Aborted.")

        row_move = LETTER_TO_NUMBER[row_key] - self.board.cursor_row
        col_move = col_key - self.board.cursor_col
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)
        await res.edit(
            content=f"Moved cursor to **{cell}** ({LETTER_TO_NUMBER[row_key]}, {col_key})"
        )


async def setup(bot):
    await bot.add_cog(Draw(bot))
