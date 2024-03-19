from __future__ import annotations

import datetime
import typing
from typing import Optional

import discord

from helpers.constants import EMBED_FIELD_CHAR_LIMIT

from .constants import DATETIME_FMT, FIRST_ROW_IDX

from .urls import SUBMISSION_URL
from .utils import EmbedColours, Row
from ...utils.utils import SimpleModal, url_to_image
from helpers.context import CustomContext
from .labels import (
    COMMENT_LABEL,
    COMMENT_BTN_LABEL,
    SUBMIT_BTN_LABEL,
    THEME_LABEL,
    RULES_LABEL,
    DEADLINE_LABEL,
    CLAIM_MAX_LABEL,
    UNAPP_MAX_LABEL,
)

if typing.TYPE_CHECKING:
    from ..afd import Afd, AfdSheet
    from main import Bot


class EditModal(discord.ui.Modal):
    def __init__(self, afdcog: Afd) -> None:
        super().__init__(title="Edit AFD information", timeout=180)
        self.afdcog = afdcog
        self.sheet = afdcog.sheet
        self.df = self.sheet.df
        self.edited = None

        self.add_item(
            discord.ui.TextInput(
                label=THEME_LABEL,
                default=self.sheet.THEME,
                style=discord.TextStyle.short,
                custom_id="theme",
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=RULES_LABEL,
                default=self.sheet.RULES,
                placeholder="The names within curly braces are variables",
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
                default=str(self.sheet.CLAIM_MAX),
                style=discord.TextStyle.short,
                custom_id="claim_max",
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label=UNAPP_MAX_LABEL,
                default=str(self.sheet.UNAPP_MAX),
                style=discord.TextStyle.short,
                custom_id="unapp_max",
            )
        )

    def children_dict(self) -> typing.Dict[str, discord.ui.TextInput]:
        ch_dict = {child.custom_id: child for child in self.children}
        return ch_dict

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.followup.send(error)
        raise error

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        children = self.children_dict()

        theme = children["theme"]
        rules = children["rules"]
        deadline = children["deadline"]
        claim_max = children["claim_max"]
        unapp_max = children["unapp_max"]

        resp = {}

        if theme.value != theme.default:
            self.df.loc[FIRST_ROW_IDX, THEME_LABEL] = theme.value
            resp[THEME_LABEL] = f"Updated from `{theme.default}` to `{theme.value}`"

        if rules.value != rules.default:
            try:
                rules_fmt = rules.value.format(
                    CLAIM_MAX=claim_max.value, UNAPP_MAX=unapp_max.value
                )
            except KeyError as e:
                resp[
                    RULES_LABEL
                ] = f"{e}\nPlease make sure you did not modify any of the variables."
            else:
                if len(rules.value) > EMBED_FIELD_CHAR_LIMIT:
                    resp[
                        RULES_LABEL
                    ] = f"Can't be longer than 1024 characters. Let Witherr know if you want to increase this limit."
                else:
                    self.df.loc[FIRST_ROW_IDX, RULES_LABEL] = rules.value
                    resp[RULES_LABEL] = f"Updated to:\n```\n{rules_fmt}\n```"

        try:
            datetime.datetime.strptime(deadline.value, DATETIME_FMT)
        except ValueError:
            resp[
                DEADLINE_LABEL
            ] = f"{deadline.value} is not a valid format. Expected format: `dd/MM/YYYY HH:mm`"
        else:
            if deadline.value != deadline.default:
                from_ts = self.sheet.DEADLINE_TS
                self.df.loc[FIRST_ROW_IDX, DEADLINE_LABEL] = deadline.value
                resp[
                    DEADLINE_LABEL
                ] = f"Updated from `{from_ts}` to {self.sheet.DEADLINE_TS}"

        if claim_max.value.isdigit():
            if claim_max.value != claim_max.default:
                self.df.loc[FIRST_ROW_IDX, CLAIM_MAX_LABEL] = claim_max.value
                resp[
                    CLAIM_MAX_LABEL
                ] = f"Updated from `{claim_max.default}` to `{claim_max.value}`"
        else:
            resp[CLAIM_MAX_LABEL] = f"{claim_max.value} is not a valid number"

        if unapp_max.value.isdigit():
            if unapp_max.value != unapp_max.default:
                self.df.loc[FIRST_ROW_IDX, UNAPP_MAX_LABEL] = unapp_max.value
                resp[
                    UNAPP_MAX_LABEL
                ] = f"Updated from `{unapp_max.default}` to `{unapp_max.value}`"
        else:
            resp[UNAPP_MAX_LABEL] = f"{unapp_max.value} is not a valid number"

        await self.sheet.update_row(
            FIRST_ROW_IDX, from_col=THEME_LABEL, to_col=UNAPP_MAX_LABEL
        )

        if len(resp) != 0:
            embed = self.afdcog.bot.Embed(
                title="The following AFD information field(s) have been updated!"
            )
            for label, msg in resp.items():
                embed.add_field(name=label, value=msg)

            await interaction.followup.send(embed=embed)
            await self.afdcog.log_channel.send(embed=embed)  # TODO ping AFD role
            self.edited = True
        else:
            await interaction.followup.send("No changes.")
            self.edited = False


