import asyncio
import datetime
import discord
import re
import zlib
import io
import os
import aiohttp
import lxml.etree as etree

from discord.ext import commands, menus
from .utils import fuzzy
from collections import Counter
from typing import Optional, Tuple
from .utils.paginator import BotPages


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode("utf-8")

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b""
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b"\n")
            while pos != -1:
                yield buf[:pos].decode("utf-8")
                buf = buf[pos + 1 :]
                pos = buf.find(b"\n")


class DocsPageSource(menus.ListPageSource):
    def __init__(self, ctx, entries: Tuple, *, per_page: int):
        super().__init__(entries, per_page=per_page)
        self.ctx = ctx
        self.bot = self.ctx.bot
        self.embed = self.bot.Embed()

    async def format_page(self, menu, entries):
        self.embed.clear_fields()
        self.embed.description = "\n".join(
            [f"[`{key}`]({url})" for key, url in entries]
        )

        maximum = self.get_max_pages()
        if maximum > 1:
            text = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            self.embed.set_footer(text=text)

        return self.embed


class Documentations(commands.Cog):
    """Documentation related category."""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "📄"

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != "# Sphinx inventory version 2":
            raise RuntimeError("Invalid objects.inv file version.")

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if "zlib" not in line:
            raise RuntimeError("Invalid objects.inv file, not z-lib compatible.")

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r"(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)")
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(":")
            if directive == "py:module" and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == "std:doc":
                subdirective = "label"

            if location.endswith("$"):
                location = location[:-1] + name

            key = name if dispname == "-" else dispname
            prefix = f"{subdirective}:" if domain == "std" else ""

            if projname == "discord.py":
                key = key.replace("discord.ext.commands.", "").replace("discord.", "")

            result[f"{prefix}{key}"] = os.path.join(url, location)

        return result

    async def build_rtfm_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            sub = cache[key] = {}
            async with aiohttp.ClientSession() as session:
                async with session.get(page + "/objects.inv") as resp:
                    if resp.status != 200:
                        raise RuntimeError(
                            "Cannot build rtfm lookup table, try again later."
                        )

                    stream = SphinxObjectFileReader(await resp.read())
                    cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache

    async def do_rtfm(self, ctx, key, obj):
        page_types = {
            "latest": "https://discordpy.readthedocs.io/en/latest",
            "python": "https://docs.python.org/3",
            "master": "https://discordpy.readthedocs.io/en/master",
        }

        if obj is None:
            await ctx.send(page_types[key])
            return

        if not hasattr(self, "_rtfm_cache"):
            await ctx.trigger_typing()
            await self.build_rtfm_lookup_table(page_types)

        obj = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", obj)

        if key.startswith("latest"):
            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == "_":
                    continue
                if q == name:
                    obj = f"abc.Messageable.{name}"
                    break

        cache = list(self._rtfm_cache[key].items())

        def transform(tup):
            return tup[0]

        matches = fuzzy.finder(obj, cache, key=lambda t: t[0], lazy=False)

        if len(matches) == 0:
            return await ctx.send("Could not find anything. Sorry.")

        formatter = DocsPageSource(ctx, matches, per_page=8)
        menu = BotPages(formatter, ctx=ctx)
        await menu.start()

    @commands.group(
        aliases=["rtfd", "rtfm", "doc", "documentation", "documentations"],
        invoke_without_command=True,
    )
    async def docs(self, ctx, *, obj: str = None):
        """Gives you a documentation link for a discord.py entity.

        Events, objects, and functions are all supported through
        a cruddy fuzzy algorithm.
        """
        key = "master"
        await self.do_rtfm(ctx, key, obj)

    @docs.command(name="python", aliases=["py"])
    async def docs_python(self, ctx, *, obj: str = None):
        """Gives you a documentation link for a Python entity."""
        key = "python"
        await self.do_rtfm(ctx, key, obj)

    @docs.command(name="latest", aliases=["1.7.3"])
    async def docs_master(self, ctx, *, obj: str = None):
        """Gives you a documentation link for a discord.py entity (master branch)"""
        await self.do_rtfm(ctx, "latest", obj)

    def library_name(self, channel):
        # language_<name>
        name = channel.name
        index = name.find("_")
        if index != -1:
            name = name[index + 1 :]
        return name.replace("-", ".")

    @commands.command(
        name="source",
        aliases=("src",),
        brief="Displays the source code of a command.",
        description="""
        Displays the full source code or for a specific command of the bot.

        Code taken from [Robodanny](https://github.com/Rapptz/RoboDanny).
        """,
    )
    async def source(self, ctx, *, command: str = None):
        """
        To display the source code of a subcommand you can separate it by periods, e.g. timer.start for the start subcommand of the timer command or by spaces.
        """

        # use the imported source function from utils/source.py
        final_url = source(self, command=command)
        await ctx.send(final_url)


async def setup(bot):
    await bot.add_cog(Documentations(bot))
