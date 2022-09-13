import os
import sys
import discord
from discord.ext import menus, commands

from jishaku.codeblocks import codeblock_converter


class CodeView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__()
        self.ctx = ctx

    @discord.ui.button(label="Input code")
    async def modal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("You do not own this bot.", ephemeral=True)
        modal = CodeModal(self.ctx)
        await interaction.response.send_modal(modal)


class CodeModal(discord.ui.Modal):
    field_1 = discord.ui.TextInput(label='Input', style=discord.TextStyle.paragraph, required=False)
    field_2 = discord.ui.TextInput(label='\u200b', style=discord.TextStyle.paragraph, required=False)
    field_3 = discord.ui.TextInput(label='\u200b', style=discord.TextStyle.paragraph, required=False)
    field_4 = discord.ui.TextInput(label='\u200b', style=discord.TextStyle.paragraph, required=False)
    field_5 = discord.ui.TextInput(label='\u200b', style=discord.TextStyle.paragraph, required=False)

    def __init__(self, ctx):
        super().__init__(title='Input code to bypass character limit')
        self.ctx = ctx
        self.bot = self.ctx.bot

    async def on_submit(self, interaction: discord.Interaction):
        code = f"""{self.field_1}\n{self.field_2}\n{self.field_3}\n{self.field_4}\n{self.field_5}"""
        py_command = self.bot.get_command("jsk py")
        
        await self.ctx.invoke(py_command, argument=codeblock_converter(code))
        await interaction.response.defer()

        CHAR_LIMIT = 1988
        for i in range(0, len(code), CHAR_LIMIT):
            await interaction.followup.send(f"```py\n{code[i:i+CHAR_LIMIT]}\n```")
            await asyncio.sleep(1)
            
    async def on_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message(error)
