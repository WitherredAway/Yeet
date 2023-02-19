import re


CHANNEL = "[a-fA-F0-9]{2}"
HEX_REGEX = re.compile(
    rf"\b(?P<red>{CHANNEL})(?P<green>{CHANNEL})(?P<blue>{CHANNEL})(?P<alpha>{CHANNEL})?\b"
)

ZERO_TO_255 = "0*25[0-5]|0*2[0-4][0-9]|0*1[0-9]{2}|0*[1-9][0-9]|0*[0-9]"
RGB_A_REGEX = re.compile(
    rf"\((?P<red>{ZERO_TO_255}) *,? +(?P<green>{ZERO_TO_255}) *,? +(?P<blue>{ZERO_TO_255})(?: *,? +(?P<alpha>{ZERO_TO_255}))?\)"
)

FLAG_EMOJI_REGEX = re.compile("[\U0001F1E6-\U0001F1FF]")

CUSTOM_EMOJI_REGEX = re.compile("<a?:[a-zA-Z0-9_]+:\d+>")
