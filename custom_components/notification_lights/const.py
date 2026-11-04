"""Constants for Notification Lights."""

DOMAIN = "notification_lights"
AQARA_DOMAIN = "aqara_advanced_lighting"

CONF_QUIET_ENTITY = "quiet_entity"

# Subentry types: each light and each notification is one subentry (its id is the item id).
KIND_LIGHT = "light"
KIND_NOTIFICATION = "notification"

# Notification light
CONF_LIGHT = "light"
CONF_AREAS = "areas"
CONF_FLOOR = "floor"
CONF_SEGMENTS = "segments"
CONF_OFFSET = "offset"
CONF_BRIGHTNESS = "brightness"
CONF_QUIET_HOURS = "quiet_hours"
CONF_IDLE_POLICY = "idle_policy"

IDLE_OFF = "off"
IDLE_RESTORE = "restore"
IDLE_POLICIES = [IDLE_OFF, IDLE_RESTORE]

# Notification
CONF_NAME = "name"
CONF_COLOUR = "colour"
CONF_FOOTPRINT = "footprint"
CONF_PRIORITY = "priority"
CONF_SHOW_QUIET = "show_during_quiet_hours"
CONF_SCOPE = "scope"
CONF_SCOPE_AREA = "scope_area"
CONF_SCOPE_FLOOR = "scope_floor"
CONF_DELAY = "delay"
CONF_SOURCE_TYPE = "source_type"
CONF_SOURCE_ENTITIES = "source_entities"
CONF_SOURCE_STATE = "source_state"
CONF_SOURCE_TEMPLATE = "source_template"

SCOPE_HOUSE = "house"
SCOPE_FLOOR = "floor"
SCOPE_ROOM = "room"
SCOPES = [SCOPE_HOUSE, SCOPE_FLOOR, SCOPE_ROOM]

SOURCE_ENTITIES = "entities"
SOURCE_TEMPLATE = "template"

# Entry-level device holding Dismiss all and Print guide.
GENERAL_DEVICE = "general"

PREVIEW_SECONDS = 30
SERVICE_DISMISS_ALL = "dismiss_all"
SERVICE_PRINT_SHEET = "print_sheet"
