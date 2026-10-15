"""One device per Luminous plant, with power, energy and battery sensors."""
from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    RestoreSensor,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfEnergy, UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .api import parse_number

# Units match what the Luminous web dashboard prints next to each value.
POWER = dict(device_class=SensorDeviceClass.POWER, native_unit_of_measurement=UnitOfPower.KILO_WATT, state_class=SensorStateClass.MEASUREMENT)
ENERGY = dict(device_class=SensorDeviceClass.ENERGY, native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR, state_class=SensorStateClass.TOTAL_INCREASING)
VOLTAGE = dict(device_class=SensorDeviceClass.VOLTAGE, native_unit_of_measurement=UnitOfElectricPotential.VOLT, state_class=SensorStateClass.MEASUREMENT)

# These two are W instead of kW on ARCTIC_HYBRID inverters (the web app switches the unit label).
W_ON_ARCTIC = {"stats.solar_power", "stats.totalGrid"}

# key is the path inside the statsV1 "data" object.
SENSORS = (
    SensorEntityDescription(key="stats.solar_power", name="Solar power", **POWER),
    SensorEntityDescription(key="stats.consumptionValue", name="Load power", **POWER),
    SensorEntityDescription(key="stats.totalGrid", name="Grid power", **POWER),
    SensorEntityDescription(
        key="stats.battery_charge_percentage",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="batteryVoltage", name="Battery voltage", **VOLTAGE),
    SensorEntityDescription(key="stats.input_voltage", name="Grid voltage", **VOLTAGE),
    SensorEntityDescription(key="stats.generation", name="Solar energy today", **ENERGY),
    SensorEntityDescription(key="stats.energyThisMonth", name="Solar energy this month", **ENERGY),
    SensorEntityDescription(key="lifetimeGeneration", name="Solar energy lifetime", **ENERGY),
    SensorEntityDescription(key="todayConsumption", name="Consumption today", **ENERGY),
    SensorEntityDescription(key="stats.batteryState", name="Battery state"),
    SensorEntityDescription(key="stats.grid_state", name="Grid state"),
    SensorEntityDescription(key="stats.last_updated_timestamp", name="Last update", device_class=SensorDeviceClass.TIMESTAMP),
    # One-way flows from api.energy_flows.
    SensorEntityDescription(key="flows.grid_import", name="Grid import power", **POWER),
    SensorEntityDescription(key="flows.grid_export", name="Grid export power", **POWER),
    SensorEntityDescription(key="flows.battery_charge", name="Battery charge power", **POWER),
    SensorEntityDescription(key="flows.battery_discharge", name="Battery discharge power", **POWER),
)

# For the Energy dashboard: kWh counters built from the flow power sensors above.
ENERGY_SENSORS = (
    SensorEntityDescription(key="grid_import", name="Grid import energy", **ENERGY),
    SensorEntityDescription(key="grid_export", name="Grid export energy", **ENERGY),
    SensorEntityDescription(key="battery_charge", name="Battery charged energy", **ENERGY),
    SensorEntityDescription(key="battery_discharge", name="Battery discharged energy", **ENERGY),
)

# A device that stops reporting this long is treated as offline; the gap is not counted.
MAX_GAP_SECONDS = 30 * 60


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [LuminousSensor(coordinator, plant_id, d) for plant_id in coordinator.data for d in SENSORS]
        + [LuminousEnergySensor(coordinator, plant_id, d) for plant_id in coordinator.data for d in ENERGY_SENSORS]
    )


class LuminousSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, plant_id: str, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._plant_id = plant_id
        self._attr_unique_id = f"{plant_id}_{description.key}"
        plant = coordinator.data[plant_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, plant_id)},
            name=plant["name"] or f"Luminous plant {plant_id}",
            manufacturer="Luminous",
            model=plant["stats"].get("inverterModel"),
        )

    @property
    def _stats(self) -> dict:
        return (self.coordinator.data.get(self._plant_id) or {}).get("stats") or {}

    @property
    def native_value(self):
        value = self._stats
        for part in self.entity_description.key.split("."):
            value = (value or {}).get(part)
        if value in (None, "", "NA"):
            return None
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return datetime.fromtimestamp(float(value), UTC)
        if self.entity_description.native_unit_of_measurement:
            number = parse_number(value)
            if number is not None and self.entity_description.key in W_ON_ARCTIC and self._stats.get("inverterType") == "ARCTIC_HYBRID":
                return number / 1000  # this model reports W, the others kW
            return number
        return value


class LuminousEnergySensor(LuminousSensor, RestoreSensor):
    """kWh total for one flow, built from its power and the device's own report times.

    The API has no grid/battery energy counters, so this adds power x time between device reports.
    shortcut: holds each power reading until the next report, so it is only as fine as the device's
    reporting interval; switch to API counters if Luminous ever exposes them.
    """

    def __init__(self, coordinator, plant_id: str, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, plant_id, description)
        self._total = 0.0
        self._last: tuple[float, float] | None = None  # (device report time, kW)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) and last.native_value is not None:
            self._total = float(last.native_value)
        self._add_reading()

    def _handle_coordinator_update(self) -> None:
        self._add_reading()
        super()._handle_coordinator_update()

    def _add_reading(self) -> None:
        reported = parse_number((self._stats.get("stats") or {}).get("last_updated_timestamp"))
        power = (self._stats.get("flows") or {}).get(self.entity_description.key)
        if reported is None or power is None or (self._last and reported <= self._last[0]):
            return  # no new report from the device since last poll
        if self._last and reported - self._last[0] <= MAX_GAP_SECONDS:
            self._total += self._last[1] * (reported - self._last[0]) / 3600
        self._last = (reported, power)

    @property
    def native_value(self):
        return round(self._total, 3)
