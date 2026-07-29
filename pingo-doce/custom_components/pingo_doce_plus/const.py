from pathlib import Path
from homeassistant.const import Platform

DOMAIN = "pingo_doce_plus"
NAME = "Pingo Doce Plus"
SHARED = Path("/config/pingo_doce_plus")
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]
