from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PingoAuth(entry.runtime_data), PingoCookie(entry.runtime_data)])

class Base(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_info = {'identifiers': {('pingo_doce_plus', 'account')}, 'name': 'Pingo Doce Plus'}

class PingoAuth(Base):
    _attr_name = 'Sessão autenticada'
    _attr_unique_id = 'pingo_doce_plus_authenticated'
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    @property
    def is_on(self): return bool(self.coordinator.data.get('authenticated'))

class PingoCookie(Base):
    _attr_name = 'Cookie disponível'
    _attr_unique_id = 'pingo_doce_plus_cookie_available'
    _attr_icon = 'mdi:cookie-check'
    @property
    def is_on(self): return bool(self.coordinator.data.get('cookie_available'))
    @property
    def extra_state_attributes(self): return {'cookie_names': self.coordinator.data.get('cookie_names', [])}
