from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import importlib
import inspect
import logging
import math
import sys
from textwrap import dedent
from types import ModuleType
import discord
import re
import io
import os
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple, Union

from helpers.utils import format_join

if TYPE_CHECKING:
    from main import Bot

import zlib
import aiohttp
from discord.ext import commands, menus
from discord import app_commands
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
class DocObjectSource:
    filename: str
    url: str
    parent: bool  # Whether the parent object's source is being shown e.g. if it's an attribute
    object: object
    firstlineno: int
    code_lines: List[str]


@dataclass
class DocObject:
    label: str
    doc: Doc
    path: str
    location: str

    @property
    def docs_url(self) -> str:
        return os.path.join(self.doc.url, self.location)

    @property
    def sourceable(self) -> bool:
        return all((self.path, self.doc.source, self.doc.module_name))

    def build_source(self):
        if getattr(self, "_source", None):
            return self._source

        doc_object = None
        if self.sourceable:
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
                    doc_object = DocObjectSource(
                        filename=filename,
                        url=url,
                        object=obj,
                        parent=parent,
                        firstlineno=firstlineno,
                        code_lines=lines,
                    )

        self._source = doc_object

    def get_source(self) -> DocObjectSource | None:
        self.build_source()
        return self._source

    def clear_source(self):
        if hasattr(self, "_source"):
            del self._source


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
    url: str
    aliases: Optional[Tuple[str]] = None
    remove_substrings: Optional[Tuple[str]] = None
    module_name: Optional[str] = None
    source: Optional[DocSource] = None

    def __hash__(self) -> int:
        return hash(self.name)

    def __format__(self, spec: str) -> str:
        if "l" in spec:
            return str(len(getattr(self, "_objects", [])))
        return self.name

    @property
    def qualified_names(self) -> Tuple[str]:
        """All (lowercase) names of the doc."""

        return tuple(n.lower() for n in (self.name, *(self.aliases or [])))

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

    async def get_objects(self, ctx_or_bot: CustomContext | Bot) -> List[DocObject]:
        if not hasattr(self, "_objects"):
            # logger.info(f"Building `{self.name}` objects...")
            if isinstance(ctx_or_bot, commands.Context):
                async with ctx_or_bot.typing():
                    await self.build_objects(ctx_or_bot.bot)
            else:
                await self.build_objects(ctx_or_bot)
        return self._objects

    def clear_objects(self):
        if hasattr(self, "_source"):
            del self._objects

    async def fuzzyfind(self, ctx: CustomContext, query: str) -> Generator[DocObject]:
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
            query, await self.get_objects(ctx), key=lambda obj: obj.label, lazy=False
        )
        return matches


