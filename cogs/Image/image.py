from __future__ import annotations
from dataclasses import dataclass
import re

import typing
import io
from typing import Optional

import discord
from discord.ext import commands
from PIL.Image import Image

from cogs.utils.utils import url_to_image

from .utils.utils import center_resize, fit_image, resize
from helpers.constants import NL
from helpers.context import CustomContext
from .utils.constants import RESIZE_LIMIT, ASPECT_RATIO_ORIGINAL
from .utils.flags import ResizeFlagDescriptions, ResizeFlags

if typing.TYPE_CHECKING:
    from main import Bot


@dataclass
class FakeAttachment:
    height: int
    width: int
    content_type: str
    filename: str
    fp: io.BytesIO

    async def read(self):
        return self.fp.read()

    @classmethod
    def from_image(cls, image: Image):
        format = image.format.lower()

        fp = io.BytesIO()
        image.save(fp, "PNG")
        fp.seek(0)

        return cls(
            image.height,
            image.width,
            image.filename or f"image.{format}",
            f"image/{format}",
            fp
        )


class ImageCog(commands.Cog):
    """Cog for image processing commands"""

    def __init__(self, bot: Bot):
        self.bot = bot

    display_emoji = "🖼️"

    @commands.command(
        name="resize",
        aliases=("crop",),
        brief="Resize image(s) to any size with minimum quality loss.",
        help=f"""**Attach files to resize them to specified height and/or width or aspect ratio.**
Specify height, width or aspect ratio parameters using flags.
## **Flags**
- `--url/img <image_url>` - {ResizeFlagDescriptions.url.value}. This is optional, you can just attach images instead.
### Standalone flags
- `--height/h <number>` - {ResizeFlagDescriptions.height.value}
- `--width/w <number>` - {ResizeFlagDescriptions.width.value}
- `--aspect_ratio/ar <width>:<height>` - {ResizeFlagDescriptions.aspect_ratio.value}
- `--fit <yes/true>=false` - {ResizeFlagDescriptions.fit.value}
### Supporting flags
- `--center/centre <yes/true>=false` - {ResizeFlagDescriptions.center.value}
- `--crop <yes/true>=false` - {ResizeFlagDescriptions.crop.value}
## **Examples**
- `resize --h 475 --w 475 --fit yes --center yes` - Resizes to and fits image to a 475x475 canvas without stretching.
- `resize --height 400 --width 600`
- `resize --aspect_ratio 16:9` - Resizes height based on original width. If original width is 1600, will change height to 900
- `resize --h 3000 --ar original` - Resizes to height 3000 and width proportional to height based on original AR of each file
- `resize --fit yes` - Crops away surrounding transparent areas to fit the content fully. Use --crop to crop instead of resizing after fitting.""",
        description="Resize image(s) to custom height/width while retaining maximum quality.",
    )
    async def _resize(self, ctx: CustomContext, *, flags: ResizeFlags):
        await ctx.typing()

        attachments = ctx.message.attachments[:]
        if flags.url:
            image = await url_to_image(flags.url, self.bot.session)
            attachments.append(FakeAttachment.from_image(image))

        if len(attachments) == 0:
            await ctx.reply("Please provide url (--url) or attach at least one image to resize!")
            return await ctx.send_help(ctx.command)

        if len(attachments) > 10:
            return await ctx.reply("Cannot resize more than 10 images at once!")

        height = flags.height
        width = flags.width
        ar = flags.ar
        fit = flags.fit
        center = flags.center
        crop = flags.crop

        if all((height is None, width is None, ar is None, fit is None)):
            await ctx.reply("Please provide atleast one standalone flag!")
            return await ctx.send_help(ctx.command)
        if any((height == 0, width == 0)):
            return await ctx.reply("Height or width cannot be zero!")

        ar_multiplier = None
        if ar is not None:
            if all((height is not None, width is not None)):
                await ctx.reply(
                    "The aspect_ratio flag cannot work with both height and width!"
                )
                return await ctx.send_help(ctx.command)

            if ar.casefold() in ASPECT_RATIO_ORIGINAL:
                ar_multiplier = None
            else:
                ar_match = re.match("(?P<width>\d+):(?P<height>\d+)", ar)
                if ar_match is None:
                    return await ctx.reply(
                        "Invalid aspect ratio provided, please make sure it follows the format `width:height`, e.g. 16:9"
                    )

                ar_height = int(ar_match.group("height"))
                ar_width = int(ar_match.group("width"))
                if any((ar_height == 0, ar_width == 0)):
                    return await ctx.reply(
                        "Height or width of the aspect_ratio flag cannot be zero!"
                    )

                ar_multiplier = ar_width / ar_height

        files = []
        files_result = []
        for attachment in attachments:
            if not attachment.content_type or not attachment.content_type.startswith("image"):
                files_result.append(f"`{attachment.filename}`: Not an image")
                continue

            _height = height
            _width = width
            if ar is not None:
                if ar_multiplier is None:
                    ar_multiplier = attachment.width / attachment.height
                if height is not None:
                    _width = height * ar_multiplier
                elif width is not None:
                    _height = width / ar_multiplier
                else:
                    _width = attachment.width
                    _height = _width / ar_multiplier
            _height = round(_height) if _height is not None else attachment.height
            _width = round(_width) if _width is not None else attachment.width

            if _height > RESIZE_LIMIT:
                files_result.append(
                    f"`{attachment.filename}`: The height cannot be larger than {RESIZE_LIMIT}!"
                )
                continue
            elif _width > RESIZE_LIMIT:
                files_result.append(
                    f"`{attachment.filename}`: The width cannot be larger than {RESIZE_LIMIT}!"
                )
                continue

            h_equal = _height == attachment.height
            w_equal = _width == attachment.width
            if h_equal and w_equal and (fit is not True):
                files_result.append(
                    f"`{attachment.filename}`: The height and width are unchanged."
                )
                continue

            file = io.BytesIO(await attachment.read())
            if fit is True:
                file, fit_size = fit_image(file)
                file = io.BytesIO(file)
                if all((ar is None, crop is True)):
                    if all((height is None, width is None)):
                        _width, _height = fit_size
                    elif height is None:
                        _height = fit_size[-1]
                    elif width is None:
                        _width = fit_size[0]

            if center is True:
                resized, (_width, _height) = center_resize(
                    file, height=_height, width=_width, crop=crop
                )
            else:
                resized, (_width, _height) = resize(
                    file, height=_height, width=_width, crop=crop
                )

            filename = f"{attachment.filename.split('.')[0]}.png"
            files.append(discord.File(io.BytesIO(resized), filename=filename))
            files_result.append(
                f"`{attachment.filename}`: **{attachment.height}**x**{attachment.width}** -> **{_height}**x**{_width}**"
            )

        actions = []
        if fit is True:
            actions.append(f"*`fit`*")
        if center is True:
            actions.append(f"*`center`*")
        if crop is True:
            actions.append(f"*`crop`*")

        flags_result = []
        l = len(files)
        if l > 0:
            flags_result.append(
                f"Performed the following actions on {l} image{'' if l == 1 else 's'}:"
            )
            flags_result.append(", ".join(actions))
            if flags.height:
                flags_result.append(f"`height = {flags.height}`")
            if flags.width:
                flags_result.append(f"`width = {flags.width}`")
            if flags.ar:
                flags_result.append(
                    f"`aspect ratio = {'original' if flags.ar in ASPECT_RATIO_ORIGINAL else flags.ar}`"
                )
                if flags.height:
                    flags_result.append(f"`width = {_width}`")
                elif flags.width:
                    flags_result.append(f"`height = {_height}`")

        await ctx.reply(
            f"{NL.join(flags_result)}\n\n{NL.join(files_result)}", files=files
        )


async def setup(bot):
    await bot.add_cog(ImageCog(bot))
