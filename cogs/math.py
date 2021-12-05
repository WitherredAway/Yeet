import discord
from discord.ext import commands, tasks
from main import *
import re
from simpleeval import simple_eval

class Calculator(discord.ui.View):
    def __init__(self, ctx: commands.Context, text: str):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.text = text
        self.history = "__**History of calculations for this session.**__"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(f"This calculator instance does not belong to you, use the `{self.ctx.command}` command to create your own instance.", ephemeral=True)
            return False
        return True

    async def new_edit(self, append, interaction: discord.Interaction, string: str=None):
        if self.text != "":
            if self.text.startswith("0") or not self.text[0].isdigit():
                self.text = self.text[1:]
            if not append.isdigit() and self.text[-1].isdigit():
                self.text += append
        if append.isdigit() or append == "3.14":
            self.text += append
        if string is None:
            string = self.text
        result = calculate(string)
        await interaction.edit_original_message(content=result)

    @discord.ui.button(label="■", style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.text == "":
            await interaction.delete_original_message()
        else:
            await interaction.edit_original_message(view=None)
        self.stop()

    @discord.ui.button(label="C", style=discord.ButtonStyle.danger)
    async def clear(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        self.text = ""
        await self.new_edit("", interaction)
    @discord.ui.button(label="⌫", style=discord.ButtonStyle.danger)
    async def backspace(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        self.text = self.text[:-1]
        await self.new_edit("", interaction)

    @discord.ui.button(label="R%", style=discord.ButtonStyle.gray)
    async def _modulus(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "%"
        await self.new_edit("%", interaction)

    @discord.ui.button(label="÷", style=discord.ButtonStyle.gray)
    async def _divide(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "/"
        await self.new_edit("/", interaction)

    @discord.ui.button(label="^", style=discord.ButtonStyle.gray)
    async def _power(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "**"
        await self.new_edit("**", interaction)

    @discord.ui.button(label="7", style=discord.ButtonStyle.blurple)
    async def _seven(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "7"
        await self.new_edit("7", interaction)

    @discord.ui.button(label="8", style=discord.ButtonStyle.blurple)
    async def _eight(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "8"
        await self.new_edit("8", interaction)

    @discord.ui.button(label="9", style=discord.ButtonStyle.blurple)
    async def _nine(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "9"
        await self.new_edit("9", interaction)

    @discord.ui.button(label="×", style=discord.ButtonStyle.gray)
    async def _multiply(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "*"
        await self.new_edit("*", interaction)

    @discord.ui.button(label="π", style=discord.ButtonStyle.gray)
    async def _placeholder(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        append = ""
        if self.text != "" and self.text[-1].isdigit():
            append = "*3.14"
        else:
            append = "3.14"
        await self.new_edit(append, interaction)

    @discord.ui.button(label="4", style=discord.ButtonStyle.blurple)
    async def _four(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "4"
        await self.new_edit("4", interaction)

    @discord.ui.button(label="5", style=discord.ButtonStyle.blurple)
    async def _five(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "5"
        await self.new_edit("5", interaction)

    @discord.ui.button(label="6", style=discord.ButtonStyle.blurple)
    async def _six(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "6"
        await self.new_edit("6", interaction)

    @discord.ui.button(label="-", style=discord.ButtonStyle.gray)
    async def _minus(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "-"
        await self.new_edit("-", interaction)

    @discord.ui.button(label="%", style=discord.ButtonStyle.gray)
    async def _percent(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "/100"
        await self.new_edit("/100", interaction)

    @discord.ui.button(label="1", style=discord.ButtonStyle.blurple)
    async def _one(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "1"
        await self.new_edit("1", interaction)

    @discord.ui.button(label="2", style=discord.ButtonStyle.blurple)
    async def _two(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "2"
        await self.new_edit("2", interaction)

    @discord.ui.button(label="3", style=discord.ButtonStyle.blurple)
    async def _three(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "3"
        await self.new_edit("3", interaction)

    @discord.ui.button(label="+", style=discord.ButtonStyle.gray)
    async def _plus(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "+"
        await self.new_edit("+", interaction)

    @discord.ui.button(label="//", style=discord.ButtonStyle.gray)
    async def _floor(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "//"
        await self.new_edit("//", interaction)

    @discord.ui.button(label=".", style=discord.ButtonStyle.gray)
    async def _period(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "."
        await self.new_edit(".", interaction)

    @discord.ui.button(label="0", style=discord.ButtonStyle.blurple)
    async def _zero(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
       # self.text += "0"
        await self.new_edit("0", interaction)

    @discord.ui.button(label="↻", style=discord.ButtonStyle.green)
    async def _history(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.edit_original_message(content=self.history)

    @discord.ui.button(label="=", style=discord.ButtonStyle.green)
    async def _equals(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        self.history += "\n" + calculate(self.text)
        self.text = str(simple_eval(self.text))
        await self.new_edit("", interaction)
    
    
def calculate(to_calc):
    if to_calc == "":
        result = "\u200b"
    elif not to_calc.isdigit() and re.search(r"[\+\-\*\/%()\.]", to_calc) is None:
        result = f"Invalid operators/operations specified."
    else:
        try:
            result = simple_eval(to_calc)
        except SyntaxError:
            result = "\u200b"
    final = f"""
```py
> {to_calc}
```
```
= {result}
```
             """
    return final


                     
class Math(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="calculator", 
                    aliases=["calc", "calculate"],
                    help=f"""
```
■ - Stops the calculator buttons
C - Clears the text box
⌫ - Backspace, erases one character
R% - Modulus operator, shows remainder of a division
÷ - Division
^ - Power / Exponent
× - Multiplication
π - pi = 3.14
– - Subtraction
% - Percentage; divides by 100
+ - Addition
// - Floor; division, but decimals removed
. - Period(t 💅)
↻ - History of calculations, logged by =
= - Equals to, brings the result into the text box. Also logs the calculation for ↻
```
                    """,
                    description="Intuitive, interactive and seamless calculator made with buttons! A whole ton easier than typing the numbers, but you can do that aswell if you wish.",
                    invoke_without_command=True, 
                    case_insensitive=True)
    async def calculator(self, ctx, *, string: str=""):
        string = string.replace("\\", "")
        string = string.replace(" ", "")
        result = calculate(string)
        view = Calculator(ctx=ctx, text=string)
        await ctx.send(result, view=view)
        await view.wait()

    @calculator.command(name="hcf", case_insensitive=True)
    async def hcf(self, ctx, num1: int, num2: int):
        if num1 > num2:
            smaller = num2
        else:
            smaller = num1
        for i in range(1, smaller+1):
            if (num1 % i == 0) and (num2 % i == 0):
                hcf = i
            else:
                hcf = None
        await ctx.send(f"__**{hcf}**__ is the HCF (Highest common factor) of `{num1}` and `{num2}`.")
        
def setup(bot):
    bot.add_cog(Math(bot))
    