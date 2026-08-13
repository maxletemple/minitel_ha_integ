"""Constants for the Minitel Interface integration."""

DOMAIN = "minitel_interface"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 10  # seconds

CONF_DASHBOARD_MEDIA_PLAYER_ENTITY = "dashboard_media_player_entity"
CONF_DASHBOARD_WEATHER_ENTITY = "dashboard_weather_entity"
CONF_DASHBOARD_WIN_INDEX = "dashboard_win_index"
CONF_DASHBOARD_OBJ_INDEX = "dashboard_obj_index"
CONF_DASHBOARD_POS_X = "dashboard_pos_x"
CONF_DASHBOARD_POS_Y = "dashboard_pos_y"
CONF_DASHBOARD_WIDTH = "dashboard_width"
CONF_DASHBOARD_HEIGHT = "dashboard_height"

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB, guards the single shared TCP socket

SERVICE_WIN_CREATE = "win_create"
SERVICE_WIN_DESTROY = "win_destroy"
SERVICE_WIN_TRANSFORM = "win_transform"
SERVICE_WIN_ORDER = "win_order"
SERVICE_SET_OBJECT_TEXT = "set_object_text"
SERVICE_SET_OBJECT_PICTURE = "set_object_picture"
SERVICE_SET_OBJECT_VIDEO = "set_object_video"
SERVICE_RM_OBJECT = "rm_object"
SERVICE_POWER = "power"

ATTR_WIN_INDEX = "win_index"
ATTR_OBJ_INDEX = "obj_index"
ATTR_POS_X = "pos_x"
ATTR_POS_Y = "pos_y"
ATTR_WIDTH = "width"
ATTR_HEIGHT = "height"
ATTR_BACKGROUND_COLOR = "background_color"
ATTR_ORDER = "order"
ATTR_X = "x"
ATTR_Y = "y"
ATTR_FONT_SIZE = "font_size"
ATTR_TEXT = "text"
ATTR_FILE_PATH = "file_path"
ATTR_FULLSCREEN = "fullscreen"
ATTR_STATE = "state"
