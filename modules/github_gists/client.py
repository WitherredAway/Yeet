import typing
from typing import Optional, TypeVar
import yarl
import asyncio
import aiohttp

from .gist import Gist
from .exceptions import ClientAuthenticateError
from constants import API_URL


class Client:
    def __init__(self, *, session: Optional[aiohttp.ClientSession] = None):
        self.session = session

        self._request_lock = asyncio.Lock()

    async def authenticate(self, *, access_token: str):
        self.access_token = access_token
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        self.user_data = await self.fetch_user()

    async def request(self, method: str, url: str, *, params=None, data=None, headers=None) -> typing.Dict:
        if not hasattr(self, "access_token"):
            raise ClientAuthenticateError("Please authenticate this GistClient instance using the authenticate method first.")
            
        hdrs = {
            'Accept': "application/vnd.github.v3+json",
            'User-Agent': (self.user_data["login"] if hasattr(self, "user_data") else "User-Agent"),
            'Authorization': "token %s" % self.access_token,
        }

        request_url = yarl.URL(API_URL) / url

        if headers is not None and isinstance(headers, dict):
            hdrs.update(headers)

        await self._request_lock.acquire()
        try:
            async with self.session.request(
                    method, request_url, params=params, json=data, headers=hdrs
                ) as response:
                remaining = response.headers.get("X-Ratelimit-Remaining")
                json_data = await response.json()
                if response.status == 429 or remaining == "0":
                    reset_after = float(response.headers.get("X-Ratelimit-Reset-After"))
                    await asyncio.sleep(reset_after)
                    self._request_lock.release()
                    return await self.request(
                        method, request_url, params=params, data=data, headers=headers
                    )
                elif 300 > response.status >= 200:
                    return json_data
                else:
                    raise response.raise_for_status()
        finally:
            if self._request_lock.locked():
                self._request_lock.release()

    async def fetch_user(self) -> typing.Dict:
        """Fetch data of the authenticated user"""

        url = "user"
        user_data: typing.Dict = await self.request("GET", url)
        return user_data

    async def fetch_data(self, gist_id: str) -> typing.Dict:
        """Fetch data of a Gist"""
        
        url = "gists/%s" % gist_id
        gist_data: typing.Dict = await self.request("GET", url)
        return gist_data

    async def get_gist(self, gist_id: str) -> Gist:
        data = await self.fetch_data(gist_id)
        return Gist(data)

    async def create_gist(
        self,
        files: typing.Dict,  # e.g. {"output.txt": {"content": "Content of the file"}}
        *,
        description: str = None,
        public: bool = True,
    ) -> Gist:
        
        data = {"public": public, "files": files}
        params = {"scope": "gist"}

        if description:
            data["description"] = description

        url = "gists"
        js = await self.request(
            "POST", url, data=data, params=params
        )
        return Gist(js)

    async def update_gist(self, gist: Gist):
        """Re-fetch data and update the instance."""
        updated_gist_data = await self.fetch_data(gist.id)
        gist._update(updated_gist_data)

    async def edit(
        self,
        gist: Gist,
        *,
        files: typing.Dict,  # e.g. {"output.txt": {"content": "Content of the file"}}
        description: str = None,
    ):

        data = {"files": files}

        if description:
            data["description"] = description

        edited_gist_data = await self.request("PATCH", gist.request_url, data=data)
        gist._update(edited_gist_data)

    async def delete(self, gist: Gist):
        """Delete the gist."""
        await self.request("DELETE", gist.request_url)
        del gist
