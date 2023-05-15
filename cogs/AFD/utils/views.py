from __future__ import annotations

import datetime
import typing
from typing import Optional

import discord

from .urls import SUBMISSION_URL
from .utils import EmbedColours, Row
from ...utils.utils import SimpleModal
from helpers.constants import NL
from helpers.context import CustomContext
from .labels import (
    CMT_LABEL,
    COMMENT_BTN_LABEL,
    SUBMIT_BTN_LABEL,
    TOPIC_LABEL,
    RULES_LABEL,
    DEADLINE_LABEL,
    CLAIM_MAX_LABEL,
    UNAPP_MAX_LABEL,
)

if typing.TYPE_CHECKING:
    from ..afd import Afd, AfdSheet
    from main import Bot


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
                custom_id="topic",
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=RULES_LABEL,
                default=self.sheet.RULES,
                style=discord.TextStyle.long,
                custom_id="rules",
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=DEADLINE_LABEL,
                default=self.sheet.DEADLINE,
                placeholder="dd/MM/YYYY HH:mm",
                style=discord.TextStyle.short,
                custom_id="deadline",
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=CLAIM_MAX_LABEL,
                default=self.sheet.CLAIM_MAX,
                style=discord.TextStyle.short,
                custom_id="claim_max",
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=UNAPP_MAX_LABEL,
                default=self.sheet.UNAPP_MAX,
                style=discord.TextStyle.short,
                custom_id="unapp_max",
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

        self.df.loc["1", TOPIC_LABEL] = topic
        self.df.loc["1", RULES_LABEL] = rules
        resp = []
        try:
            datetime.datetime.strptime(deadline.value, "%d/%m/%Y %H:%M")
        except ValueError:
            resp.append(
                "- Invalid deadline format. Expected format: `dd/MM/YYYY HH:mm`"
            )
        else:
            self.df.loc["1", DEADLINE_LABEL] = deadline.value

        if claim_max.value.isdigit():
            self.df.loc["1", CLAIM_MAX_LABEL] = claim_max.value
        else:
            resp.append("- Invalid claim max: Expected a number")

        if unapp_max.value.isdigit():
            self.df.loc["1", UNAPP_MAX_LABEL] = unapp_max.value
        else:
            resp.append("- Invalid unapproved max: Expected a number")

        await self.sheet.update_row(1, from_col="I", to_col="N")
        await interaction.followup.send(
            f"Successfully updated information{(' except:' + NL + NL.join(resp)) if resp else '!'}",
            ephemeral=True,
        )


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
    async def edit_fields(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await self.sheet.update_df()
        modal = EditModal(self.sheet)
        await interaction.response.send_modal(modal)
        await modal.wait()

        await self.msg.edit(embed=self.afdcog.embed, view=self)


class SubmitView(discord.ui.View):
    def __init__(self, afdcog: Afd, *, row: Row, ctx: CustomContext):
        super().__init__(timeout=300)
        self.afdcog = afdcog
        self.row = row
        self.ctx = ctx

        self.update_buttons()

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

    async def _stop(self):
        await self.msg.delete()
        self.stop()

    def update_buttons(self):
        self.clear_items()
        self.add_item(
            discord.ui.Button(
                label="Upload",
                url=SUBMISSION_URL,
            )
        )
        self.submit_btn.label = SUBMIT_BTN_LABEL if not self.row.image else "Resubmit"
        self.add_item(self.submit_btn)
        if self.row.image:
            self.add_item(self.unsubmit_btn)

    @discord.ui.button(label=SUBMIT_BTN_LABEL, style=discord.ButtonStyle.green, row=1)
    async def submit_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        url_label = "Drawing URL"
        modal = SimpleModal(
            title=f"Submit drawing for {self.row.pokemon}",
            inputs=[
                discord.ui.TextInput(
                    label=url_label,
                    style=discord.TextStyle.short,
                    placeholder=SUBMISSION_URL,
                    required=True,
                )
            ],
        )
        await interaction.response.send_modal(modal)
        _t = await modal.wait()
        if _t is not True:
            await self.afdcog.submit(
                self.ctx, self.row.pokemon, image_url=modal.label_dict[url_label].value
            )
            await self._stop()

    @discord.ui.button(label="Unsubmit", style=discord.ButtonStyle.red, row=1)
    async def unsubmit_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.afdcog.unsubmit(self.ctx, self.row.pokemon)
        await self._stop()


class PokemonView(discord.ui.View):
    def __init__(
        self,
        ctx: CustomContext,
        row: Row,
        *,
        afdcog: Afd,
        user: Optional[discord.User] = None,
        approved_by: Optional[discord.User] = None,
    ):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.row = row
        self.pokemon = self.row.pokemon
        self.afdcog = afdcog
        self.sheet = self.afdcog.sheet
        self.user = user
        self.approved_by = approved_by

        self.msg: discord.Message

    async def on_timeout(self):
        self.clear_items()
        await self.msg.edit(embed=self.embed, view=self)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"You can't use this!",
                ephemeral=True,
            )
            return False
        return True

    @property
    def embed(self) -> Bot.Embed:
        ctx = self.ctx
        row = self.row
        pokemon = self.pokemon
        base_image = self.sheet.get_pokemon_image(pokemon)

        embed = ctx.bot.Embed(title=f"#{row.dex} - {pokemon}")
        embed.set_thumbnail(url=base_image)
        self.update(embed)
        return embed

    def update(self, embed: Bot.Embed):
        """Method responsible for setting things based on status such as Status footer, Embed colour, Fields and Buttons"""
        self.clear_items()

        row = self.row
        color = self.ctx.bot.Embed.COLOUR
        if row.claimed:
            embed.set_author(
                name=f"{row.username} ({row.user_id})", icon_url=self.user.avatar.url
            )

            status = "Claimed."
            color = EmbedColours.CLAIMED.value
            if row.user_id == self.ctx.author.id:
                self.add_item(self.unclaim_btn)  # Add unclaim button if claimed by self

            if row.user_id == self.ctx.author.id:
                self.submit_btn.label = (
                    SUBMIT_BTN_LABEL if not row.image else "Edit submission"
                )
                self.add_item(self.submit_btn)  # Add submit button if claimed by self

            if row.image:
                embed.set_image(url=row.image)
                if row.completed:
                    status = f"Complete! Approved by {self.approved_by}."
                    color = EmbedColours.COMPLETED.value
                    if self.afdcog.is_admin(self.ctx.author):
                        self.add_item(
                            self.unapprove_btn
                        )  # Add unapprove button if completed
                else:
                    if self.afdcog.is_admin(self.ctx.author):
                        self.add_item(
                            self.approve_btn
                        )  # Add approve button if not completed
                self.comment_btn.label = (
                    COMMENT_BTN_LABEL if not row.correction_pending else "Edit comment"
                )
                self.add_item(self.comment_btn)  # Add comment button if image exists

                if row.correction_pending:
                    status = "Correction pending."
                    color = EmbedColours.CORRECTION.value
                    embed.add_field(
                        name=f"{CMT_LABEL} by {self.approved_by}",
                        value=str(row.comment),
                        inline=False,
                    )
                elif row.unreviewed:
                    status = "Submitted, Awaiting review."
                    color = EmbedColours.UNREVIEWED.value

            if (not row.image) or (row.correction_pending):
                if self.afdcog.is_admin(self.ctx.author):
                    self.add_item(
                        self.remind_btn
                    )  # Add remind button if not submitted or correction pending

            embed.set_footer(
                text=f"{status}",
            )
        else:
            status = "Not claimed."
            color = EmbedColours.UNCLAIMED.value
            embed.set_footer(text=status)
            self.add_item(self.claim_btn)  # Add claim button if not claimed

        embed.color = color

    async def update_msg(self):
        await self.sheet.update_df()
        self.row = self.sheet.get_pokemon_row(self.pokemon)
        self.user = (
            (await self.afdcog.fetch_user(self.row.user_id))
            if self.row.claimed
            else None
        )
        await self.msg.edit(embed=self.embed, view=self)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, row=0)
    async def claim_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        if (await self.afdcog.claim(self.ctx, self.pokemon)) is True:
            await self.update_msg()

    @discord.ui.button(label="Unclaim", style=discord.ButtonStyle.red, row=0)
    async def unclaim_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        if (await self.afdcog.unclaim(self.ctx, self.pokemon)) is True:
            await self.update_msg()

    @discord.ui.button(label=SUBMIT_BTN_LABEL, style=discord.ButtonStyle.blurple, row=0)
    async def submit_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = self.ctx.bot.Embed(
            title=f"Submit drawing for {self.pokemon}",
            description=f"""**Steps to submit a drawing**:
- Upload it to the website ({SUBMISSION_URL}) using the Upload button below. You will be given a URL to the uploaded image.
- Use the green submit button below and paste in the URL to submit it!
    - You can edit/delete a submission later!""",
        )
        embed.set_footer(
            text="The upload website is an official Pokétwo website made by Oliver!"
        )
        view = SubmitView(self.afdcog, row=self.row, ctx=self.ctx)
        await interaction.response.send_message(embed=embed, view=view)
        view.msg = await interaction.original_message()
        _t = await view.wait()
        if _t is not True:
            await self.update_msg()

    @discord.ui.button(label="Remind", style=discord.ButtonStyle.blurple, row=1)
    async def remind_btn(
        self, interaction: discord.Interaction, button: discord.Buttons
    ):
        await self.afdcog.send_notification(
            embed=self.afdcog.pkm_remind_embed(self.row), user=self.user, ctx=self.ctx
        )
        await interaction.response.send_message(
            f"Successfully sent a reminder to **{self.user}**.", ephemeral=True
        )

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, row=1)
    async def approve_btn(
        self, interaction: discord.Interaction, button: discord.Buttons
    ):
        await interaction.response.defer()
        if (await self.afdcog.approve(self.ctx, self.pokemon)) is True:
            await self.update_msg()

    @discord.ui.button(label="Unapprove", style=discord.ButtonStyle.red, row=1)
    async def unapprove_btn(
        self, interaction: discord.Interaction, button: discord.Buttons
    ):
        await interaction.response.defer()
        if (await self.afdcog.unapprove(self.ctx, self.pokemon)) is True:
            await self.update_msg()

    @discord.ui.button(label="Comment", style=discord.ButtonStyle.blurple, row=1)
    async def comment_btn(
        self, interaction: discord.Interaction, button: discord.Buttons
    ):
        input_label = "Comment"
        modal = SimpleModal(
            title=f"Comment on {self.pokemon}",
            inputs=[
                discord.ui.TextInput(
                    label=input_label,
                    style=discord.TextStyle.short,
                    required=False,
                    max_length=2000,
                    placeholder="Leave empty to clear any comment",
                    default=self.row.comment,
                )
            ],
        )
        await interaction.response.send_modal(modal)
        await modal.wait()

        comment = modal.label_dict[input_label].value
        if (await self.afdcog.comment(self.ctx, self.pokemon, comment)) is True:
            await self.update_msg()

