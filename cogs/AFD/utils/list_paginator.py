from __future__ import annotations
from collections import defaultdict
import itertools
import math

from typing import TYPE_CHECKING, List, Optional, Tuple, Union

import discord
from discord.ext import menus

from cogs.Draw.utils.constants import ALPHABET_EMOJIS

from .utils import Category
from cogs.utils.utils import value_to_option_dict
from cogs.RDanny.utils.paginator import (
    FIRST_PAGE_SYMBOL,
    LAST_PAGE_SYMBOL,
    NEXT_PAGE_SYMBOL,
    PREVIOUS_PAGE_SYMBOL,
    BotPages,
)
from helpers.constants import EMBED_DESC_CHAR_LIMIT, NL
from helpers.context import CustomContext
from helpers.field_paginator import Field, FieldPaginationView

if TYPE_CHECKING:
    from main import Bot


STATS_PER_PAGE = 20

class StatsPageMenu(BotPages):
    def __init__(
        self,
        categories: List[Category],
        *,
        ctx: CustomContext,
        original_embed: Bot.Embed,
        total_amount: int
    ):
        self.categories = categories
        self.original_embed = original_embed
        self.total_amount = total_amount
        initial_source = StatsPageSource(categories[0], original_embed=original_embed)
        super().__init__(initial_source, ctx=ctx, compact=False)
        self.add_select(StatsSelectMenu(self))

    def add_select(self, select: discord.SelectMenu):
        self.clear_items()
        self.add_item(select)
        self.fill_items()

    def fill_items(self) -> None:
        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            self.add_item(self.go_to_first_page)  # type: ignore
            self.go_to_first_page.label = f"1 {FIRST_PAGE_SYMBOL}"
            self.add_item(self.go_to_previous_page)  # type: ignore
            # self.add_item(self.stop_pages)   type: ignore
            self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            self.add_item(self.go_to_last_page)  # type: ignore
            self.go_to_last_page.label = f"{LAST_PAGE_SYMBOL} {max_pages}"
            if not use_last_and_first:
                self.go_to_first_page.disabled = True
                self.go_to_last_page.disabled = True

    async def rebind(
        self, source: menus.PageSource, interaction: discord.Interaction
    ) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)

class StatsPageSource(menus.ListPageSource):
    def __init__(
        self,
        category: Category,
        *,
        original_embed: Bot.Embed,
        per_page: Optional[int] = STATS_PER_PAGE,
    ):
        self.entries = category.pokemon
        super().__init__(entries=category.enumerated_pokemon, per_page=per_page)
        self.category = category
        self.original_embed = original_embed
        self.per_page = per_page

    async def format_page(self, menu: StatsPageMenu, entries: List[str]):
        embed = self.original_embed.copy()
        embed.add_field(name=f"{self.category.name} {self.category.progress()}\n{self.category.progress_bar()}", value=NL.join(entries))
        return embed

ALL_OPT_VALUE = "all"

class StatsSelectMenu(discord.ui.Select):
    def __init__(self, menu: StatsPageMenu):
        self.menu = menu
        self.categories = menu.categories
        self.ctx = menu.ctx
        super().__init__(placeholder="Change category", row=0)
        self.__fill_options()
        self.set_default(self.options[0])

    def __fill_options(self):
        for idx, category in enumerate(self.categories):
            name = category.name.split(" ")
            self.add_option(
                label=name[0],
                value=str(idx),
                description=category.name,
            )
        self.add_option(
            label="All",
            value=ALL_OPT_VALUE,
            description="All categories with individual pagination",
        )

    def set_default(self, option: discord.SelectOption):
        for o in self.options:
            o.default = False
        option.default = True

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        option = value_to_option_dict(self)[value]
        if option.default is True:
            return  # Return if user selected the same option
        self.set_default(option)

        if value == ALL_OPT_VALUE:
            fields = [Field(name=f"{c.name} {c.progress()}\n{c.progress_bar()}", values=c.enumerated_pokemon) for c in self.categories]
            view = FieldPaginationView(
                self.ctx, self.menu.original_embed, fields=fields
            )
            view.clear_items()
            view.add_item(self)
            view.fill_items()

            await interaction.response.edit_message(view=view, embed=view.embed)
            view.msg = await interaction.original_message()
        else:
            source = StatsPageSource(
                self.categories[self.options.index(option)],
                original_embed=self.menu.original_embed,
            )
            self.menu.initial_source = source
            await self.menu.rebind(source, interaction)


LIST_PER_PAGE = 20

def get_initial(
    name: str, *, bold: Optional[bool] = False
) -> Union[str, Optional[str]]:
    initial = name[0]
    bolded_name = [c for c in name]
    for idx, letter in enumerate(name):
        if letter.upper() in ALPHABET_EMOJIS.keys():
            initial = letter
            bolded_name[idx] = f"**{initial}**"
            break
        else:
            continue
    return (initial, "".join(bolded_name)) if bold else initial

