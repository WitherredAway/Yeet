import typing
from typing import Optional, TypeVar
import os
import yarl
import asyncio
import aiohttp
import json
import datetime
import re
from dataclasses import dataclass

import discord
import random
from discord.ext import commands, menus, tasks
import pandas as pd
import validators

from .utils.paginator import BotPages
import modules.github_gists as github_gists


GITHUB_ACCESS_TOKEN = os.getenv("githubTOKEN")


class CreateGistModal(discord.ui.Modal):
    """Interactive modal to create gists."""

    description = discord.ui.TextInput(
        label="Description", max_length=1000, placeholder="Description"
    )
    filename = discord.ui.TextInput(
        label="Filename",
        min_length=1,
        max_length=100,
        placeholder="Name of the new file",
        default="output.txt",
    )
    content = discord.ui.TextInput(label="Content", style=discord.TextStyle.paragraph)

    def __init__(self, view: discord.ui.View):
        super().__init__(title="Create a new gist")
        self.view = view
        self.client = self.view.client

    async def on_submit(self, interaction: discord.Interaction):
        # description = "Author ID: %s\n%s" % (self.view.ctx.author.id, self.description.value)
        description = self.description.value
        filename = self.filename.value
        content = self.content.value

        files = {filename: {"filename": filename, "content": content}}

        self.gist = await self.client.create_gist(
            files,
            description=description,
            public=True
        )
        self.view.gist = self.gist
        self.view._update_buttons()

        await interaction.response.edit_message(
            content=self.gist.html_url, view=self.view
        )


class EditGistModal(discord.ui.Modal):
    """The modal for executing various functions on a gist"""

    def __init__(self, view: discord.ui.View, gist: github_gists.Gist):
        super().__init__(title="Edit gist (only shows the first 2 files)")
        self.view = view
        self.client = self.view.client
        self.gist = gist
        self._fill_items()

    def _fill_items(self):
        # Pattern to group the author id and the description content from the description
        # (\d+) groups the ID
        # (?:\n) is a non-capturing group to detect 1 or more newlines
        # (.*) groups the content
        # pattern = re.compile(r"Author ID: (\d+)(?:\n)+(.*)")
        # self.author_id, default_desc = (pattern.match(self.gist.description)).groups()
        self.add_item(
            discord.ui.TextInput(
                label="Description",
                style=discord.TextStyle.paragraph,
                placeholder="Description of the gist.",
                default=self.gist.description,
                custom_id="gist_description",
                required=False,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Edit a specific file",
                style=discord.TextStyle.short,
                placeholder="Input existing filename to edit file,\nInput new filename to create a new file.",
                custom_id="new_filename",
                required=False,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="The specific file's content",
                placeholder="New content of the specific file.",
                style=discord.TextStyle.paragraph,
                min_length=1,
                custom_id="new_filecontent",
                required=False,
            )
        )

        for idx, file in enumerate(list(self.gist.files.values())[:2]):
            filename = file["filename"]
            content = file["content"]
            self.add_item(
                discord.ui.TextInput(
                    label="File: %s's content" % filename,
                    placeholder="Edit content of file %s." % filename,
                    style=discord.TextStyle.paragraph,
                    default=content,
                    custom_id="%s_content" % filename,
                    required=False,
                )
            )

    def children_dict(self) -> typing.Dict:
        ch_dict = {child.custom_id: child.__dict__ for child in self.children}
        return ch_dict

    async def on_submit(self, interaction: discord.Interaction):
        children_dict = self.children_dict()
        data_files = self.gist.files

        description = "Author: %s\n\n" % self.view.ctx.author
        description += children_dict["gist_description"]["_value"]
        for child_custom_id, child_value in children_dict.items():
            value = child_value["_value"]
            # If the child's custom_id is that of the new filename text input
            # and if it is not None
            if all((child_custom_id == "new_filename", value != "")):
                # Set values to input into data
                filename = value
                content = children_dict["new_filecontent"]["_value"]
                # Set its values as the new file's name and content in the gist
                try:
                    data_files[filename].update({"content": content})
                except KeyError:
                    data_files[filename] = {"filename": filename, "content": content}

            # If the child's custom_id ends with _content
            elif child_custom_id.endswith("_content"):
                # It is the content of a file
                content = value
                # Set its value as the corresponding file's content
                filename = child_custom_id.split("_")[0]
                data_files[filename].update({"content": content})

        await self.client.edit_gist(
            self.gist,
            files=data_files,
            description=description,
            public=False
        )
        await interaction.response.edit_message(content=self.gist.html_url)


class GistView(discord.ui.View):
    def __init__(
        self,
        ctx: commands.Context,
        client: github_gists.Client,
        gist: github_gists.Gist,
    ):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.client = client
        self.gist = gist
        self._update_buttons()

    def _update_buttons(self):
        self._create_gist.disabled = True if self.gist else False
        self._edit_gist.disabled = False if self.gist else True
        self._delete_gist.disabled = False if self.gist else True

    async def on_timeout(self):
        await self.response.edit(view=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you, please create your own instance."
            )
            return False
        return True

    @discord.ui.button(label="Create a gist", style=discord.ButtonStyle.green)
    async def _create_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        modal = CreateGistModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit gist", style=discord.ButtonStyle.blurple)
    async def _edit_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        await self.client.update_gist(self.gist)
        modal = EditGistModal(self, self.gist)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete gist", style=discord.ButtonStyle.danger)
    async def _delete_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        await interaction.response.edit_message(
            content="Deleted gist %s" % self.gist.id, view=None
        )
        await self.client.delete_gist(self.gist)

    @staticmethod
    async def format_embed(embed, gist: github_gists.Gist):
        embed.title = gist.id


class Test(commands.Cog):
    """Commands for testing."""

    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

    display_emoji = "🧪"

    @commands.command(name="gist", brief="GitHub Gists utilities")
    async def _gist(self, ctx, gist_url_or_id: str = None):
        embed = self.bot.Embed(title="Gist")
        gist = None
        client = github_gists.Client()
        await client.authorize(access_token=GITHUB_ACCESS_TOKEN)
        if validators.url(str(gist_url_or_id)):
            gist_url_or_id = gist_url_or_id.split("/")[
                -2 if gist_url_or_id.endswith("/") else -1
            ]
            try:
                gist = await client.get_gist(gist_url_or_id)
            except aiohttp.ClientResponseError:
                embed.description = "Gist not found."
        view = GistView(ctx, client, gist)
        view.response = await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Test(bot))
