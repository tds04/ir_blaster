"""Constants for IR Blaster integration."""

DOMAIN = "ir_blaster"

CONF_TOPIC = "mqtt_topic"
CONF_DEVICE_NAME = "device_name"

# MQTT topics (Tasmota convention)
TOPIC_SEND = "cmnd/{topic}/SerialSend5"
TOPIC_RESULT = "tele/{topic}/RESULT"

# Tuya MCU packets
PKT_STUDY_ON  = "55AA000600050104000101 11"
PKT_STUDY_OFF = "55AA000600050104000102 12"
PKT_ENABLE    = "55AA000600050101000100 0D"
PKT_SEND_IR   = "55AA000600050100000100 0C"

# DP keys in TuyaReceived
DP_IR_CODE_7 = "DpType0Id7"
DP_IR_CODE_2 = "DpType0Id2"
DP_CONTROL   = "DpType4Id1"

DEFAULT_TOPIC = "Irblaster"
