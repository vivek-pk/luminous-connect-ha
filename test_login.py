"""Check your Luminous login outside Home Assistant and print what the API returns.

Run: python3 test_login.py   (needs: pip install aiohttp). Asks for email/password; nothing is saved.
"""
import asyncio
import getpass
import json
import pathlib
import sys

import aiohttp

sys.path.insert(0, str(pathlib.Path(__file__).parent / "custom_components" / "luminous_connect"))
from api import LuminousApi, parse_number  # noqa: E402

assert parse_number(3) == 3
assert parse_number("1,234.5 kWh") == 1234.5
assert parse_number("1.2 MWh") == 1200
assert parse_number("NA") is None


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        api = LuminousApi(session, input("Email: "), getpass.getpass())
        await api.login()
        print("Logged in, user id", api.user_id)
        plants = await api.get_plants()
        print("Plants:", [(p["id"], p.get("plantName")) for p in plants])
        for plant in plants:
            print(json.dumps(await api.get_stats(plant["id"]), indent=2))


asyncio.run(main())
