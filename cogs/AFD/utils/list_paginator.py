from typing import TYPE_CHECKING, List, Optional

import discord
from discord.ext import menus

from .utils import Category
from cogs.utils.utils import value_to_option_dict
from cogs.RDanny.utils.paginator import (
    FIRST_PAGE_SYMBOL,
    LAST_PAGE_SYMBOL,
    NEXT_PAGE_SYMBOL,
    PREVIOUS_PAGE_SYMBOL,
    BotPages,
)
from helpers.constants import NL
from helpers.context import CustomContext
from helpers.field_paginator import Field, FieldPaginationView

if TYPE_CHECKING:
    from main import Bot


class StatsPageMenu(BotPages):
    def __init__(
        self,
        categories: List[Category],
        *,
        ctx: CustomContext,
        original_embed: Bot.Embed,
    ):
        self.categories = categories
        self.original_embed = original_embed
        initial_source = StatsPageSource(categories[0], original_embed=original_embed)
        super().__init__(initial_source, ctx=ctx)
        self.add_select()

    def add_select(self):
        self.clear_items()
        self.add_item(StatsSelectMenu(self.categories, menu=self))
        self.fill_items()

    def _update_labels(self, page_number: int) -> None:
        if not self.source.is_paginating():
            for item in self.pagination_buttons:
                self.remove_item(item)
            return
        else:
            for item in self.pagination_buttons:
                if item not in self.children:
                    self.add_item(item)
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


PER_PAGE = 20


class StatsPageSource(menus.ListPageSource):
    def __init__(
        self,
        category: Category,
        *,
        original_embed: Bot.Embed,
        per_page: Optional[int] = PER_PAGE,
    ):
        super().__init__(entries=category.pokemon, per_page=per_page)
        self.category = category
        self.original_embed = original_embed
        self.per_page = per_page

    async def format_page(self, menu: StatsPageMenu, entries: List[str]):
        embed = self.original_embed.copy()
        embed.add_field(name=self.category.name, value=NL.join(entries))
        return embed


ALL_OPT_VALUE = "all"


class StatsSelectMenu(discord.ui.Select):
    def __init__(self, categories: List[Category], *, menu: StatsPageMenu):
        self.categories = categories
        self.menu = menu
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
            fields = [Field(name=c.name, values=c.pokemon) for c in self.categories]
            view = FieldPaginationView(
                self.ctx, self.menu.original_embed, fields=fields
            )
            view.clear_items()
            view.add_item(self)
            view.fill_items()

            await interaction.response.edit_message(view=view, embed=view.embed)
            view.msg = self.ctx.message
        else:
            source = StatsPageSource(
                self.categories[self.options.index(option)],
                original_embed=self.menu.original_embed,
            )
            self.menu.initial_source = source
            await self.menu.rebind(source, interaction)
