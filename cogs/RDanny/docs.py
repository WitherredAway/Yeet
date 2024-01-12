from dataclasses import dataclass
from functools import cached_property
import importlib
import inspect
import sys
from types import ModuleType
import discord
import re
import io
import os
from typing import Dict, List, Optional, Tuple, Union

import zlib
import aiohttp
from discord.ext import commands, menus
from helpers.constants import NL

from helpers.context import CustomContext

from .utils import fuzzy
from .utils.paginator import BotPages
from .utils.source import source

# Imports that are for getting source code
# but not actually used here
import PIL
import pymongo


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


@dataclass
class DocSource:
    url: str
    module: ModuleType
    branch_fmt_str: Optional[str] = "master"
    directory: Optional[str] = ""

    @cached_property
    def branch(self) -> str:
        version = getattr(self.module, "__version__")
        if not version:
            return self.branch_fmt_str
        major, minor, macro = version.split(".")
        return self.branch_fmt_str.format_map(
            dict(major=major, minor=minor, macro=macro)
        )


@dataclass
class Doc:
    name: str
    aliases: Tuple[str]
    url: str
    remove_substrings: Optional[Tuple[str]] = None
    module_name: Optional[str] = None
    source: Optional[DocSource] = None

    @property
    def qualified_names(self) -> Tuple[str]:
        return (name.lower() for name in self.aliases + (self.name,))


@dataclass
class DocEntrySource:
    url: str
    parent: bool  # Whether the parent object's source is being shown e.g. if it's an attribute
    object: object


@dataclass
class DocEntry:
    name: str
    doc: Doc
    path: str
    location: str

    @property
    def docs_url(self) -> str:
        return os.path.join(self.doc.url, self.location)

    def get_source(self) -> DocEntrySource | None:
        if hasattr(self, "_source"):
            return self._source

        if not self.path or not self.doc.source or not self.doc.module_name:
            return None

        parent_module_name = self.doc.module_name
        split = self.path.split(".")
        if len(split) == 1 and split[0] != parent_module_name:
            split.insert(0, parent_module_name)

        # Get module name by looping through and importing all
        # cummulative split parts from the start until it errors.
        # Hacky but it works. Theoretically.
        module = None
        for i in range(len(split)):
            try:
                module_name = ".".join(split[0 : i + 1])
                candidate = sys.modules.get(module_name) or importlib.import_module(
                    module_name
                )
            except ModuleNotFoundError:
                break
            else:
                module = candidate
                if module_name not in sys.modules:
                    sys.modules[module_name] = module

        if module is None:
            return None

        split = split[i:]
        obj = None
        filename = None
        parent = False
        for attr in split:
            try:
                candidate = getattr(obj or module, attr)
                filename = inspect.getsourcefile(candidate)
                lines, firstlineno = inspect.getsourcelines(candidate)
            except (AttributeError, TypeError):
                parent = True  # Whether the parent object's source is being shown
                break
            except OSError:
                print(f"Failed to get source of {candidate}.")
                continue
            else:
                obj = candidate

        if obj is None:
            return None

        location = os.path.join(
            self.doc.source.directory,
            os.path.relpath(filename).replace("\\", "/").split("/site-packages/")[-1]  # Might cause issues for hardcoding 'site-packages'
        )
        url = f"{self.doc.source.url}/blob/{self.doc.source.branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}"

        self._source = DocEntrySource(url=url, object=obj, parent=parent)
        return self._source


LIBRARIES = {
    "python": Doc(
        name="Python",
        aliases=("py",),
        url="https://docs.python.org/3"
    ),
    "discord.py": Doc(
        name="discord.py",
        aliases=("dpy", "discord"),
        url="https://discordpy.readthedocs.io/en/latest",
        remove_substrings=("ext.commands.",),
        module_name="discord",
        source=DocSource(
            module=discord,
            url="https://github.com/Rapptz/discord.py",
            branch_fmt_str="v{major}.{minor}.x",
        ),
    ),
    "pymongo": Doc(
        name="PyMongo",
        aliases=("mongo",),
        url="https://pymongo.readthedocs.io/en/stable",
        remove_substrings=("collection.",),
        module_name="pymongo",
        source=DocSource(
            module=pymongo,
            url="https://github.com/mongodb/mongo-python-driver",
            branch_fmt_str="v{major}.{minor}",
        ),
    ),
    "pillow": Doc(
        name="Pillow",
        aliases=("pil",),
        url="https://pillow.readthedocs.io/en/stable",
        module_name="PIL",
        source=DocSource(
            module=PIL,
            url="https://github.com/python-pillow/Pillow",
            branch_fmt_str="{major}.{minor}.x",
            directory="src",
        ),
    ),
}

DEFAULT_LIBRARY = "discord.py"

class LibraryAndQueryConverter(commands.Converter):
    async def convert(self, ctx: CustomContext, lib_and_query: Optional[str] = None) -> Tuple[str, Union[str, None]]:
        if not lib_and_query:
            return DEFAULT_LIBRARY, None

        split = lib_and_query.split(" ", 1)
        if len(split) == 1:
            split.insert(0, DEFAULT_LIBRARY)

        lib, query = split
        names = {a: l for l, d in LIBRARIES.items() for a in d.qualified_names}
        if og_lib := names.get(lib.lower()):
            return og_lib, query
        else:
            return DEFAULT_LIBRARY, lib_and_query


