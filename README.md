# Luminous Connect X for Home Assistant

Reads your solar plant data from the Luminous Connect X cloud every 5 minutes.

## Install

1. Copy `custom_components/luminous_connect` into your Home Assistant `config/custom_components/` folder.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Luminous Connect X** and enter your luminousconnectx.com email and password.

Each plant shows up as a device with these sensors: solar, load and grid power (kW); battery % and voltage; grid voltage; solar energy today, this month and lifetime; consumption today (kWh); battery and grid state; and last update time.

For the Energy dashboard, use **Solar energy today** as solar production.

## Troubleshooting

Run `python3 test_login.py` on any computer (`pip install aiohttp` first) to check your login and see the raw data the API returns.
