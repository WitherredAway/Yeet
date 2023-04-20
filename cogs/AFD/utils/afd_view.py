from __future__ import annotations
import datetime

import typing
import pandas as pd

import discord
from helpers.constants import NL

from helpers.context import CustomContext

from .labels import (
    TOPIC_LABEL,
    RULES_LABEL,
    DEADLINE_LABEL,
    CLAIM_MAX_LABEL,
    UNAPP_MAX_LABEL
)

if typing.TYPE_CHECKING:
    from ..afd import Afd, AfdSheet


class EditModal(discord.ui.Modal):
    def __init__(self, sheet: AfdSheet) -> None:
        super().__init__(title="Edit AFD information", timeout=180)
        self.sheet = sheet
        self.df = self.sheet.df

        self.add_item(
            discord.ui.TextInput(
                label=TOPIC_LABEL,
                default=self.sheet.TOPIC,
                style=discord.TextStyle.short,
                custom_id="topic"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=RULES_LABEL,
                default=self.sheet.RULES,
                style=discord.TextStyle.long,
                custom_id="rules"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=DEADLINE_LABEL,
                default=self.sheet.DEADLINE,
                placeholder="dd/MM/YYYY HH:mm",
                style=discord.TextStyle.short,
                custom_id="deadline"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=CLAIM_MAX_LABEL,
                default=self.sheet.CLAIM_MAX,
                style=discord.TextStyle.short,
                custom_id="claim_max"
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=UNAPP_MAX_LABEL,
                default=self.sheet.UNAPP_MAX,
                style=discord.TextStyle.short,
                custom_id="unapp_max"
            )
        )

    def children_dict(self) -> typing.Dict[str, discord.ui.TextInput]:
        ch_dict = {child.custom_id: child for child in self.children}
        return ch_dict

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        children = self.children_dict()

        topic = children["topic"].value
        rules = children["rules"].value
        deadline = children["deadline"]
        claim_max = children["claim_max"]
        unapp_max = children["unapp_max"]

        self.df.loc['1', TOPIC_LABEL] = topic
        self.df.loc['1', RULES_LABEL] = rules
        resp = []
        try:
            datetime.datetime.strptime(deadline.value, "%d/%m/%Y %H:%M")
        except ValueError:
            resp.append("- Invalid deadline format. Expected format: `dd/MM/YYYY HH:mm`")
        else:
            self.df.loc['1', DEADLINE_LABEL] = deadline.value

        if claim_max.value.isdigit():
            self.df.loc['1', CLAIM_MAX_LABEL] = claim_max.value
        else:
            resp.append("- Invalid claim max: Expected a number")

        if unapp_max.value.isdigit():
            self.df.loc['1', UNAPP_MAX_LABEL] = unapp_max.value
        else:
            resp.append("- Invalid unapproved max: Expected a number")

        await self.sheet.update_row(1, from_col='I', to_col='N')
        await interaction.followup.send(f"Successfully updated information{(' except:' + NL + NL.join(resp)) if resp else '!'}", ephemeral=True)


class AfdView(discord.ui.View):
    def __init__(self, afdcog: Afd, *, ctx: CustomContext):
        super().__init__(timeout=300)
        self.afdcog = afdcog
        self.ctx = ctx
        self.sheet = afdcog.sheet
        self.df = afdcog.df

        self.msg: discord.Message

        url_dict = {
            "AFD Gist": (afdcog.afd_gist.url, 0),
            "AFD Credits": (afdcog.credits_gist.url, 0),
            "Spreadsheet": (afdcog.sheet.url, 0),
        }
        for label, (url, row) in url_dict.items():
            self.add_item(discord.ui.Button(label=label, url=url, row=row))

        self.remove_item(self.edit_fields)
        if afdcog.is_admin(self.ctx.author):
            self.add_item(self.edit_fields)

    async def on_timeout(self):
        self.remove_item(self.edit_fields)
        await self.msg.edit(embed=self.msg.embeds[0], view=self)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"You can't use this!",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Edit info", style=discord.ButtonStyle.blurple)
    async def edit_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.sheet.update_df()
        modal = EditModal(self.sheet)
        await interaction.response.send_modal(modal)
        await modal.wait()

        await self.msg.edit(embed=self.afdcog.embed, view=self)