def format_doc(label: str, docs_url: str, source: DocEntrySource = None):
    text = f"[`{label}`]({docs_url})"
    if source:
        source_text = f"{'ᵖᵃʳᵉⁿᵗ ' if source.parent else ''}ˢᵒᵘʳᶜᵉ"
        text += f" \u200b *[{source_text}]({source.url})*" if source else ""

    return text


class DocsPageSource(menus.ListPageSource):
    def __init__(
        self, ctx: CustomContext, lib: str, entries: List[DocEntry], *, per_page: int
    ):
        super().__init__(entries, per_page=per_page)
        self.ctx = ctx
        self.bot = self.ctx.bot

        doc = LIBRARIES[lib]
        self.embed = self.bot.Embed(
            title=f"{doc.name}"
            + (f" v{doc.source.module.__version__}" if doc.source else "")
        )

    async def format_page(self, menu, entries: List[DocEntry]):
        self.embed.clear_fields()
        self.embed.description = "\n".join(
            [
                format_doc(
                    label=doc_entry.name,
                    docs_url=doc_entry.docs_url,
                    source=await self.bot.loop.run_in_executor(
                        None, doc_entry.get_source
                    ),
                )
                for doc_entry in entries
            ]
        )

        maximum = self.get_max_pages()
        if maximum > 1:
            text = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)"
            )
            self.embed.set_footer(text=text)

        return self.embed


class Documentation(commands.Cog):
    """Documentation of Discord.py and source code of features"""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "📄"

    def parse_object_inv(self, stream: SphinxObjectFileReader, doc: Doc):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = []

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

            key = path = name if dispname == "-" else dispname
            prefix = f"{subdirective}:" if domain == "std" else ""

            key = key.replace(f"{doc.module_name}.", "")
            if doc.remove_substrings:
                for r in doc.remove_substrings:
                    key = key.replace(r, "")

            doc_entry = DocEntry(
                name=f"{prefix}{key}",
                doc=doc,
                path=path,
                location=location,
            )
            result.append(doc_entry)

        return result

    async def build_rtfm_lookup_table(self, docs: Dict[str, Doc]):
        cache = {}
        for doc_name, doc in docs.items():
            sub = cache[doc_name] = {}
            async with aiohttp.ClientSession() as session:
                async with session.get(os.path.join(doc.url, "objects.inv")) as resp:
                    if resp.status != 200:
                        raise RuntimeError(
                            "Cannot build rtfm lookup table, try again later."
                        )

                    stream = SphinxObjectFileReader(await resp.read())
                    cache[doc_name] = self.parse_object_inv(stream, doc)

        self._rtfm_cache = cache

    async def do_rtfm(self, ctx: CustomContext, lib: str, query: str):
        if query is None:
            doc = LIBRARIES[lib]
            await ctx.send(
                format_doc(
                    name=doc.name,
                    docs_url=doc.url,
                    source_url=getattr(doc.source, "url", None),
                )
            )
            return

        if not hasattr(self, "_rtfm_cache"):
            await ctx.typing()
            await self.build_rtfm_lookup_table(LIBRARIES)

        query = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", query)

        if lib.startswith("discord.py"):
            # point the abc.Messageable types properly:
            q = query.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == "_":
                    continue
                if q == name:
                    query = f"abc.Messageable.{name}"
                    break

        cache = self._rtfm_cache[lib]

        def transform(tup):
            return tup[0]

        matches = fuzzy.finder(query, cache, key=lambda t: t.name, lazy=False)

        if len(matches) == 0:
            return await ctx.send(f"Could not find anything in `{lib}`'s entities, sorry.")

        formatter = DocsPageSource(ctx, lib, matches, per_page=8)
        menu = BotPages(formatter, ctx=ctx)
        await menu.start()

    @commands.group(
        aliases=["rtfd", "rtfm", "rtfs", "doc", "documentation"],
        invoke_without_command=True,
        brief=f"Get documentation and source code links for {', '.join(map(lambda s: f'`{s}`', LIBRARIES.keys()))} entities",
        usage=f"""[lib="{DEFAULT_LIBRARY}"] [entity_query=None]""",
        description=f"""
Find documentation and source code links for entities of the following modules/libraries:
{NL.join([f"- {' | '.join(f'`{d.qualified_names}`')}" for l, d in LIBRARIES.items()])}

Events, objects, and functions are all supported through
a cruddy fuzzy algorithm."""
    )
    async def docs(self, ctx, *, lib_and_query: LibraryAndQueryConverter = commands.param(converter=LibraryAndQueryConverter)):
        await self.do_rtfm(ctx, *lib_and_query)

    @docs.command(name="view")
    async def docs_view(self, ctx):
        ...

    @docs.command(name="refresh", aliases=["delcache", "del-cache"])
    async def docs_refresh_cache(self, ctx):
        """Refresh rtfm cache. For example to update with latest docs."""

        async with ctx.typing():
            await self.build_rtfm_lookup_table(LIBRARIES)
            refreshed = self._rtfm_cache.keys()
            await ctx.send(
                f"Refreshed rtfm cache for {', '.join(map(lambda s: f'`{s}`', refreshed))}."
            )

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
        To display the source code of a subcommand. You can separate it by periods, e.g. timer.start for the start subcommand of the timer command or by spaces.
        """
        # use the imported source function from utils/source.py
        final_url = source(self.bot, command=command)
        await ctx.send(f"<{final_url}>")


async def setup(bot):
    await bot.add_cog(Documentation(bot))