DOCS = {
    "python": Doc(name="Python", aliases=("py",), url="https://docs.python.org/3"),
    "discord.py": Doc(
        name="discord.py",
        url="https://discordpy.readthedocs.io/en/latest",
        aliases=("dpy", "discord"),
        remove_substrings=("ext.commands.",),
        module_name="discord",
        source=DocSource(
            base_url="https://github.com/Rapptz/discord.py",
            module=discord,
            branch_fmt_str="v{major}.{minor}.x",
        ),
    ),
    "aiohttp": Doc(
        name="aiohttp",
        url="https://docs.aiohttp.org/en/stable/",
        module_name="aiohttp",
        source=DocSource(
            base_url="https://github.com/aio-libs/aiohttp",
            module=aiohttp,
            branch_fmt_str="{major}.{minor}",
        ),
    ),
    "pymongo": Doc(
        name="PyMongo",
        url="https://pymongo.readthedocs.io/en/stable",
        aliases=("mongo", "mg", "mongodb"),
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
        url="https://pillow.readthedocs.io/en/stable",
        aliases=("pil",),
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
        objs = await doc.fuzzyfind(ctx, query) if query is not None else None

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
        self.doc = doc

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
                    source=(
                        await self.bot.loop.run_in_executor(None, obj.get_source)
                        if obj.doc.source
                        else None
                    ),
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


def normalize_indent(lines: List[str], index: Optional[int] = 0) -> List[str]:
    """Add common indentation to the line at provided index (default 0) in case it's missing it"""

    new_lines = lines[:]
    if not new_lines[index].startswith(" "):
        indent = ""
        line = discord.utils.find(lambda l: l.startswith(" "), new_lines)
        if line is not None:
            for char in line:
                if char != " ":
                    break
                indent += " "
            new_lines[0] = indent + new_lines[0]
    return new_lines


class CodeSource(menus.PageSource):
    def __init__(self, ctx: CustomContext, doc: Doc, obj: DocObject):
        self.ctx = ctx
        self.bot = self.ctx.bot

        self.doc = doc
        self.obj = obj
        self.source = obj._source
        self.filetype = self.source.filename.split(".")[-1]

        docstring = self.source.object.__doc__
        code = re.sub(
            r"""([ruRUfF]*(?:"{3}(?:.|\n)+?"{3})|(?:'{3}(?:.|\n)+?'{3}))\n *?""",
            "...\n",
            "".join(self.source.code_lines),
            1,
        )

        self.doclines = tuple(
            dedent(NL.join(normalize_indent(docstring.split(NL)))).split(NL)
        )
        self.codelines = tuple(dedent(NL.join(code.split(NL))).split(NL))

        self.entrants = {
            # lines: lines_per_page
            self.doclines: 15,
            self.codelines: 15,
        }

        self.embed = self.bot.Embed(title=obj.path, url=obj._source.url)

    async def get_page(self, page_number: int) -> int:
        return page_number

    def is_paginating(self) -> bool:
        return self.get_max_pages() > 1

    def get_num_pages(self, lines: List[str], *, per_page: int) -> int:
        return math.ceil(len(lines) / per_page)

    def get_max_pages(self) -> int:
        return max(
            [
                self.get_num_pages(lines, per_page=per_page)
                for lines, per_page in self.entrants.items()
            ]
        )

    def get_entries(
        self, lines: List[str], current_page: int, *, per_page: int
    ) -> List[str]:
        """Get entries for the current page."""

        pgstart = current_page * per_page
        max_entries = min(pgstart + per_page, len(lines))
        min_entries = max(max_entries - per_page, 0)

        return lines[min_entries:max_entries]

    def get_page_info(
        self, lines: List[str], current_page: int, *, per_page: int
    ) -> str:
        pages = self.get_num_pages(lines, per_page=per_page)
        return f"{min(current_page+1, pages)}/{pages} ({len(lines)} lines)"

    async def format_page(self, menu: BotPages, current_page: int) -> Bot.Embed:
        self.embed.clear_fields()

        doc_per_page = self.entrants[self.doclines]
        docstring = (
            f"```yaml\n"
            f"{NL.join(self.get_entries(self.doclines, current_page, per_page=doc_per_page))}\n"
            "```"
        )
        self.embed.add_field(
            name=f"docstring {self.get_page_info(self.doclines, current_page, per_page=doc_per_page)}",
            value=docstring,
            inline=False,
        )

        code_per_page = self.entrants[self.codelines]
        code = (
            f"```{self.filetype}\n"
            f"{NL.join(self.get_entries(self.codelines, current_page, per_page=code_per_page))}\n"
            "```"
        )
        self.embed.add_field(
            name=f"code {self.get_page_info(self.codelines, current_page, per_page=code_per_page)}",
            value=code,
            inline=False,
        )

        return self.embed


class SourceSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="View source code of an entity", options=[discord.SelectOption(label="-", value="-")])

    async def callback(self, interaction):
        await interaction.response.defer()
        cog: Documentation = self.view.ctx.bot.get_cog("Documentation")
        await self.view.ctx.invoke(
            cog.docs_view,
            doc_and_objects=await DocAndObjectsConverter().convert(
                self.view.ctx,
                f"{self.view.source.doc.name} {self.values[0]}"
            )
        )


class DocPages(BotPages):
    def __init__(self, source, *, ctx):
        self.source_select = SourceSelect()
        super().__init__(source, ctx=ctx)

    def _update_labels(self, page_number):
        if self.source_select not in self.children:
            self.add_item(self.source_select)

        super()._update_labels(page_number)
        self.remove_item(self.numbered_page)

    async def _get_kwargs_from_page(self, page: List[DocObject]) -> Dict[str, Any]:
        self.source_select.options = []
        for obj in page:
            src = await self.ctx.bot.loop.run_in_executor(None, obj.get_source)
            option = discord.SelectOption(
                label=obj.label,
                value=obj.label,
                description=src.object.__name__ if src.parent else ""
            )
            self.source_select.options.append(option)

        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}
        else:
            return {}


