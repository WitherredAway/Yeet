import io
import os
import re
from typing import Optional, Tuple, Union

import aiohttp


IMGUR_API_URL = "https://api.imgur.com/3"

IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
IMGUR_CLIENT_SECRET = os.getenv("IMGUR_CLIENT_SECRET")


class ImgurImage:
    def __init__(self, response: dict, *, content: io.BytesIO) -> None:
        for key, val in response.items():
            setattr(self, key, val)
        self.content = content


class Response:
    def __init__(self, response: dict) -> None:
        for key, val in response.items():
            setattr(self, key, val)


imgur_url_regex = re.compile(
    "(?:https?:\/\/)?(?:www\.)?((?:i\.)?imgur.com\/(?:(?P<dir>a|gallery)\/)?(?P<id>.+))",
    re.MULTILINE,
)
prefix_regex = re.compile("^(?:https?:\/\/)?(?:www\.)?")


class Imgur:
    def __init__(self, client_id: str, *, session: aiohttp.ClientSession) -> None:
        self.client_id = client_id
        self.headers = {"Authorization": f"Client-ID {self.client_id}"}

        self.session = session

    async def request(
        self, method: str, url: str, *, payload: Optional[dict] = None
    ) -> Union[dict, bytes]:
        async with self.session.request(
            method, url, headers=self.headers, data=payload
        ) as resp:
            resp.raise_for_status()
            try:
                return await resp.json()
            except aiohttp.ContentTypeError:
                return await resp.read()

    async def fetch_image(self, url: str) -> ImgurImage:
        data = await self.request("get", (await self.resolve_api_url(url))[0])
        return ImgurImage(data["data"], content=await self.fetch_image_bytes(url))

    async def fetch_image_bytes(self, url: str) -> io.BytesIO:
        url = await self.resolve_url(url)
        con = await self.request("get", url)
        return io.BytesIO(con)

    async def upload_image(
        self,
        image: io.BytesIO,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Tuple[ImgurImage, Response]:
        payload = {
            "title": title,
            "description": description,
            "name": name,
            "image": image,
        }
        data = await self.request("post", f"{IMGUR_API_URL}/image", payload=payload)
        image = ImgurImage(data["data"])
        response = Response(data)
        return image, response

    async def resolve_api_url(self, url: str) -> Tuple[str, str]:
        """Takes any image url and returns https://api.imgur.com/3/image/IMAGE_ID and IMAGE_ID"""
        if (match := imgur_url_regex.match(url)) is None:
            raise ValueError(f"Invalid url: {url}")

        img_dir = match.group("dir")
        _id = match.group("id")
        if img_dir == "a":
            req_url = f"{IMGUR_API_URL}/album/{_id}"
        elif img_dir == "gallery":
            req_url = f"{IMGUR_API_URL}/gallery/{_id}"
        elif not img_dir:
            return f"{IMGUR_API_URL}/image/{_id}", _id

        result = await self.request("get", req_url)
        try:
            image_id = result["data"]["images"][0]["id"]
        except KeyError as e:
            print(result)
            raise e
        else:
            return f"{IMGUR_API_URL}/image/{image_id}", image_id

    async def resolve_url(self, url: str) -> str:
        """Takes any image url and returns the direct url"""
        req_url, _id = await self.resolve_api_url(url)
        return f"https://i.imgur.com/{_id}.png"
