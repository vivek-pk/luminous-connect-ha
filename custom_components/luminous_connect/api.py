"""Minimal client for the Luminous Connect X cloud API.

Endpoints and headers were read from the luminousconnectx.com web app bundle; there is no public API doc.
"""
import re

import aiohttp

USER_URL = "https://lumconnectprodusermanagement.azurewebsites.net/v1/"
PRODUCT_URL = "https://lumconnectprodproductmanagement.azurewebsites.net/v1/"


class AuthError(Exception):
    """Wrong email or password."""


def parse_number(value):
    """The API mixes numbers and strings like '1,234.5 kWh' or '1.2 MWh'; return a float in k-units."""
    if isinstance(value, (int, float)):
        return value
    text = str(value or "").replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match[0]) * (1000 if "MWh" in text else 1)


class LuminousApi:
    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None
        self.user_id: str | None = None

    async def login(self) -> None:
        async with self._session.post(
            USER_URL + "users/nox/loginEmail",
            json={"email": self._email, "password": self._password},
        ) as resp:
            # The web app treats 204 (empty body) as "wrong email or password".
            if resp.status in (204, 401, 403):
                raise AuthError
            resp.raise_for_status()
            user = await resp.json()
            self._token = resp.headers.get("Authorization")
        if not self._token or not user.get("id"):
            raise AuthError
        self.user_id = str(user["id"])

    async def _get(self, path: str):
        for attempt in range(2):
            if not self._token:
                await self.login()
            async with self._session.get(
                PRODUCT_URL + path,
                headers={"authorization": self._token, "X-UserID": self.user_id, "accept": "application/json"},
            ) as resp:
                if resp.status in (401, 403) and attempt == 0:
                    self._token = None  # token expired: log in again once
                    continue
                resp.raise_for_status()
                return None if resp.status == 204 else await resp.json()

    async def get_plants(self) -> list[dict]:
        if not self.user_id:
            await self.login()
        body = await self._get(f"plants/getAllV1/{self.user_id}")
        data = (body or {}).get("data") or {}
        return (data.get("primaryPlant") or []) + (data.get("secondaryPlant") or [])

    async def get_stats(self, plant_id) -> dict:
        body = await self._get(f"plants/{plant_id}/statsV1")
        return (body or {}).get("data") or {}
