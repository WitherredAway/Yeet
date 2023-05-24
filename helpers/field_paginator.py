from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

import discord
from cogs.RDanny.utils.paginator import (
    FIRST_PAGE_SYMBOL,
    LAST_PAGE_SYMBOL,
    NEXT_PAGE_SYMBOL,
    PREVIOUS_PAGE_SYMBOL,
)

from helpers.constants import NL
from helpers.context import CustomContext

if TYPE_CHECKING:
    from main import Bot


FIELD_PER_PAGE = 10


@dataclass
class Field:
    name: str
    values: List[str]
    per_page: Optional[int] = FIELD_PER_PAGE

    def __post_init__(self):
        self.page_number: int = 0

        pages, left_over = divmod(len(self.values), self.per_page)
        if left_over:
            pages += 1

        self.max_pages = pages

        self.first_page_button = FirstPageButton(self)
        self.previous_page_button = PreviousPageButton(self)
        self.name_button = FieldNameButton(self)
        self.next_page_button = NextPageButton(self)
        self.last_page_button = LastPageButton(self)

    def is_paginating(self) -> bool:
        return self.max_pages > 1

    @property
    def value(self) -> str:
        _from = self.per_page * self.page_number
        return NL.join(self.values[_from : _from + self.per_page])

    def add_items(self, view: FieldPaginationView):
        view.add_item(self.first_page_button)
        view.add_item(self.previous_page_button)
        view.add_item(self.name_button)
        view.add_item(self.next_page_button)
        view.add_item(self.last_page_button)

    def update_buttons(self):
        self.previous_page_button.label = f"{self.page_number} {PREVIOUS_PAGE_SYMBOL}"
        name = self.name.split(" ")
        self.name_button.label = f'{name if len(name) == 1 else f"{name[0]}..."} [{self.page_number + 1}/{self.max_pages}]'
        self.next_page_button.label = f"{NEXT_PAGE_SYMBOL} {self.page_number + 2}"

        self.next_page_button.disabled = False
        self.previous_page_button.disabled = False

        if (self.page_number + 1) >= self.max_pages:
            self.next_page_button.disabled = True
            self.next_page_button.label = NEXT_PAGE_SYMBOL
            self.last_page_button.disabled = True
            self.last_page_button.label = LAST_PAGE_SYMBOL
        else:
            self.last_page_button.disabled = False
            self.last_page_button.label = f"{LAST_PAGE_SYMBOL} {self.max_pages}"

        if self.page_number == 0:
            self.previous_page_button.disabled = True
            self.previous_page_button.label = PREVIOUS_PAGE_SYMBOL
            self.first_page_button.disabled = True
            self.first_page_button.label = FIRST_PAGE_SYMBOL
        else:
            self.first_page_button.disabled = False
            self.first_page_button.label = f"1 {FIRST_PAGE_SYMBOL}"



class FieldNavButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.view: FieldPaginationView

    async def callback(self, interaction: discord.Interaction):
        self.use()
        await self.view.update_msg(interaction)


class FirstPageButton(FieldNavButton):
    def __init__(self, field: Field):
        super().__init__(label=FIRST_PAGE_SYMBOL, style=discord.ButtonStyle.grey)
        self.field = field

    def use(self):
        self.field.page_number = 0


class PreviousPageButton(FieldNavButton):
    def __init__(self, field: Field):
        super().__init__(label=PREVIOUS_PAGE_SYMBOL, style=discord.ButtonStyle.grey)
        self.field = field

    def use(self):
        if self.field.page_number != 0:
            self.field.page_number -= 1


class FieldNameButton(FieldNavButton):
    def __init__(self, field: Field):
        super().__init__(
            label=field.name, style=discord.ButtonStyle.blurple, disabled=True
        )
        self.field = field

    def use(self):
        if self.field.page_number != 0:
            self.field.page_number -= 1


class NextPageButton(FieldNavButton):
    def __init__(self, field: Field):
        super().__init__(label=NEXT_PAGE_SYMBOL, style=discord.ButtonStyle.grey)
        self.field = field

    def use(self):
        if self.field.page_number != self.field.max_pages:
            self.field.page_number += 1


class LastPageButton(FieldNavButton):
    def __init__(self, field: Field):
        super().__init__(label=LAST_PAGE_SYMBOL, style=discord.ButtonStyle.grey)
        self.field = field

    def use(self):
        self.field.page_number = self.field.max_pages - 1


class FieldPaginationView(discord.ui.View):
    def __init__(
        self, ctx: CustomContext, original_embed: Bot.Embed, *, fields: List[Field]
    ):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.bot = ctx.bot
        self.original_embed = original_embed
        self.fields = fields

        if len([f for f in fields if f.is_paginating()]) > 5:
            raise ValueError("Too many paginating fields")

        self.clear_items()
        self.fill_items()

    async def update_msg(self, interaction: discord.Interaction):
        for field in self.fields:
            field.update_buttons()
        await interaction.response.edit_message(view=self, embed=self.embed)

    def fill_items(self, view: Optional[discord.ui.View] = None):
        view = view or self
        for field in self.fields:
            if field.is_paginating():
                field.update_buttons()
                field.add_items(view)

    @property
    def embed(self):
        embed = self.original_embed.copy()
        for field in self.fields:
            embed.add_field(name=field.name, value=field.value)
        return embed

    async def on_timeout(self):
        await self.msg.edit(view=None)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you!",
                ephemeral=True,
            )
            return False
        return True
