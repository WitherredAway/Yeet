from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import importlib
import inspect
import logging
import sys
from types import ModuleType
import discord
import re
import io
import os
from typing import TYPE_CHECKING, Dict, Generator, List, Optional, Tuple, Union

from cogs.utils.utils import format_join

if TYPE_CHECKING:
    from main import Bot

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


logger = logging.getLogger(__name__)


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
    base_url: str
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

    @cached_property
    def url(self) -> str:
        return f"{self.base_url}/blob/{self.branch}"


@dataclass
class Doc:
    """The Document object for a documentation source.

    Parameters
    ----------
    name: `str`
        The name of the documentation source.
    aliases: `Tuple[str]`
        The extra names that can be used to refer to this documentation source.
    url: `str`
        The documentation url.
    remove_substrings: `Optional[Tuple[str]]` = None
        A tuple of substrings that will be removed from this Doc's objects' names when parsing.
    module_name: `Optional[str]` = None
        The name of the module this Doc represents.
    source: `Optional[DocSource]` = None
        A DocSource object containing the data for showing the source code of objects. Will not
        show source code if this is None.

    Attributes
    ----------
    qualified_names: `Tuple[str]`
        A tuple of all of its names and aliases.

    Methods
    -------
    """  # TODO

    name: str
    aliases: Tuple[str]
    url: str
    remove_substrings: Optional[Tuple[str]] = None
    module_name: Optional[str] = None
    source: Optional[DocSource] = None

    def __hash__(self) -> int:
        return hash(self.name)

    def __format__(self, spec: str) -> str:
        if "l" in spec:
            if hasattr(self, "_objects"):
                return str(len(self._objects))
        return self.name

    @property
    def qualified_names(self) -> Tuple[str]:
        """All (lowercase) names of the doc."""

        return tuple(n.lower() for n in (self.name, *self.aliases))

    def parse_object_inv(self, stream: SphinxObjectFileReader) -> List[DocObject]:
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

            key = key.replace(f"{self.module_name}.", "")
            if self.remove_substrings:
                for r in self.remove_substrings:
                    key = key.replace(r, "")

            obj = DocObject(
                label=f"{prefix}{key}",
                doc=self,
                path=path,
                location=location,
            )
            result.append(obj)

        return result

    async def build_objects(self, bot: Bot):
        async with bot.session.get(os.path.join(self.url, "objects.inv")) as resp:
            if resp.status != 200:
                raise RuntimeError("Cannot build rtfm lookup table, try again later.")

            stream = SphinxObjectFileReader(await resp.read())
            self._objects = await bot.loop.run_in_executor(
                None, self.parse_object_inv, stream
            )

    async def get_objects(self, bot: Bot) -> List[DocObject]:
        if not hasattr(self, "_objects"):
            await self.build_objects(bot)
        return self._objects

    def clear_objects(self):
        if hasattr(self, "_source"):
            del self._objects

    async def fuzzyfind(self, bot: Bot, query: str) -> Generator[DocObject]:
        query = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", query)
        if self.name.lower().startswith("discord.py"):
            # point the abc.Messageable types properly:
            q = query.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == "_":
                    continue
                if q == name:
                    query = f"abc.Messageable.{name}"
                    break

        matches = fuzzy.finder(
            query, await self.get_objects(bot), key=lambda obj: obj.label, lazy=False
        )
        return matches


@dataclass
class DocObjectSource:
    url: str
    parent: bool  # Whether the parent object's source is being shown e.g. if it's an attribute
    object: object


@dataclass
class DocObject:
    label: str
    doc: Doc
    path: str
    location: str

    @property
    def docs_url(self) -> str:
        return os.path.join(self.doc.url, self.location)

    def build_source(self):
        doc_object = None
        if all((self.path, self.doc.source, self.doc.module_name)):
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

            if module is not None:
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
                        parent = (
                            True  # Whether the parent object's source is being shown
                        )
                        break
                    except OSError:
                        print(f"Failed to get source of {candidate}.")
                        continue
                    else:
                        obj = candidate

                if obj is not None:
                    location = os.path.join(
                        self.doc.source.directory,
                        os.path.relpath(filename)
                        .replace("\\", "/")
                        .split("/site-packages/")[
                            -1
                        ],  # Might cause issues for hardcoding 'site-packages'
                    )
                    url = f"{self.doc.source.url}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}"
                    doc_object = DocObjectSource(url=url, object=obj, parent=parent)

        self._source = doc_object

    async def get_source(self, bot: Bot) -> DocObjectSource | None:
        if not hasattr(self, "_source"):
            await bot.loop.run_in_executor(None, self.build_source)
        return self._source

    def clear_source(self):
        if hasattr(self, "_source"):
            del self._source


DOCS = {
    "python": Doc(name="Python", aliases=("py",), url="https://docs.python.org/3"),
    "discord.py": Doc(
        name="discord.py",
        aliases=("dpy", "discord"),
        url="https://discordpy.readthedocs.io/en/latest",
        remove_substrings=("ext.commands.",),
        module_name="discord",
        source=DocSource(
            base_url="https://github.com/Rapptz/discord.py",
            module=discord,
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
            base_url="https://github.com/mongodb/mongo-python-driver",
            module=pymongo,
            branch_fmt_str="v{major}.{minor}",
        ),
    ),
    "pillow": Doc(
        name="Pillow",
        aliases=("pil",),
        url="https://pillow.readthedocs.io/en/stable",
        module_name="PIL",
        source=DocSource(
            base_url="https://github.com/python-pillow/Pillow",
            module=PIL,
            branch_fmt_str="{major}.{minor}.x",
            directory="src",
        ),
    ),
}

