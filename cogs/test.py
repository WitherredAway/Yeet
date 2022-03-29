import typing
from typing import Optional
import os
import yarl
import asyncio
import aiohttp
import json
import datetime

import discord
import random
from discord.ext import commands, menus, tasks
import pandas as pd
import validators

from .utils.paginator import BotPages


GITHUB_API = "https://api.github.com"
GITHUB_ACCESS_TOKEN = os.getenv("githubTOKEN")


class GistClient:
    def __init__(self, *, username: str, access_token: str, session: Optional[aiohttp.ClientSession] = None):
        self.username = username
        self.access_token = access_token
        self.session = session

        self.URL = "gists"
        self._request_lock = asyncio.Lock()

    async def _generate_session(self):
        self.session = aiohttp.ClientSession()

    async def request(self, method, gist_id: Optional[str] = None, *, params=None, data=None, headers=None):
        hdrs = {
            'Accept': "application/vnd.github.v3+json",
            'User-Agent': self.username,
            'Authorization': "token %s" % self.access_token,
        }

        url = f'{self.URL}/{gist_id if gist_id else ""}'
        request_url = yarl.URL(API_URL) / url

        if headers is not None and isinstance(headers, dict):
            hdrs.update(headers)

        if not self.session:
            await self._generate_session()

        await self._request_lock.acquire()
        try:
            async with self.session.request(
                    method, request_url, params=params, json=data, headers=hdrs
                ) as response:
                remaining = response.headers.get("X-Ratelimit-Remaining")
                json_data = await response.json()
                if response.status == 429 or remaining == "0":
                    reset_after = float(response.headers.get("X-Ratelimit-Reset-After"))
                    await asyncio.sleep(reset_after)
                    self._request_lock.release()
                    return await self.request(
                        method, gist_id, params=params, data=data, headers=headers
                    )
                elif 300 > response.status >= 200:
                    return json_data
                else:
                    raise response.raise_for_status()
        finally:
            if self._request_lock.locked():
                self._request_lock.release()

    async def fetch_data(self, gist_id: str):
        """Fetch data of a Gist"""
        
        gist_data_json = await self.request("GET", gist_id)
        return gist_data_json

    async def get_gist(cls, gist_id: str):
        

    async def create_gist(
        cls,
        files: typing.Dict,  # e.g. {"output.txt": {"content": "Content of the file"}}
        *,
        description: str = None,
        public: bool = True,
    ) -> Gist:
        
        data = {"public": public, "files": files}
        params = {"scope": "gist"}

        if description:
            data["description"] = description

        js = await self.request(
            "POST", data=data, params=params
        )
        return Gist(js, client=self)
    
class Gist:
    def __init__(self, data: typing.Dict, *, client: GistClient):
        self.data = data
        # Set the data dict's items as attributes
        self.__dict__.update(data)
        self.client = client

    async def update(self):
        """Re-fetch data and update the instance."""
        updated_gist_data = await self.client.fetch_data(self.id)
        self.__dict__.update(updated_gist_data)

    async def edit(
        self,
        files: typing.Dict,  # e.g. {"output.txt": {"content": "Content of the file"}}
        *,
        description: str = None,
    ):

        data = {"files": files}

        if description:
            data["description"] = description

        await self.client.request("PATCH", self.id, data=data)

    async def delete(
        self,
    ):
        
        await self.client.request("DELETE", self.id)


class CreateGistModal(discord.ui.Modal):

    filename = discord.ui.TextInput(
        label="Filename",
        min_length=1,
        max_length=100,
        placeholder="output.txt",
        default="output.txt",
    )
    description = discord.ui.TextInput(
        label="Description", max_length=1000, placeholder="Description"
    )
    content = discord.ui.TextInput(label="Content", style=discord.TextStyle.paragraph)

    def __init__(self, view: discord.ui.View):
        super().__init__(title="Create a new gist")
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.gist = await Gist.create_gist(
            GITHUB_ACCESS_TOKEN,
            self.content.value,
            description=self.description.value,
            filename=self.filename.value,
        )
        self.view.gist = self.gist
        self.view._update_buttons()

        await interaction.response.edit_message(
            content=self.gist.html_url, view=self.view
        )