class ListPageMenu(BotPages):
    def __init__(
        self,
        source: menus.ListPageSource,
        *,
        ctx: CustomContext,
        select: Optional[bool] = False
    ):
        self.ctx = ctx
        self.bot = ctx.bot
        self.do_select = select
        super().__init__(source, ctx=ctx)
        if select is True and self.source.is_paginating():
            self.select: ListSelectMenu = self.add_select(ListSelectMenu(self))

    def add_select(self, select: discord.SelectMenu) -> discord.SelectMenu:
        self.clear_items()
        self.add_item(select)
        self.fill_items()
        return select

    def _update_labels(self, page_number: int) -> None:
        if not self.source.is_paginating():
            for item in self.pagination_buttons:
                self.remove_item(item)
            return
        else:
            for item in self.pagination_buttons:
                if item not in self.children:
                    self.add_item(item)
            if self.do_select is True:
                self.select.set_default(str(self.current_page))

        max_pages = self.source.get_max_pages()
        self.go_to_first_page.disabled = page_number == 0

        self.go_to_previous_page.label = f"{page_number} {PREVIOUS_PAGE_SYMBOL}"
        self.go_to_current_page.label = f"{page_number + 1}/{max_pages}"
        self.go_to_next_page.label = f"{NEXT_PAGE_SYMBOL} {page_number + 2}"

        self.go_to_next_page.disabled = False
        self.go_to_previous_page.disabled = False
        # self.go_to_first_page.disabled = False

        if max_pages is not None:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages
            self.go_to_last_page.label = f"{LAST_PAGE_SYMBOL} {max_pages}"
            if (page_number + 1) >= max_pages:
                self.go_to_next_page.disabled = True
                self.go_to_next_page.label = NEXT_PAGE_SYMBOL
            if page_number == 0:
                self.go_to_previous_page.disabled = True
                self.go_to_previous_page.label = PREVIOUS_PAGE_SYMBOL

    def fill_items(self) -> None:
        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            self.add_item(self.go_to_first_page)  # type: ignore
            self.go_to_first_page.label = f"1 {FIRST_PAGE_SYMBOL}"
            self.add_item(self.go_to_previous_page)  # type: ignore
            # self.add_item(self.stop_pages)   type: ignore
            self.add_item(self.go_to_current_page)  # type: ignore
            self.add_item(self.go_to_next_page)  # type: ignore
            self.add_item(self.go_to_last_page)  # type: ignore
            self.go_to_last_page.label = f"{LAST_PAGE_SYMBOL} {max_pages}"
            if not use_last_and_first:
                self.go_to_first_page.disabled = True
                self.go_to_last_page.disabled = True

    async def rebind(
        self, source: menus.PageSource, interaction: discord.Interaction
    ) -> None:
        self.source = source
        self.current_page = 0

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(0)
        await interaction.response.edit_message(**kwargs, view=self)

class ListPageSource(menus.ListPageSource):
    def __init__(
        self,
        category: Category,
        *,
        entries: List[str],
        dynamic_pages: Optional[bool] = False,
        max_per_page: Optional[int] = LIST_PER_PAGE
    ):
        self.joiner = NL
        # If dynamic_pages is true, each page should have as many entries as possible.
        if dynamic_pages is True:
            pages = []
            for entry in entries:
                if len(pages) == 0:
                    pages.append([])

                p = pages[-1] + [entry]
                if (len(self.joiner.join(p)) >= EMBED_DESC_CHAR_LIMIT) or (len(p) > max_per_page):
                    pages.append([])
                pages[-1].append(entry)

            per_page = 1
        else:
            pages = entries
            per_page = max_per_page

        self.category = category
        super().__init__(entries=pages, per_page=per_page)

    async def format_page(self, menu: ListPageMenu, entries: List[str]):
        embed = menu.bot.Embed(title=f"{self.category.name} {self.category.progress()}\n{self.category.progress_bar()}", description=self.joiner.join(entries))
        embed.set_footer(
            text=f"Use the `{menu.ctx.clean_prefix}afd view <pokemon>` command to see more info on and interact with an entry"
        )
        return embed


class ListSelectMenu(discord.ui.Select):
    def __init__(self, menu: ListPageMenu):
        super().__init__(placeholder="Jump to page", row=0)
        self.menu = menu
        self.category = menu.source.category
        self.__fill_options()
        self.set_default(self.options[0])

    def __fill_options(self):
        initials = defaultdict(list)
        for idx, pkm in enumerate(self.category.pokemon):
            initial = get_initial(pkm)
            if initial not in list(itertools.chain(*list(initials.values()))):
                initials[math.floor(idx / self.menu.source.per_page)].append(initial)

        for page, initials in initials.items():
            self.add_option(
                label=", ".join(initials),
                value=str(page),
                # emoji=ALPHABET_EMOJIS.get(initials[0], "#️⃣"),
            )

    def set_default(self, value_or_option: Union[str, discord.SelectOption]):
        if isinstance(value_or_option, discord.SelectOption):
            option = value_or_option
        else:
            value_or_option = int(value_or_option)
            vals = [int(o.value) for o in self.options]
            if value_or_option not in vals:
                value_or_option = vals[
                    list(sorted(vals + [value_or_option])).index(value_or_option) - 1
                ]  # get the one before it if it doesnt exist
            option = value_to_option_dict(self)[str(value_or_option)]

        for o in self.options:
            o.default = False
        option.default = True

    async def callback(self, interaction: discord.Interaction):
        page = self.values[0]
        self.set_default(page)

        await self.menu.show_checked_page(interaction, int(page))


FIELDS_PER_PAGE = 3

class FieldPageSource(menus.ListPageSource):
    def __init__(
        self,
        category: Category,
        *,
        entries: List[Tuple[str, str]]
    ):
        self.category = category
        super().__init__(entries=entries, per_page=FIELDS_PER_PAGE)

    async def format_page(self, menu: ListPageMenu, entries: List[Tuple[str, str]]):
        embed = menu.bot.Embed(title=f"{self.category.name} {self.category.progress()}\n{self.category.progress_bar()}")
        for name, value in entries:
            embed.add_field(name=name, value=value)
        return embed