class Documentation(commands.Cog):
    """Documentation of Discord.py and source code of features"""

    def __init__(self, bot):
        self.bot = bot

    display_emoji = "📄"

    # async def cog_load(self):
    #     start = time.time()
    #     logger.info(
    #         f"LOading all documentation objects and sources..."
    #     )
    #     for doc in DOCS.values():
    #         objs = await doc.get_objects(self.bot)
    #         for obj in objs:
    #             await obj.get_source(self.bot)
    #     logger.info(
    #         f"Loaded all documentation objects and sources in \033[33;1m{round(time.time()-start, 2)}s\033[0m"
    #     )

    async def do_rtfm(self, ctx: CustomContext, doc: Doc, objs: List[DocObject] | None):
        if not objs:
            return

        PER_PAGE = 8
        formatter = DocsPageSource(ctx, doc, objs, per_page=PER_PAGE)
        menu = DocPages(formatter, ctx=ctx)
        await menu.start()

    @commands.hybrid_group(
        aliases=["rtfd", "rtfm", "rtfs", "doc", "documentation"],
        invoke_without_command=True,
        description=f"Get documentation and source code for python, discord.py, pillow, etc entities",
        usage=f"""[lib="{DEFAULT_LIBRARY}"] [entity_query=None]""",
        help=f"""
Find documentation and source code links for entities of the following modules/libraries:
{NL.join([f"- {'/'.join([f'`{n}`' for n in d.qualified_names])}" for l, d in DOCS.items()])}

Events, objects, and functions are all supported through
a cruddy fuzzy algorithm.""",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
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

    @docs.group(name="cache", invoke_without_command=True)
    async def docs_cache(self, ctx: CustomContext):
        if not hasattr(self.bot, "DOCS"):
            docs = DOCS
        else:
            docs = DOCS

        return await ctx.send(
            f"Current rtfm cache:\n"
            f"{format_join(docs.values(), '- `{0}` — {0:l} objects', joiner=NL)}"
        )

    @docs_cache.command(name="refresh", aliases=["recache"])
    async def docs_cache_refresh(self, ctx: CustomContext):
        """Refresh rtfm cache. For example to update with latest docs."""

        async with ctx.typing():
            refreshed = await self.refresh_cache(DOCS)
            await ctx.send(
                f"Refreshed rtfm cache of the following modules/libraries:\n"
                f"{format_join(refreshed, '- `{0}` — {0:l} objects ({1:+})', joiner=NL)}"
            )

    async def do_rtfs(self, ctx: CustomContext, doc: Doc, objs: List[DocObject] | None):
        # TODO: Multiple objects?
        if not objs:
            return

        if not doc.source:
            return await ctx.send(
                f"Source code is not available for the `{doc.name}` module/library due to limitations :("
            )

        for obj in objs:  # TODO: Allow multiple?
            src = await self.bot.loop.run_in_executor(None, obj.get_source)
            if src:
                break
        else:
            return await ctx.send(
                f"Source code is not available for any objects from `{doc.name}` matching your query due to limitations :("
            )

        formatter = CodeSource(ctx, doc, obj)
        menu = BotPages(formatter, ctx=ctx)
        await menu.start()

    @docs.command(
        name="source",
        aliases=("src", "view"),
        description=f"View source code for {', '.join(map(lambda s: f'`{s}`', DOCS.keys()))} entities",
        usage=f"""[lib="{DEFAULT_LIBRARY}"] [entity_query=None]""",
        help=f"""
View source code for entities of the following modules/libraries:
{NL.join([f"- {'/'.join([f'`{n}`' for n in d.qualified_names])}" for l, d in DOCS.items()])}

Events, objects, and functions are all supported through
a cruddy fuzzy algorithm.""",
    )
    async def docs_view(
        self,
        ctx: CustomContext,
        *,
        doc_and_objects: DocAndObjectsConverter = commands.param(
            default=DocAndObjectsConverter().convert
        ),
    ):
        await self.do_rtfs(ctx, *doc_and_objects)

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