class AfdView(discord.ui.View):
    def __init__(self, afdcog: Afd, *, ctx: CustomContext):
        super().__init__(timeout=300)
        self.afdcog = afdcog
        self.ctx = ctx
        self.sheet = afdcog.sheet
        self.df = afdcog.df

        self.message: discord.Message

        url_dict = {
            # "AFD Credits": (afdcog.credits_gist.url, 0),
            "Spreadsheet": (afdcog.sheet.url, 0),
        }
        for label, (url, row) in url_dict.items():
            self.add_item(discord.ui.Button(label=label, url=url, row=row))

        self.remove_item(self.edit_fields)
        if afdcog.is_admin(self.ctx.author):
            self.add_item(self.edit_fields)

    async def on_timeout(self):
        self.remove_item(self.edit_fields)
        await self.message.edit(embed=self.message.embeds[0], view=self)
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
        modal = EditModal(self.afdcog)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.edited:
            await self.message.edit(embed=self.afdcog.embed, view=self)


class SubmitView(discord.ui.View):
    def __init__(self, afdcog: Afd, *, row: Row, ctx: CustomContext):
        super().__init__(timeout=300)
        self.afdcog = afdcog
        self.row = row
        self.ctx = ctx

        self.update_buttons()

    async def on_timeout(self):
        await self._stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"This instance does not belong to you!",
                ephemeral=True,
            )
            return False
        return True

    async def _stop(self):
        await self.message.edit(view=None)
        self.stop()

    def update_buttons(self):
        self.clear_items()
        # self.add_item(
        #     discord.ui.Button(
        #         label="Upload",
        #         url=SUBMISSION_URL,
        #     )
        # )
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

    @discord.ui.button(label="Unsubmit", style=discord.ButtonStyle.red, row=1)
    async def unsubmit_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await self.afdcog.unsubmit(self.ctx, self.row.pokemon)


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

        self.image_info = None
        self.message: discord.Message

    async def on_timeout(self):
        await self.message.edit(embed=self.embed, view=None)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                f"You can't use this!",
                ephemeral=True,
            )
            return False
        return True

    async def set_image_info(self):
        if self.row.image:
            try:
                image = await url_to_image(self.row.image, self.ctx.bot.session)
            except ValueError:
                return
            t = sum(1 for r, g, b, a in list(image.getdata()) if a == 0)
            total = image.height * image.width
            transparent = round((t / total) * 100, 2)

            self.image_info = {
                "height": image.height,
                "width": image.width,
                "transparent": transparent,
            }

    @property
    def embed(self) -> Bot.Embed:
        ctx = self.ctx
        row = self.row
        pokemon = self.pokemon
        base_image = self.sheet.get_pokemon_image(pokemon)

        embed = ctx.bot.Embed(title=f"#{row.dex + 1} - {pokemon}")
        embed.set_thumbnail(url=base_image)
        self.update(embed)
        return embed

    def update(self, embed: Bot.Embed):
        """Method responsible for setting things based on status such as Status footer, Embed colour, Fields and Buttons"""
        self.clear_items()

        row = self.row
        color = self.ctx.bot.Embed.COLOUR
        is_admin = self.afdcog.is_admin(self.ctx.author)
        if row.claimed:
            embed.set_author(
                name=f"{self.user} ({self.user.id})",
                icon_url=self.user.display_avatar.url,
            )

            status = "Claimed."
            color = EmbedColours.INCOMPLETE.value
            if row.user_id == self.ctx.author.id:
                self.add_item(self.unclaim_btn)  # Add unclaim button if claimed by self

            if row.user_id == self.ctx.author.id:
                self.submit_btn.label = (
                    SUBMIT_BTN_LABEL if not row.image else "Edit submission"
                )
                self.add_item(self.submit_btn)  # Add submit button if claimed by self

            if row.image:
                embed.set_image(url=row.image)
                if row.approved:
                    status = f"Complete! Approved by {row.approved_by}."
                    color = EmbedColours.APPROVED.value
                    if is_admin:
                        self.add_item(
                            self.unapprove_btn
                        )  # Add unapprove button if completed
                else:
                    if is_admin:
                        self.add_item(
                            self.approve_btn
                        )  # Add approve button if not completed
                self.comment_btn.label = (
                    COMMENT_BTN_LABEL if not row.correction_pending else "Edit comment"
                )
                if is_admin:
                    self.add_item(self.comment_btn)  # Add comment button if image exists

                if row.correction_pending:
                    status = "Correction pending."
                    color = EmbedColours.CORRECTION.value
                    embed.add_field(
                        name=f"{COMMENT_LABEL} by {self.approved_by}",
                        value=str(row.comment),
                        inline=False,
                    )
                elif row.unreviewed:
                    status = "Submitted, Awaiting review."
                    color = EmbedColours.UNREVIEWED.value

                if self.image_info:
                    h = self.image_info["height"]
                    w = self.image_info["width"]
                    t = self.image_info["transparent"]
                    embed.add_field(
                        name="Image info",
                        value=f"height: {h}\nwidth: {w}\ntransparent pixels: {t}%",
                    )

            if (not row.image) or (row.correction_pending):
                if is_admin:
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

        if is_admin:
            self.add_item(
                discord.ui.Button(
                    label="Jump To Spreadsheet",
                    url=self.sheet.get_pokemon_loc(row.dex),
                    row=2,
                )
            )  # Add jump to spreadsheet button if admin

        embed.color = color

    async def update_msg(self):
        await self.sheet.update_df()
        self.row = self.sheet.get_pokemon_row(self.pokemon)
        self.user = (
            (await self.afdcog.fetch_user(self.row.user_id))
            if self.row.claimed
            else None
        )
        await self.set_image_info()
        await self.message.edit(embed=self.embed, view=self)

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
        #! TEMPORARY
        embed = self.ctx.bot.Embed(
            title=f"Submit drawing for {self.pokemon}",
            description=f"""**Steps to submit a drawing**:
1. Submit using the `afd submit` command (`{self.ctx.clean_prefix}help afd submit`)
2. Submit through the submit button below
  - [TEMPORARY] Upload the image to any Discord channel and copy the image url
  - Use the green submit button below and paste the URL in the modal to submit it!
    - You can edit/delete a submission later!""",
        )
        embed.set_footer(
            text="We are TEMPORARILY using discord for the images. Please save your drawings somewhere safe for when we find a permanent solution."
        )
        view = SubmitView(self.afdcog, row=self.row, ctx=self.ctx)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
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
