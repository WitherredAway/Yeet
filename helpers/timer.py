from datetime import timedelta
import logging
import time
from typing import List, Optional, Self, Tuple

from helpers.utils import comma_join


class Elapsed(timedelta):
    # TODO: Document this

    @property
    def microseconds(self) -> int:
        return super().microseconds - self.milliseconds

    @property
    def milliseconds(self) -> int:
        return super().microseconds / 1000

    @property
    def seconds(self) -> float:
        return super().seconds + (super().microseconds / 1000000)

    @property
    def minutes(self) -> int:
        return int(self.seconds / 60)

    @property
    def hours(self) -> int:
        return int(self.minutes / 60)

    @property
    def weeks(self) -> int:
        return int(self.days / 7)

    @property
    def total_microseconds(self) -> float:
        return self.total_seconds * 1000000

    @property
    def total_milliseconds(self) -> float:
        return self.total_seconds * 1000

    @property
    def total_seconds(self) -> float:
        return super().total_seconds()

    @property
    def total_minutes(self) -> float:
        return self.total_seconds / 60

    @property
    def total_hours(self) -> float:
        return self.total_minutes / 60

    @property
    def total_weeks(self) -> float:
        return self.total_days / 7

    DISPLAY_PROPERTIES = {
        "weeks": "w",
        "days": "d",
        "hours": "h",
        "minutes": "m",
        "seconds": "s",
        # "milliseconds": "ms",
        # "microseconds": "μs",
    }

    def _get_attr_values(
        self, *, include_total_seconds: Optional[bool] = False
    ) -> List[Tuple[str, float]]:
        attrs = []

        if include_total_seconds:
            attrs.append(("total_seconds", self.total_seconds))

        for property in self.DISPLAY_PROPERTIES.keys():
            value = getattr(self, property)
            if value != 0:
                attrs.append((property, value))

        return attrs

    def __repr__(self) -> str:
        property_values = self._get_attr_values(include_total_seconds=True)
        attrs = [f"{property}={value}" for property, value in property_values]

        return f"Elapsed({', '.join(attrs)})"

    def __format__(self, __format_spec: str) -> str:
        if "c" in __format_spec:  # Compact
            property_values = self._get_attr_values()
            attrs = []
            for property, value in property_values:
                shortcut = self.DISPLAY_PROPERTIES[property]

                rounded_value = round(value, 2)
                is_integer = divmod(rounded_value, 1)[1] == 0
                value = int(value) if is_integer else rounded_value

                attrs.append(f"{value}{shortcut}")

            return "".join(attrs)

        else:
            property_values = self._get_attr_values()
            attrs = []
            for property, value in property_values:
                plural = value != 1
                if not plural:
                    property = property.removesuffix("s")

                rounded_value = round(value, 2)
                attrs.append(f"{rounded_value} {property}")

            return comma_join(attrs)


class TimerAlreadyStarted(Exception):
    pass


class TimerAlreadyEnded(Exception):
    pass


ANSI_CODES = {
    "green": "\033[32",
    "yellow": "\033[33",
    "blue": "\033[34",
    "white": "\033[0",
    "escape": "\033[0m",
    "bold": "1",
}


class Timer:
    # TODO: Document this
    # TODO: Rename start_time to started_at, end_time to ended_at
    # TODO: Move this to its own module
    def __init__(
        self,
        name: Optional[str] = "default timer",
        *,
        logger: Optional[logging.Logger] = None,
        start_message: Optional[str] = None,
        end_message: Optional[str] = "Timer {name} completed in {end_time}",
        colored_output: Optional[bool] = True,
    ):
        self.name = name
        self.logger = logger
        self.start_message = start_message
        self.end_message = end_message
        self.colored_output = colored_output

        self.start_time: int = None
        self.end_time: int = None

    @property
    def started(self) -> bool:
        return self.start_time is not None

    @property
    def ended(self) -> bool:
        return self.end_time is not None

    @property
    def elapsed(self) -> Elapsed:
        elapsed_seconds = time.time() - self.start_time
        return Elapsed(seconds=elapsed_seconds)

    def color_message(
        self, message: str, color: str, *, bold: Optional[bool] = False
    ) -> str:
        """Returns message colored and/or bolded"""

        escape_code = ANSI_CODES.get("escape")
        code = ANSI_CODES.get(color.lower(), "")

        style_code = ""
        if bold:
            style_code += ANSI_CODES.get("bold")

        if style_code:
            style_code = f";{style_code}"

        code += style_code
        code = f"{code}m"

        return f"{code}{message}{escape_code}"

    def log(self, message: str):
        if self.logger:
            name = self.name

            colored = self.colored_output
            if colored:
                message = self.color_message(message, "green")
                name = self.color_message(self.name, "blue", bold=True)

            format_dict = {"name": name}
            if self.ended:
                end_time = format(self.end_time, "c")
                if colored:
                    end_time = self.color_message(end_time, "yellow", bold=True)
                format_dict["end_time"] = end_time

            self.logger.info(message.format_map(format_dict))

    def start(self) -> Self:
        if self.started:
            raise TimerAlreadyStarted(f"Timer `{self.name}` has already started")

        if self.start_message:
            self.log(self.start_message)

        self.start_time = time.time()

        return self

    def end(self) -> Elapsed:  # TODO: Rename to stop
        if self.ended:
            raise TimerAlreadyEnded(
                f"Timer `{self.name}` has already ended. Use Timer.end_time to see results."
            )

        self.end_time = self.elapsed

        if self.end_message:
            self.log(self.end_message)

        return self.end_time

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.end()
