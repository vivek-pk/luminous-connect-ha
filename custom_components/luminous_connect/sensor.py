"""One device per Luminous plant, with power, energy and battery sensors."""
from datetime import UTC, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
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
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        LuminousSensor(coordinator, plant_id, description)
        for plant_id in coordinator.data
        for description in SENSORS
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
    def native_value(self):
        value = (self.coordinator.data.get(self._plant_id) or {}).get("stats")
        for part in self.entity_description.key.split("."):
            value = (value or {}).get(part)
        if value in (None, "", "NA"):
            return None
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            return datetime.fromtimestamp(float(value), UTC)
        if self.entity_description.native_unit_of_measurement:
            return parse_number(value)
        return value
