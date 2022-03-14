import aiohttp
import mystbin
import json
import os
import typing

from typing import Optional, Type
from types import TracebackType

PASTE_URL = "https://www.toptal.com/developers/hastebin/documents"


class MystbinClient(mystbin.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __aenter__(self) -> mystbin.Client:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()


async def paste_to_bin(paste_content: str, syntax: str = "txt") -> str:
    async with MystbinClient() as mystbin_client:
        content = await mystbin_client.post(paste_content, syntax=syntax)
        return content.url