class EditGistModal(discord.ui.Modal):
    """The modal for executing various functions on a gist"""

    def __init__(self, view: discord.ui.View, gist: Gist):
        super().__init__(title="Edit gist (only shows the first 2 files)")
        self.view = view
        self.gist = gist
        self._fill_items()

    def _fill_items(self):
        self.add_item(
            discord.ui.TextInput(
                label="Description",
                placeholder="Edit the gist's description",
                style=discord.TextStyle.paragraph,
                default=self.gist.description,
                custom_id="gist_description",
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Edit a specific file",
                style=discord.TextStyle.short,
                placeholder="Input existing filename to edit file,\nInput new filename to create a new file.",
                custom_id="new_filename",
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="The specific file's content",
                placeholder="New content of the specific file.",
                style=discord.TextStyle.paragraph,
                min_length=1,
                custom_id="new_filecontent",
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
                )
            )

    def children_dict(self):
        ch_dict = {child.custom_id: child.__dict__ for child in self.children}
        return ch_dict

    async def on_submit(self, interaction: discord.Interaction):
        children_dict = self.children_dict()
        data_files = self.gist.files

        description = children_dict["gist_description"]["_value"]
        for child_custom_id, child_value in children_dict.items():
            value = child_value["_value"]
            # If the child's custom_id is that of the new filename text input
            # and if it is not None
            if all((child_custom_id == "new_filename", value is not None)):
                # Set values to input into data
                filename = value
                content = children_dict["new_filecontent"]["_value"]
                # Set its values as the new file's name and content in the gist
                try:
                    data_files[filename].update({"content": content})
                except KeyError:
                    data_files[filename] = {"filename": filename, "content": content}

            # If the child's custom_id ends with content
            elif child_custom_id.endswith("_content"):
                # It is the content of a file
                content = value
                # Set its value as the corresponding file's content
                filename = child_custom_id.split("_")[0]
                data_files[filename].update({"content": content})

        await self.gist.edit(
            data_files,
            description=description,
        )
        await interaction.response.edit_message(content=self.gist.html_url)


class GistView(discord.ui.View):
    def __init__(self, ctx: commands.Context, gist: Gist):
        super().__init__(timeout=300)
        self.ctx = ctx
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
        await self.gist.update()
        modal = EditGistModal(self, self.gist)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete gist", style=discord.ButtonStyle.danger)
    async def _delete_gist(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        await interaction.response.edit_message(
            content="Deleted gist %s" % self.gist.id, view=None
        )
        await self.gist.delete()
        await self.stop()

    @staticmethod
    async def format_embed(embed, gist: Gist):
        embed.title = gist.id


class Test(commands.Cog):
    """Commands for testing."""

    def __init__(self, bot):
        self.bot = bot
        self.hidden = True

        self.UCP_GIST_ID = "2206767186c249f17b07ad9a299f068c"
        self.UCP_FILENAME = "Unclaimed Pokemon.txt"

    display_emoji = "🧪"

    @commands.command()
    async def gist(self, ctx, gist_url_or_id: str = None):
        embed = self.bot.Embed(title="Gist")
        gist = None
        if validators.url(str(gist_url_or_id)):
            gist_url_or_id = gist_url_or_id.split("/")[
                -2 if gist_url_or_id.endswith("/") else -1
            ]
            try:
                gist = await Gist.get_gist(GITHUB_ACCESS_TOKEN, gist_url_or_id)
            except aiohttp.ClientResponseError:
                embed.description = "Gist not found."
        view = GistView(ctx, gist)
        view.response = await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Test(bot))
