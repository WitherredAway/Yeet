import aiohttp
import json
import os
import typing


API_DEV_KEY = os.getenv("API_DEV_KEY")
PASTE_URL = "https://pastebin.com/api/api_post.php"


async def paste_to_bin(
    paste_content: str,
    *,
    name: str="Sample name",
    option: str="paste", 
    syntax: str=None,
    expire_date: str="N") -> str:

    data = {
        'api_dev_key': API_DEV_KEY,
        'api_paste_code': paste_content,
        'api_paste_name': name,
        'api_option': option,
        'api_paste_format': syntax,
        'api_paste_expire_date': expire_date
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(PASTE_URL, data=data) as response:
            return response.content