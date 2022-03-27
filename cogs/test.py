import typing
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


class Github:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self._req_lock = asyncio.Lock()

    async def request(
        self, method, url, *, params=None, data=None, headers=None
    ):
        hdrs = {
            "Accept": "application/vnd.github.inertia-preview+json",
            "User-Agent": "WitherredAway",
            "Authorization": "token %s" % self.access_token,
        }

        request_url = yarl.URL(GITHUB_API) / url

        if headers is not None and isinstance(headers, dict):
            hdrs.update(headers)

        await self._req_lock.acquire()
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.request(method, request_url, params=params, json=data, headers=hdrs)
                remaining = response.headers.get("X-Ratelimit-Remaining")
                json_data = await response.json()
                if response.status == 429 or remaining == "0":
                    delta = discord.utils._parse_ratelimit_header(response)
                    await asyncio.sleep(delta)
                    self._req_lock.release()
                    return await self.request(
                        method, url, params=params, data=data, headers=headers
                    )
                elif 300 > response.status >= 200:
                    return json_data
                else:
                    raise response.raise_for_status()
        finally:
            if self._req_lock.locked():
                self._req_lock.release()


class Gist:
    def __init__(self, access_token: str = os.getenv("githubTOKEN")):
        self.access_token = access_token
        self.github = Github(self.access_token)

    @staticmethod
    async def fetch_data(gist_id: str, access_token: str):
        """Fetch data of a Gist"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        url = "gists/%s" % gist_id

        github = Github(access_token)
        gist_data_json = await github.request("GET", url, headers=headers)
        return gist_data_json

    async def update(self):
        """Re-fetch data and update the instance."""
        updated_gist_data = await self.fetch_data(self.id, self.access_token)
        self.__dict__.update(updated_gist_data)
    
    @classmethod
    async def get_gist(cls, access_token: str, gist_id: str):
        gist_obj = cls(access_token)
        gist_obj.__dict__.update(await cls.fetch_data(gist_id, access_token))
        return gist_obj

    @classmethod
    async def create_gist(
        cls,
        access_token: str,
        content: str,
        *,
        description: str = None,
        filename: str = "output.txt",
        public: bool = True,
    ):
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        data = {"public": public, "files": {filename: {"content": content}}}
        params = {"scope": "gist"}

        if description:
            data["description"] = description

        github = Github(access_token)
        js = await github.request(
           "POST", "gists", data=data, headers=headers, params=params
        )
        return await cls.get_gist(access_token, js["id"])

    async def edit(
        self,
        files: typing.Dict, # e.g. {"output.txt": {"content": "Content if the file"}}
        *,
        description: str = None,
    ):
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        data = {
            "files": files
        }

        if description:
            data["description"] = description

        url = "gists/%s" % self.id
        
        js = await self.github.request("PATCH", url, data=data, headers=headers)

    async def delete(
        self,
    ):
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        url = "gists/%s" % self.id
        js = await self.github.request("DELETE", url, headers=headers)


class CreateGistModal(discord.ui.Modal):

    filename = discord.ui.TextInput(
        label="Filename",
        min_length=1,
        max_length=100,
        placeholder="output.txt",
        default="output.txt",
    )
    description = discord.ui.TextInput(label="Description", max_length=1000, placeholder="Description")
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

        await interaction.response.edit_message(content=self.gist.html_url, view=self.view)


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
                custom_id="gist_description"
            )
        )
        
        self.add_item(
            discord.ui.TextInput(
                label="Edit a specific file",
                style=discord.TextStyle.short,
                placeholder="Input existing filename to edit file,\nInput new filename to create a new file.",
                custom_id="new_filename"
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
        ch_dict = {
            child.custom_id: child.__dict__ for child in self.children
        }
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
                    data_files[filename].update(
                        {
                             "content": content
                        }
                    )
                except KeyError:
                    data_files[filename] = {
                        "filename": filename,
                        "content": content
                    }
            
            # If the child's custom_id ends with content
            elif child_custom_id.endswith("_content"):
                # It is the content of a file
                content = value
                # Set its value as the corresponding file's content
                filename = child_custom_id.split("_")[0]
                data_files[filename].update(
                    {
                        "content": content
                    }
                )
                
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
        await interaction.response.edit_message(content="Deleted gist %s" % self.gist.id, view=None)
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

        #self.update_unclaimed_pokemon.start()

    #def cog_unload(self):
        #self.update_unclaimed_pokemon.cancel()

    display_emoji = "🧪"

    @commands.command()
    async def gist(self, ctx, gist_url_or_id: str = None):
        embed = self.bot.Embed(title="Gist")
        gist = None
        if validators.url(str(gist_url_or_id)):
            gist_url_or_id = gist_url_or_id.split("/")[-2 if gist_url_or_id.endswith("/") else -1]
            try:
                gist = await Gist.get_gist(GITHUB_ACCESS_TOKEN, gist_url_or_id)
            except aiohttp.ClientResponseError:
                embed.description = "Gist not found."
        view = GistView(ctx, gist)
        view.response = await ctx.send(embed=embed, view=view)
        

    async def get_unclaimed(self):
        pk = pd.read_csv(
            "https://docs.google.com/spreadsheets/d/1-FBEjg5p6WxICTGLn0rvqwSdk30AmZqZgOOwsI2X1a4/export?gid=0&format=csv",
            index_col=0,
            header=6,
        )

        msg = "\n".join(sorted(list(pk["Name"][pk["Person in Charge"].isna()])))
        return msg

    # The task that updates the unclaimed pokemon gist
    @tasks.loop(minutes=5)
    async def update_unclaimed_pokemon(self):
        content = await self.get_unclaimed()
        amount = len(content.split("\n"))
        if hasattr(self, "amount"):
            if self.amount == amount:
                return
        else:
            self.amount = amount

        github = Github(self.bot)
        date = (datetime.datetime.utcnow()).strftime("%I:%M%p, %d/%m/%Y")

        gist_url = await github.edit_gist(
            self.UCP_GIST_ID,
            content,
            description="%s unclaimed pokemon as of %s GMT (Checks every 5 minutes, and updates only if there is a change)"
            % (amount, date),
            filename=self.UCP_FILENAME,
        )
        await self.bot.update_channel.send("Updated! %s (%s)" % (gist_url, amount))

    @update_unclaimed_pokemon.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Test(bot))
