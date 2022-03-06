import discord
import re
import itertools
import emojis
import copy
import asyncio

from typing import Optional, Union
from discord.ext import commands, tasks
from .utils.utils import invert_dict

row_alpha = [
    "🇦",
    "🇧",
    "🇨",
    "🇩",
    "🇪",
    "🇫",
    "🇬",
    "🇭",
    "🇮",
    "🇯",
    "🇰",
    "🇱",
    "🇲",
    "🇳",
    "🇴",
    "🇵",
    "🇶",
]

col_alpha = [
    "0️⃣",
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣",
    "🔟",
    "<:11:920679053688725596>",
    "<:12:920679079756300339>",
    "<:13:920679103332495430>",
    "<:14:920679132260618260>",
    "<:15:920679200854253578>",
    "<:16:920679238414266408>",
]


class DrawButtons(discord.ui.View):
    def __init__(self, ctx, board, row_list, col_list, bg):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.response = None
        self.initial_board = board
        self.board = copy.deepcopy(self.initial_board)
        self.row_list = row_list
        self.col_list = col_list
        self.cursor_row = int(len(row_list) / 2)
        self.cursor_col = int(len(col_list) / 2)
        self.cells = [(self.cursor_row, self.cursor_col)]
        self.cursor = self.board[self.cursor_row][self.cursor_col]
        self.cursor_row_max = row_list.index(row_list[-1])
        self.cursor_col_max = col_list.index(col_list[-1])
        self.bg = bg
        self.auto = False
        self.fill = False
        self.initial_cell = (None, None)
        self.initial_row = self.initial_cell[0]
        self.initial_col = self.initial_cell[1]
        self.final_cell = (None, None)
        self.final_row = self.final_cell[0]
        self.final_col = self.final_cell[1]
        self.inv_cur_cle = invert_dict(self.cur_cle)


    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, use the `{self.ctx.command}` command to create your own instance.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self):
        self.clear_items()
        self.add_item(
            discord.ui.Button(
                label=f"This interaction has timed out. Use {self.ctx.prefix}{self.ctx.command} for a new one.",
                style=discord.ButtonStyle.gray,
                disabled=True,
            )
        )
        self.board[self.cursor_row][self.cursor_col] = self.find_key(
            self.board[self.cursor_row][self.cursor_col]
        )
        embed = make_embed(self.ctx, self.board, self.bg, self.row_list, self.col_list)
        await self.response.edit(embed=embed, view=self)
        self.stop()

    @discord.ui.select(
        placeholder="🎨 Colour picker",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Red", emoji="🟥", value="🔴"),
            discord.SelectOption(label="Orange", emoji="🟧", value="🟠"),
            discord.SelectOption(label="Yellow", emoji="🟨", value="🟡"),
            discord.SelectOption(label="Green", emoji="🟩", value="🟢"),
            discord.SelectOption(label="Blue", emoji="🟦", value="🔵"),
            discord.SelectOption(label="Purple", emoji="🟪", value="🟣"),
            discord.SelectOption(label="Brown", emoji="🟫", value="🟤"),
            discord.SelectOption(label="Black", emoji="⬛", value="⚫"),
            discord.SelectOption(label="White", emoji="⬜", value="⚪"),
            discord.SelectOption(
                label="Emoji", emoji="<:emojismiley:920902406336815104>", value="emoji"
            ),
        ],
    )
    async def colour_picker(self, select, interaction):
        await interaction.response.defer()
        if select.values[0] == "emoji":
            res = await interaction.channel.send(
                content="Please send a single emoji you want to draw on your drawing board. e.g. 😎"
            )

            def first_emoji(self, sentence):
                return [
                    word
                    for word in sentence.split()
                    if str(word.encode("unicode-escape"))[2] == "\\"
                ]

            def check(m):
                return m.author == interaction.user and len(m.content.split(" ")) == 1

            try:
                msg = await self.ctx.bot.wait_for("message", timeout=30, check=check)
            except asyncio.TimeoutError:
                return await interaction.channel.send(content="Timed out.")
            emoji_check = discord.PartialEmoji.from_str(msg.content)
            emoji = (
                msg.content
                if emoji_check.is_unicode_emoji()
                else (f"<{'a' if emoji_check.animated else ''}:_:{emoji_check.id}>")
            )
            select.add_option(label=emoji_check.name or emoji, emoji=emoji, value=emoji)
            try:
                await interaction.edit_original_message(view=self)
            except discord.HTTPException as e:
                await interaction.channel.send(content=e.text.split(": ")[-1])
                select.options.pop(-1)
                await interaction.edit_original_message(view=self)
                await asyncio.sleep(0.5)
            await res.delete()
            await asyncio.sleep(0.5)
            await msg.delete()
        else:
            self.cursor = select.values[0]

    def cursor_conv(self, row_key):
        conv = {
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
        row = conv[row_key] - self.cursor_row
        return row

    cur_cle = {
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
    
    def find_key(self, value):
        return self.inv_cur_cle.get(value, value)

    def clear_cursors(self):
        for cell_tuple in self.cells:
            try:
                self.board[cell_tuple[0]][cell_tuple[1]] = self.find_key(
                    self.board[cell_tuple[0]][cell_tuple[1]]
                )
            except:
                pass
        self.cells = [(self.cursor_row, self.cursor_col)]

    async def move_cursor(
        self, interaction: discord.Interaction, row_move: int = 0, col_move: int = 0
    ):
        if self.fill is not True:
            self.board[self.cursor_row][self.cursor_col] = self.find_key(
                self.board[self.cursor_row][self.cursor_col]
            )
        self.cursor_row += row_move
        self.cursor_col += col_move
        if self.fill is not True:
            self.cells = [(self.cursor_row, self.cursor_col)]
        if self.fill is True:
            self.final_cell = (self.cursor_row, self.cursor_col)
            self.final_row = self.final_cell[0]
            self.final_col = self.final_cell[1]
            self.cells.append(self.final_cell)
            for row in range(
                min(self.initial_row, self.final_row),
                max(self.initial_row, self.final_row) + 1,
            ):
                for col in range(
                    min(self.initial_col, self.final_col),
                    max(self.initial_col, self.final_col) + 1,
                ):
                    self.cells.append((row, col))

        if self.auto is True:
            await self.edit_draw(interaction, self.cursor)

        for cell_tuple in self.cells:
            try:
                self.board[cell_tuple[0]][cell_tuple[1]] = self.cur_cle[
                    self.board[cell_tuple[0]][cell_tuple[1]]
                ]
            except KeyError:
                continue
        embed = make_embed(self.ctx, self.board, self.bg, self.row_list, self.col_list)
        if self.auto is not True:
            await interaction.edit_original_message(embed=embed)

    async def edit_draw(self, interaction, draw=None, corner=None):
        if all(cell == draw for cell in self.cells):
            return
        if draw is None:
            draw = self.board[self.cursor_row][self.cursor_col]
        if corner is None:
            corner = self.cursor
        for cell_tuple in self.cells:
            self.board[cell_tuple[0]][cell_tuple[1]] = draw
        embed = make_embed(self.ctx, self.board, self.bg, self.row_list, self.col_list)
        await interaction.edit_original_message(embed=embed, view=self)

    # ------ buttons ------

    @discord.ui.button(
        emoji="<:stop:921864670145552444>", style=discord.ButtonStyle.danger
    )
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        self.clear_cursors()
        embed = make_embed(self.ctx, self.board, self.bg, self.row_list, self.col_list)
        await interaction.edit_original_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(
        emoji="<:clear:922414780193579009>", style=discord.ButtonStyle.danger
    )
    async def clear(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        self.auto = False
        self.auto_colour.style = discord.ButtonStyle.gray
        self.fill = False
        self.fill_bucket.style = discord.ButtonStyle.grey
        self.cursor_row = int(len(self.row_list) / 2)
        self.cursor_col = int(len(self.col_list) / 2)
        row = [self.bg for i in range(len(self.col_list))]
        board = [row[:] for i in range(len(self.row_list))]
        self.board = board
        self.clear_cursors()
        try:
            self.board[self.cursor_row][self.cursor_col] = self.cur_cle[
                self.board[self.cursor_row][self.cursor_col]
            ]
        except KeyError:
            pass
        embed = make_embed(self.ctx, self.board, self.bg, self.row_list, self.col_list)
        await interaction.edit_original_message(embed=embed, view=self)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder1(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder2(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:fill:930832869692149790>", style=discord.ButtonStyle.gray
    )
    async def fill_bucket(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        if self.fill == False:
            self.fill = True
            self.initial_cell = (self.cursor_row, self.cursor_col)
            self.initial_row = self.initial_cell[0]
            self.initial_col = self.initial_cell[1]
            self.fill_bucket.style = discord.ButtonStyle.green
        elif self.fill == True:
            self.fill = False
            self.clear_cursors()
            try:
                self.board[self.cursor_row][self.cursor_col] = self.cur_cle[
                    self.board[self.cursor_row][self.cursor_col]
                ]
            except KeyError:
                pass
            self.fill_bucket.style = discord.ButtonStyle.grey
        await self.edit_draw(interaction)
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder3(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:up_left:920896021700161547>", style=discord.ButtonStyle.blurple
    )
    async def up_right(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        row_move = -1
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:up:920895538696704053>", style=discord.ButtonStyle.blurple
    )
    async def up(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        row_move = -1
        col_move = 0
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:up_right:920895852128657480>", style=discord.ButtonStyle.blurple
    )
    async def up_left(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        row_move = -1
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder5(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:erase:927526530052132894>", style=discord.ButtonStyle.gray
    )
    async def erase(self, button: discord.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.edit_draw(interaction, self.cur_cle[self.bg])

    @discord.ui.button(
        emoji="<:left:920895993145327628>", style=discord.ButtonStyle.blurple
    )
    async def left(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        row_move = 0
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:auto_cursor:921352341427470347>", style=discord.ButtonStyle.gray
    )
    async def auto_colour(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        if self.auto == False:
            self.auto = True
            self.auto_colour.style = discord.ButtonStyle.green
        elif self.auto == True:
            self.auto = False
            self.auto_colour.style = discord.ButtonStyle.grey
        await interaction.edit_original_message(view=self)

    @discord.ui.button(
        emoji="<:right:920895888229036102>", style=discord.ButtonStyle.blurple
    )
    async def right(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        row_move = 0
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(label="\u200b", style=discord.ButtonStyle.gray)
    async def placeholder6(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()

    @discord.ui.button(
        emoji="<:middle:920897054060998676>", style=discord.ButtonStyle.green
    )
    async def draw(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.edit_draw(interaction, self.cursor)

    @discord.ui.button(
        emoji="<:down_left:920895965987242025>", style=discord.ButtonStyle.blurple
    )
    async def down_left(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        row_move = 1
        col_move = -1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:down:920895939030429696>", style=discord.ButtonStyle.blurple
    )
    async def down(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        row_move = 1
        col_move = 0
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:down_right:920895913608765551>", style=discord.ButtonStyle.blurple
    )
    async def down_right(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        row_move = 1
        col_move = 1
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)

    @discord.ui.button(
        emoji="<:ABCD:920896121285537832>", style=discord.ButtonStyle.blurple
    )
    async def set_cursor(
        self, button: discord.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer()
        res = await self.ctx.send(
            'Please type the cell you want to move the cursor to. e.g. "A1", "a8", "A10", etc.'
        )

        def check(m):
            return m.author == interaction.user

        try:
            msg = await self.ctx.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            return await self.ctx.send("Timed out.")
        cell = msg.content.upper()
        if len(cell) != 2 and len(cell) != 3:
            return await self.ctx.send("Min and max length of cell must be 2 and 3")
        ABC = "ABCDEFGHIJKLMNOPQ"
        NUM = [
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
        ]
        row_key = cell[0]
        col_key = cell[1:]
        if (
            row_key not in ABC[: self.cursor_row_max + 1]
            or col_key not in NUM[: self.cursor_col_max + 1]
        ):
            return await self.ctx.send(f"Invalid cell provided.")
        row_move = self.cursor_conv(row_key)
        col_move = int(col_key) - self.cursor_col
        await self.move_cursor(interaction, row_move=row_move, col_move=col_move)
        await res.delete()
        await asyncio.sleep(0.5)
        await msg.delete()


def make_embed(ctx, board, bg, row, col):
    embed = discord.Embed(title=f"{ctx.author}'s drawing board.")
    val = ""
    for idx, i in enumerate(board):
        u200b = "\u200b"
        val += f"\n{row[idx]}  {u200b.join(i)}"
    embed.add_field(name=f"{bg}  {''.join(col)}\u200b", value=val, inline=False)
    embed.set_footer(
        text=f"Tip: You can customize this board! Do {ctx.prefix}help draw for more info."
    )
    return embed


def make_board(bg, height, width):
    col = [bg for i in range(height)]
    tboard = [col[:] for i in range(width)]
    row_list = row_alpha[:height]
    col_list = col_alpha[:width]

    try:
        tboard[int(len(row_list) / 2)][int(len(col_list) / 2)] = DrawButtons.cur_cle[
            tboard[int(len(row_list) / 2)][int(len(col_list) / 2)]
        ]
    except KeyError:
        tboard = tboard
    return tboard, row_list, col_list


class Draw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🖌️"

    @commands.bot_has_permissions(external_emojis=True)
    @commands.group(
        name="draw",
        aliases=["drawing", "paint", "painting"],
        case_insensitive=True,
        help="p",
        description="p",
        invoke_without_command=True,
    )
    async def draw(
        self,
        ctx,
        height: Optional[int] = 9,
        width: Optional[int] = 9,
        background: str = "⬜",
    ):
        bg = background
        bg_list = ["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜"]
        if bg not in bg_list:
            return await ctx.send(
                f"Please include a proper background. Available backgrounds:\n{', '.join(bg_list)}"
            )
        if any((height < 5, height > 17, width < 5, width > 17)):
            return await ctx.send("Min and max height and width are 5 and 17!")

        tboard, row_list, col_list = make_board(bg, height, width)
        view = DrawButtons(ctx, tboard, row_list, col_list, bg)

        response = await ctx.send(
            embed=make_embed(ctx, tboard, bg, row_list, col_list), view=view
        )
        view.response = response
        await view.wait()

    @draw.command(name="copy")
    async def copy(
        self,
        ctx,
        message: Union[int, discord.Message] = None,
        message_channel: Union[int, discord.TextChannel] = None,
    ):
        if ctx.message.reference:
            message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        elif message is not None:
            if message_channel is None:
                message_channel = ctx.channel
            else:
                message_channel = await ctx.bot.fetch_channel(
                    message_channel
                    if type(message_channel) == int
                    else message_channel.id
                )
            try:
                message = await message_channel.fetch_message(
                    message if type(message) == int else message.id
                )
            except:
                return await ctx.send(
                    "Please provide a valid message ID or reply to a message!"
                )

        if all(
            (
                message.embeds,
                "drawing board" in message.embeds[0].title,
                message.author == ctx.bot.user,
            )
        ):
            value = message.embeds[0].fields[0].value
            name = message.embeds[0].fields[0].name
            tboard = []
            for line in value.split("\n"):
                tboard.append(line[3:].split("\u200b"))
            bg = name[0]
        else:
            return await ctx.send(
                "Invalid message, make sure it's a draw embed and a message from the bot."
            )

        row_list = row_alpha[: len(tboard)]
        col_list = col_alpha[: len(tboard[0])]
        try:
            tboard[int(len(row_list) / 2)][
                int(len(col_list) / 2)
            ] = DrawButtons.cur_cle[
                tboard[int(len(row_list) / 2)][int(len(col_list) / 2)]
            ]
        except KeyError:
            pass
        view = DrawButtons(ctx, tboard, row_list, col_list, bg)

        response = await ctx.send(
            embed=make_embed(ctx, tboard, bg, row_list, col_list), view=view
        )
        view.response = response
        await view.wait()


def setup(bot):
    bot.add_cog(Draw(bot))
