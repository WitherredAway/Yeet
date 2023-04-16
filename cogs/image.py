from __future__ import annotations
from enum import Enum
import re

import typing
import io
from typing import Optional

import discord
from discord.ext import commands
from cogs.utils.utils import resize
from helpers.constants import NL

from helpers.context import CustomContext

if typing.TYPE_CHECKING:
    from main import Bot


RESIZE_LIMIT = 3840
ASPECT_RATIO_ORIGINAL = ('retain', 'keep', 'same', 'original', 'og')


class FlagDescriptions(Enum):
    height = "Height flag to specify height when resizing."
    width = "Width flag to specify width when resizing."
    aspect_ratio = f"Aspect Ratio flag to specify width:height aspect ratio when resizing. \
        Pass in either of`{', '.join(ASPECT_RATIO_ORIGINAL)}` to retain the original aspect ratio of file(s)."

class ResizeFlags(commands.FlagConverter, prefix='--', delimiter=' ', case_insensitive=True):
    height: Optional[int] = commands.flag(aliases=("h",), max_args=1, description=FlagDescriptions.height.value)
    width: Optional[int] = commands.flag(aliases=("w",), max_args=1, description=FlagDescriptions.width.value)
    ar: Optional[str] = commands.flag(
        name="aspect_ratio",
        aliases=("ar",),
        max_args=1,
        description=FlagDescriptions.aspect_ratio.value
    )


class Image(commands.Cog):
    """Cog for image processing commands"""

    def __init__(self, bot: Bot):
        self.bot = bot

    display_emoji = "🖼️"

    @commands.command(
        name="resize",
        brief="Resize image(s) to any size with minimum quality loss.",
        help=f"""**Attach files to resize them to specified height and/or width or aspect ratio.**
The way height, width or aspect ratio parameters are passed is through flags.

**Flags**
`--height <number>` - {FlagDescriptions.height.value}
`--width <number>` - {FlagDescriptions.width.value}
`--aspect_ratio <width>:<height>` - {FlagDescriptions.aspect_ratio.value} If either height/width flag is passed, it will resized based on it, but will not work if both are passed. If neither is specified, it will use the original width.

**Examples**
- `resize --height 400 --width 600`
- `resize --h 400 --w 600`
- `resize --aspect_ratio 16:9` Resizes based on original width. If original width is 1600, will change height to 900
- `resize --h 900 --ar 16:9` Resizes to height 900 and width 1600 (16/9 * 900)
- `resize --w 1600 --ar 16:9` Resizes to width 1600 and height 900 (9/16 * 1600)
- `resize --h 3000 --ar original` Resizes to height 3000 and width proportional to height based on original AR of file(s)

If either height or width is not passed, it will keep the original for each attachment respectively.""",
        description="Resize image(s) to custom height/width while retaining maximum quality."
    )
    async def _resize(self, ctx: CustomContext, *, flags: ResizeFlags):
        await ctx.typing()
        if len(ctx.message.attachments) == 0:
            return await ctx.send_help(ctx.command)

        height = flags.height
        width = flags.width
        ar = flags.ar
        if all((height is None, width is None, ar is None)):
            await ctx.reply("Please provide atleast one flag!")
            return await ctx.send_help(ctx.command)
        if any((height == 0, width == 0)):
            return await ctx.reply("Height or width cannot be zero!")

        if ar is not None:
            if all((height is not None, width is not None)):
                await ctx.reply("The aspect_ratio flag cannot work with both height and width!")
                return await ctx.send_help(ctx.command)

            if ar.casefold() in ASPECT_RATIO_ORIGINAL:
                ar_multiplier = None
            else:
                ar_match = re.match("(?P<width>\d+):(?P<height>\d+)", ar)
                if ar_match is None:
                    return await ctx.reply("Invalid aspect ratio provided, please make sure it follows the format `width:height`, e.g. 16:9")

                ar_height = int(ar_match.group('height'))
                ar_width = int(ar_match.group('width'))
                if any((ar_height == 0, ar_width == 0)):
                    return await ctx.reply("Height or width of the aspect_ratio flag cannot be zero!")

                ar_multiplier = ar_width / ar_height

        files = []
        files_result = []
        for attachment in ctx.message.attachments:
            if not attachment.content_type.startswith('image'):
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
                files_result.append(f"`{attachment.filename}`: The height cannot be larger than {RESIZE_LIMIT}!")
                continue
            elif _width > RESIZE_LIMIT:
                files_result.append(f"`{attachment.filename}`: The width cannot be larger than {RESIZE_LIMIT}!")
                continue

            file = io.BytesIO(await attachment.read())
            resized = io.BytesIO(resize(file, height=_height, width=_width))
            filename = f"{attachment.filename.split('.')[0]}.png"
            files.append(discord.File(resized, filename=filename))
            files_result.append(f"`{attachment.filename}`: **{attachment.height}**x**{attachment.width}** -> **{_height}**x**{_width}**")

        flags_result = []
        l = len(files)
        if l > 0:
            flags_result.append(f"Resized {l} image{'' if l == 1 else 's'} to:")
            if flags.height:
                flags_result.append(f"`height = {flags.height}`")
            if flags.width:
                flags_result.append(f"`width = {flags.width}`")
            if flags.ar:
                flags_result.append(f"`aspect ratio = {'original' if flags.ar in ASPECT_RATIO_ORIGINAL else flags.ar}`")
                if flags.height:
                    flags_result.append(f"`width = {_width}`")
                elif flags.width:
                    flags_result.append(f"`height = {_height}`")

        await ctx.reply(f"{NL.join(flags_result)}\n\n{NL.join(files_result)}", files=files)


async def setup(bot):
    await bot.add_cog(Image(bot))
