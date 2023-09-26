from enum import Enum
from typing import Optional, Self

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
        aliases=("image", "img"), max_args=1, description=ResizeFlagDescriptions.url.value
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
    async def convert(cls, ctx: CustomContext, argument: str) -> Self:
        """|coro|

        The method that actually converters an argument to the flag mapping.

        Parameters
        ----------
        ctx: :class:`Context`
            The invocation context.
        argument: :class:`str`
            The argument to convert from.

        Raises
        --------
        FlagError
            A flag related parsing error.

        Returns
        --------
        :class:`FlagConverter`
            The flag converter instance with all flags parsed.
        """
        argument = argument.replace("—", "--")

        # Only respect ignore_extra if the parameter is a keyword-only parameter
        ignore_extra = True
        if (
            ctx.command is not None
            and ctx.current_parameter is not None
            and ctx.current_parameter.kind == ctx.current_parameter.KEYWORD_ONLY
        ):
            ignore_extra = ctx.command.ignore_extra

        arguments = cls.parse_flags(argument, ignore_extra=ignore_extra)
        flags = cls.__commands_flags__

        self = cls.__new__(cls)
        for name, flag in flags.items():
            try:
                values = arguments[name]
            except KeyError:
                if flag.required:
                    raise MissingRequiredFlag(flag)
                else:
                    if callable(flag.default):
                        # Type checker does not understand flag.default is a Callable
                        default = await maybe_coroutine(flag.default, ctx)
                        setattr(self, flag.attribute, default)
                    else:
                        setattr(self, flag.attribute, flag.default)
                    continue

            if flag.max_args > 0 and len(values) > flag.max_args:
                if flag.override:
                    values = values[-flag.max_args :]
                else:
                    raise TooManyFlags(flag, values)

            # Special case:
            if flag.max_args == 1:
                value = await convert_flag(ctx, values[0], flag)
                setattr(self, flag.attribute, value)
                continue

            # Another special case, tuple parsing.
            # Tuple parsing is basically converting arguments within the flag
            # So, given flag: hello 20 as the input and Tuple[str, int] as the type hint
            # We would receive ('hello', 20) as the resulting value
            # This uses the same whitespace and quoting rules as regular parameters.
            values = [await convert_flag(ctx, value, flag) for value in values]

            if flag.cast_to_dict:
                values = dict(values)

            setattr(self, flag.attribute, values)

        return self
