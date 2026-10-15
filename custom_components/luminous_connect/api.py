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


# statsV1 "animationFlow" codes -> direction, copied from the web app's energy-flow animation switch.
GRID_IMPORT = {"1.5", "1.7", "1.11", "1.12", "2.5", "2.7", "2.11", "2.12", "3.5", "3.7", "3.11", "3.12", "4.5", "4.7", "4.9", "4.11", "6.3", "6.4", "6.5", "7.3", "7.4", "9.3", "9.4", "9.5", "10.3", "10.4", "13.6", "13.7", "13.9", "13.10", "13.11", "14.3", "14.4", "14.5", "15.3", "15.4", "15.5", "15.13", "15.15"}
GRID_EXPORT = {"4.12", "4.13", "4.14", "4.15", "5.1", "10.5", "10.6", "13.12", "13.13", "13.14", "13.15", "13.16", "15.8", "15.9", "15.10", "15.12", "15.16", "15.17", "15.18"}
BATTERY_CHARGE = {"1.2", "1.7", "1.8", "1.11", "2.2", "2.7", "2.8", "2.11", "3.2", "3.7", "3.8", "3.11", "4.2", "4.7", "4.8", "4.9", "4.11", "4.12", "4.13", "6.4", "6.5", "7.4", "9.4", "9.5", "13.3", "13.7", "13.8", "13.9", "13.10", "13.12", "13.13", "14.4", "14.5", "15.4", "15.5", "15.7", "15.9", "15.10", "15.11", "15.13"}
BATTERY_DISCHARGE = {"1.3", "1.4", "2.3", "2.4", "3.3", "3.4", "4.3", "4.4", "6.2", "7.2", "9.2", "13.4", "13.5", "13.16", "14.2", "15.2", "15.14", "15.16", "15.17", "15.18"}


def energy_flows(data: dict) -> dict:
    """Split grid and battery power into one-way flows in kW, as the Energy dashboard needs."""
    stats = data.get("stats") or {}
    code = str(data.get("animationFlow"))
    grid = abs(parse_number(stats.get("totalGrid")) or 0)
    if data.get("inverterType") == "ARCTIC_HYBRID":
        grid /= 1000  # this model reports W, the others kW
    battery = abs(parse_number(stats.get("batteryPower")) or 0) / 1000  # always W
    return {
        "grid_import": grid if code in GRID_IMPORT else 0.0,
        "grid_export": grid if code in GRID_EXPORT else 0.0,
        "battery_charge": battery if code in BATTERY_CHARGE else 0.0,
        "battery_discharge": battery if code in BATTERY_DISCHARGE else 0.0,
    }


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
