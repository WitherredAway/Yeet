import discord
import re
import simpleeval
import math

from simpleeval import simple_eval
from typing import Optional
from discord.ext import commands, tasks
from discord import app_commands
from helpers.utils import isfloat


class Calculator(discord.ui.View):
    def __init__(self, ctx: commands.Context, text: str):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.response = None
        self.text = text
        self.history = "__**History of calculations for this session.**__"

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
        await self.response.edit(view=self)

    async def new_edit(
        self, append, interaction: discord.Interaction, string: str = None
    ):
        # very convoluted code, new bugs might arise
        if self.text != "":
            check = any(
                [self.text.startswith("0"), not self.text[0].isdigit()]
            ) and not any(
                [self.text[0] == "-", self.text[0] == "+", self.text[0] == "."]
            )
            if check:
                self.text = self.text[1:]
            if not append.isdigit() and any(
                [self.text[-1].isdigit(), append == "-", append == "+"]
            ):
                self.text += append

        if self.text == "":
            if any([append == "+", append == "-", append == "."]):
                self.text += append

        if isfloat(append):
            self.text += append

        if string is None:
            string = self.text
        result = calculate(string)
        await interaction.edit_original_response(content=result)

    @discord.ui.button(label="■", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.text == "":
            await interaction.delete_original_response()
        else:
            await interaction.edit_original_response(view=None)
        self.stop()

    @discord.ui.button(label="C", style=discord.ButtonStyle.danger)
    async def clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.history += f"\n__Cleared__:\n{calculate(self.text)}"
        self.text = ""
        await self.new_edit("", interaction)

    @discord.ui.button(label="⌫", style=discord.ButtonStyle.danger)
    async def backspace(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.text = self.text[:-1]
        await self.new_edit("", interaction)

    @discord.ui.button(label="R%", style=discord.ButtonStyle.gray)
    async def _modulus(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        # self.text += "%"
        await self.new_edit("%", interaction)

    @discord.ui.button(label="÷", style=discord.ButtonStyle.gray)
    async def _divide(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        # self.text += "/"
        await self.new_edit("/", interaction)

    @discord.ui.button(label="𝓍ʸ", style=discord.ButtonStyle.gray)
    async def _power(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "**"
        await self.new_edit("**", interaction)

    @discord.ui.button(label="7", style=discord.ButtonStyle.blurple)
    async def _seven(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "7"
        await self.new_edit("7", interaction)

    @discord.ui.button(label="8", style=discord.ButtonStyle.blurple)
    async def _eight(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "8"
        await self.new_edit("8", interaction)

    @discord.ui.button(label="9", style=discord.ButtonStyle.blurple)
    async def _nine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "9"
        await self.new_edit("9", interaction)

    @discord.ui.button(label="×", style=discord.ButtonStyle.gray)
    async def _multiply(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        # self.text += "*"
        await self.new_edit("*", interaction)

    @discord.ui.button(label="π", style=discord.ButtonStyle.gray)
    async def _placeholder(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        append = ""
        if self.text != "" and self.text[-1].isdigit():
            append = f"*{math.pi}"
        else:
            append = f"{math.pi}"
        await self.new_edit(append, interaction)

    @discord.ui.button(label="4", style=discord.ButtonStyle.blurple)
    async def _four(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "4"
        await self.new_edit("4", interaction)

    @discord.ui.button(label="5", style=discord.ButtonStyle.blurple)
    async def _five(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "5"
        await self.new_edit("5", interaction)

    @discord.ui.button(label="6", style=discord.ButtonStyle.blurple)
    async def _six(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "6"
        await self.new_edit("6", interaction)

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray)
    async def _minus(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "-"
        await self.new_edit("-", interaction)

    @discord.ui.button(label="%", style=discord.ButtonStyle.gray)
    async def _percent(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        # self.text += "/100"
        await self.new_edit("/100", interaction)

    @discord.ui.button(label="1", style=discord.ButtonStyle.blurple)
    async def _one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "1"
        await self.new_edit("1", interaction)

    @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def _two(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "2"
        await self.new_edit("2", interaction)

    @discord.ui.button(label="3", style=discord.ButtonStyle.blurple)
    async def _three(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "3"
        await self.new_edit("3", interaction)

    @discord.ui.button(label="+", style=discord.ButtonStyle.gray)
    async def _plus(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "+"
        await self.new_edit("+", interaction)

    @discord.ui.button(label="//", style=discord.ButtonStyle.gray)
    async def _floor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "//"
        await self.new_edit("//", interaction)

    @discord.ui.button(label=".", style=discord.ButtonStyle.gray)
    async def _point(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "."
        await self.new_edit(".", interaction)

    @discord.ui.button(label="0", style=discord.ButtonStyle.blurple)
    async def _zero(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # self.text += "0"
        await self.new_edit("0", interaction)

    @discord.ui.button(label="↻", style=discord.ButtonStyle.green)
    async def _history(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await interaction.edit_original_response(content=self.history)

    @discord.ui.button(label="=", style=discord.ButtonStyle.green)
    async def _equals(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.history += "\n__Equalled__:\n" + calculate(self.text)
        self.text = str(simple_eval(self.text))
        await self.new_edit("", interaction)


def calculate(to_calc):
    err = "Invalid operators/operations specified."
    if to_calc == "":
        result = "\u200b"
    elif not to_calc.isdigit() and re.search(r"[\+\-\*\/%()\.]", to_calc) is None:
        result = err
    else:
        try:
            result = simple_eval(to_calc)
        except SyntaxError:
            result = "\u200b"
        except simpleeval.NameNotDefined:
            result = err
    final = f"""
```py
> {to_calc}
```
```
= {result}
```"""
    return final


class Math(commands.Cog):
    """Commands for mathematical features."""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "🔢"

    @commands.hybrid_command(
        name="calculate",
        aliases=["calc", "calculator"],
        brief="Interactive and fancy calculator.",
        help=f"""
```
■ - Stops the calculator buttons
C - Clears the text box
⌫ - Backspace, erases one character
R% - Modulus operator, shows remainder of a division
÷ - Division
^ - Power / Exponent
× - Multiplication
π - pi
– - Subtraction
% - Percentage; divides by 100
+ - Addition
// - Floor; division, but decimals removed
. - Period(t 💅)
↻ - History of calculations, logged by = and C
= - Equals to, brings the result into the text box. Also logs the calculation for ↻
```
                    """,
        description="Interactive calculator with buttons! Easier than typing numbers, but you can do that aswell.",
        invoke_without_command=True,
        case_insensitive=True,
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def calculator(self, ctx, *, expression: str = ""):
        expression = expression.replace("\\", "")
        expression = expression.replace(" ", "")
        result = calculate(expression)
        view = Calculator(ctx=ctx, text=expression)
        response = await ctx.send(result, view=view)
        view.response = response
        await view.wait()

    @commands.hybrid_command(
        name="simplecalculate",
        aliases=["simplecalc", "sc", "simplecalculator"],
        brief="Simple calculator. Use `calculate` for fanciness.",
        help="Supports simple [python arithmetic operators](https://www.w3schools.com/python/python_operators.asp#:~:text=Python%20Arithmetic%20Operators) for calculation.",
        description="Simple calculate command. Use the `calculate` command for an interactive calculator.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def simplecalculate(self, ctx, *, expression=""):
        expression = expression.replace("\\", "")
        expression = expression.replace(" ", "")
        result = calculate(expression)
        await ctx.send(result)


async def setup(bot):
    await bot.add_cog(Math(bot))