DEFAULT_LIBRARY = "discord.py"


class DocAndObjectsConverter(commands.Converter):
    async def convert(
        self, ctx: CustomContext, lib_and_query: Optional[str] = None
    ) -> Tuple[Doc, Union[List[DocObject], None]]:
        if not lib_and_query:  # No parameters pass. use default lib and no query
            lib, query = DEFAULT_LIBRARY, None

        else:
            names = {a: l for l, d in DOCS.items() for a in d.qualified_names}

            lib_and_or_query = lib_and_query.split(" ", 1)
            if len(lib_and_or_query) == 1:
                # Only lib or query passed in
                if lib_and_or_query[0] in names:  # It's lib. no query
                    # We don't want to lower the entire thing, just the library name
                    lib, query = names[lib_and_or_query[0].lower()], None
                else:  # It's query. use default lib
                    lib, query = DEFAULT_LIBRARY, lib_and_or_query[0]
            else:
                # Two supposed parameters passed
                lib, query = lib_and_or_query
                if og_lib := names.get(lib.lower()):  # If first one is lib
                    lib, query = og_lib, query
                else:
                    lib, query = (
                        DEFAULT_LIBRARY,
                        lib_and_query,
                    )  # If the entire thing is query. use default lib

        doc = DOCS[lib]
        objs = await doc.fuzzyfind(ctx.bot, query) if query is not None else None

        if objs is None:
            await ctx.send(
                format_doc(
                    label=doc.name,
                    docs_url=doc.url,
                    source=doc.source,
                )
            )
        elif len(objs) == 0:
            await ctx.send(
                f"Could not find anything in `{doc.name}`'s entities, sorry."
            )

        return doc, objs


def format_doc(label: str, docs_url: str, source: DocObjectSource | DocSource = None):
    text = f"[`{label}`]({docs_url})"
    if source:
        source_text = f"{'ᵖᵃʳᵉⁿᵗ ' if getattr(source, 'parent', None) else ''}ˢᵒᵘʳᶜᵉ"
        text += f" \u200b *[{source_text}]({source.url})*" if source else ""

    return text


class DocsPageSource(menus.ListPageSource):
    def __init__(
        self, ctx: CustomContext, doc: Doc, objects: List[DocObject], *, per_page: int
    ):
        super().__init__(objects, per_page=per_page)
        self.ctx = ctx
        self.bot = self.ctx.bot

        self.embed = self.bot.Embed(
            title=f"{doc.name}"
            + (f" v{doc.source.module.__version__}" if doc.source else "")
        )

    async def format_page(self, menu, objects: List[DocObject]):
        self.embed.clear_fields()
        self.embed.description = "\n".join(
            [
                format_doc(
                    label=obj.label,
                    docs_url=obj.docs_url,
                    source=await obj.get_source(self.bot),
                )
                for obj in objects
            ]
        )

        maximum = self.get_max_pages()
        if maximum > 1:
            text = (
                f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} objects)"
            )
            self.embed.set_footer(text=text)

        return self.embed


class Documentation(commands.Cog):
    """Documentation of Discord.py and source code of features"""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "📄"

    async def do_rtfm(self, ctx: CustomContext, doc: Doc, objs: List[DocObject] | None):
        if not objs:
            return

        formatter = DocsPageSource(ctx, doc, objs, per_page=8)
        menu = BotPages(formatter, ctx=ctx)
        await menu.start()

    @commands.group(
        aliases=["rtfd", "rtfm", "rtfs", "doc", "documentation"],
        invoke_without_command=True,
        brief=f"Get documentation and source code links for {', '.join(map(lambda s: f'`{s}`', DOCS.keys()))} entities",
        usage=f"""[lib="{DEFAULT_LIBRARY}"] [entity_query=None]""",
        description=f"""
Find documentation and source code links for entities of the following modules/libraries:
{NL.join([f"- {'/'.join([f'`{n}`' for n in d.qualified_names])}" for l, d in DOCS.items()])}

Events, objects, and functions are all supported through
a cruddy fuzzy algorithm.""",
    )
    async def docs(
        self,
        ctx: CustomContext,
        *,
        doc_and_objects: DocAndObjectsConverter = commands.param(
            default=DocAndObjectsConverter().convert
        ),
    ):
        await self.do_rtfm(ctx, *doc_and_objects)

    async def refresh_cache(self, libraries: Dict[str, Doc]) -> Tuple[Doc]:
        refreshed = {}
        for doc_name, doc in libraries.items():
            old_objs = len(getattr(doc, "_objects", []))
            await doc.build_objects(self.bot)
            refreshed[doc] = len(doc._objects) - old_objs
        return tuple(refreshed.items())

    @docs.command(name="refresh", aliases=["recache"])
    async def docs_refresh_cache(self, ctx: CustomContext):
        """Refresh rtfm cache. For example to update with latest docs."""

        async with ctx.typing():
            refreshed = await self.refresh_cache(DOCS)
            await ctx.send(
                f"Refreshed rtfm cache of the following modules/libraries:\n"
                f"{format_join(refreshed, '- `{0}` — {0:l} objects ({1:+})', joiner=NL)}"
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
    async def source(self, ctx: CustomContext, *, command: str = None):
        """
        To display the source code of a subcommand. You can separate it by periods, e.g. timer.start for the start subcommand of the timer command or by spaces.
        """
        # use the imported source function from utils/source.py
        final_url = source(self.bot, command=command)
        await ctx.send(f"<{final_url}>")


async def setup(bot):
    await bot.add_cog(Documentation(bot))
