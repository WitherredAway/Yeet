from enum import Enum
from typing import Optional

from discord.ext import commands
from discord.utils import maybe_coroutine
from discord.ext.commands import MissingRequiredFlag, TooManyFlags
from discord.ext.commands.flags import convert_flag

from helpers.context import CustomContext

from .utils import ASPECT_RATIO_ORIGINAL


class ResizeFlagDescriptions(Enum):
    url = "Flag to pass in an image url"
    height = "Flag to specify height."
    width = "Flag to specify width."
    aspect_ratio = f"Flag to specify width:height aspect ratio when resizing. \
Pass either of `{', '.join(ASPECT_RATIO_ORIGINAL)}` to retain the original aspect ratio of file(s). \
If either height/width flag is passed, it will resized based on it, but will not work if both are passed. \
If neither is specified, it will use the original width to resize the height."
    fit = f"Flag `(yes/true)` to specify if you want the bot to fit the image to the edges by cropping away transparent surrounding areas."
    center = f"Flag `(yes/true)` to specify if you want to resize image(s)' background while keeping the image centered and unwarped."
    crop = f"Flag `(yes/true)` to specify if you want the bot to crop your image when resizing."


class ResizeFlags(
    commands.FlagConverter, prefix="--", delimiter=" ", case_insensitive=True
):
    url: Optional[str] = commands.flag(
        aliases=("image", "img"),
        max_args=1,
        description=ResizeFlagDescriptions.url.value,
    )
    height: Optional[int] = commands.flag(
        aliases=("h",), max_args=1, description=ResizeFlagDescriptions.height.value
    )
    width: Optional[int] = commands.flag(
        aliases=("w",), max_args=1, description=ResizeFlagDescriptions.width.value
    )
    ar: Optional[str] = commands.flag(
        name="aspect_ratio",
        aliases=("ar",),
        max_args=1,
        description=ResizeFlagDescriptions.aspect_ratio.value,
    )
    fit: Optional[bool] = commands.flag(
        name="fit", max_args=1, description=ResizeFlagDescriptions.fit.value
    )
    center: Optional[bool] = commands.flag(
        name="center",
        aliases=("centre",),
        max_args=1,
        description=ResizeFlagDescriptions.center.value,
    )
    crop: Optional[bool] = commands.flag(
        name="crop", max_args=1, description=ResizeFlagDescriptions.crop.value
    )

    @classmethod
    async def convert(cls, ctx: CustomContext, argument: str):
        argument = argument.replace("—", "--")
        return await super().convert(ctx, argument)
