"""Constants for Notification Lights."""

DOMAIN = "notification_lights"
AQARA_DOMAIN = "aqara_advanced_lighting"

CONF_QUIET_ENTITY = "quiet_entity"

SUBENTRY_LIGHT = "light"

CONF_LIGHT = "light"
CONF_SEGMENTS = "segments"
CONF_OFFSET = "offset"
CONF_BRIGHTNESS = "brightness"
CONF_QUIET_AT_BEDTIME = "quiet_at_bedtime"
CONF_IDLE_POLICY = "idle_policy"

IDLE_OFF = "off"
IDLE_RESTORE = "restore"
IDLE_POLICIES = [IDLE_OFF, IDLE_RESTORE]
