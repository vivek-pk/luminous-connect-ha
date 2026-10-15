# Luminous Connect X for Home Assistant

Reads your solar plant data from the Luminous Connect X cloud every 2 minutes.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Validate](https://github.com/vivek-pk/luminous-connect-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/vivek-pk/luminous-connect-ha/actions/workflows/validate.yml)

## Install

### With HACS (recommended)

1. Click to open this repository in HACS on your Home Assistant, then click **Download**:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vivek-pk&repository=luminous-connect-ha&category=integration)

2. Restart Home Assistant.
3. Click to add the integration, then enter your luminousconnectx.com email and password:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=luminous_connect)

### Manual

1. Copy `custom_components/luminous_connect` into your Home Assistant `config/custom_components/` folder.
2. Restart Home Assistant.
3. Use the **Add integration** button above, or go to **Settings → Devices & services → Add integration → Luminous Connect X**.

Each plant shows up as a device with these sensors: solar, load and grid power (kW); battery % and voltage; grid voltage; solar energy today, this month and lifetime; consumption today (kWh); battery and grid state; and last update time.

It also adds one-way power sensors (grid import/export, battery charge/discharge) and matching kWh totals for the Energy dashboard.

## Energy dashboard

Go to **Settings → Dashboards → Energy** and pick:

| Energy dashboard field | Sensor |
|---|---|
| Grid consumption | Grid import energy |
| Return to grid | Grid export energy |
| Solar production | Solar energy today |
| Battery: energy going in | Battery charged energy |
| Battery: energy coming out | Battery discharged energy |

Home consumption is worked out by Home Assistant from these.

Luminous does not give grid or battery kWh totals, so the integration builds them from power readings and the time between device reports. Expect them to be close to, but not exactly, the Luminous app's numbers. Gaps longer than 30 minutes (device offline) are not counted. The first numbers appear after the second device report.

## Troubleshooting

Run `python3 test_login.py` on any computer (`pip install aiohttp` first) to check your login and see the raw data the API returns.
