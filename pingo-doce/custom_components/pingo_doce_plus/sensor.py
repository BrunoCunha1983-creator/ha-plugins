from dataclasses import dataclass
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass
from homeassistant.const import UnitOfCurrency
from homeassistant.helpers.update_coordinator import CoordinatorEntity

@dataclass(frozen=True, kw_only=True)
class Desc(SensorEntityDescription):
    field: str

SENSORS = (
    Desc(key='status', name='Estado', field='status', icon='mdi:account-key'),
    Desc(key='points', name='Pontos', field='points', native_unit_of_measurement='pontos', icon='mdi:star-circle'),
    Desc(key='balance', name='Saldo', field='balance', device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=UnitOfCurrency.EURO),
    Desc(key='expiry_amount', name='Saldo a expirar', field='expiry_amount', device_class=SensorDeviceClass.MONETARY, native_unit_of_measurement=UnitOfCurrency.EURO),
    Desc(key='expiry_date', name='Validade do saldo', field='expiry_date', icon='mdi:calendar-clock'),
    Desc(key='expiry_message', name='Mensagem de validade', field='expiry_message', icon='mdi:message-text'),
    Desc(key='last_update', name='Última atualização', field='last_update', device_class=SensorDeviceClass.TIMESTAMP),
)

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(PingoSensor(entry.runtime_data, d) for d in SENSORS)

class PingoSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f'pingo_doce_plus_{description.key}'
        self._attr_device_info = {'identifiers': {('pingo_doce_plus', 'account')}, 'name': 'Pingo Doce Plus'}
    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.field)
