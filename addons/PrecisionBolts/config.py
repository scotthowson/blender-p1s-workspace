from itertools import chain
from pathlib import Path

import bpy

# TODO: Check what is still used

DEBUG_PRINT_THUMB_RENDER_LOG = False

BLENDER = bpy.app.binary_path
SCRIPT_DIR = Path(__file__).parent
DEFAULTS_DIR = SCRIPT_DIR / "defaults"
BOLT_PRESETS_DIR = DEFAULTS_DIR / "BOLT"
NUT_PRESETS_DIR = DEFAULTS_DIR / "NUT"
SCREW_PRESETS_DIR = DEFAULTS_DIR / "SCREW"
USER_PRESETS_DIR = SCRIPT_DIR / "user_presets"
TOOLTIPS_CFG = SCRIPT_DIR / "tooltips.ini"
RESOURCES_DIR = SCRIPT_DIR / "resources"
HEADS_FILE = RESOURCES_DIR / "heads.blend"
DRIVERS_FILE = RESOURCES_DIR / "drivers.blend"
NUTS_FILE = RESOURCES_DIR / "nuts.blend"
METRIC_THREADS_FILE = RESOURCES_DIR / "metric_threads.csv"

PRESET_THUMB_TEMPLATE = RESOURCES_DIR / "thumb_render_template.blend"
PRESET_THUMB_SCRIPT = SCRIPT_DIR / "generate_thumb.py"
PRESET_THUMB_DIR = USER_PRESETS_DIR / "thumbnails"
PRESET_THUMB_RESOLUTION = 256
PRESET_THUMB_SUFFIX = ".png"
THUMB_COLLECTION_ALIAS = "fastener_thumbnails"
ACTIVE_PRESET_DIR_ALIAS = "active_fastener_preset_dir"

THUMB_GEN_IP = "127.0.0.1"
THUMB_GEN_PORT = "8888"

PROPS_ALIAS = "fastener_props"
PRESET_UPDATE_PROP_ALIAS = "fastener_presets_update_required"

THREAD_FIELDS = ("thread_name", "major_diameter", "pitch")

PROP_BLACKLIST = {
    "bl_rna",
    "rna_type",
    "editing",
    "preset_thumbnail",
    "preset_category",
}

FASTENER_PROP_GROUPINGS = {
    "THREAD": {
        "custom_thread_profile",
        "length",
        "pitch",
        "major_diameter",
        "nut_diameter",
        "minor_diameter",
        "crest_weight",
        "root_weight",
        "thread_angle",
        "thread_resolution",
        "starts",
        "runout_length",
        "runout_offset",
        "shank_length",
        "chamfer",
        "chamfer_length",
        "chamfer_divisions",
        "screw_taper_factor",
        "trim"
    },
    "HEAD": {
        "head_type",
        "head_length",
        "head_diameter",
        "head_subdiv",
        "head_mod_a",
        "head_mod_b",
        "head_mod_c",
    },
    "DRIVER": {
        "driver_type",
        "driver_depth",
        "driver_diameter",
        "driver_mod_a",
        "driver_mod_b",
        "driver_mod_c",
        "driver_mod_d",
        "driver_mod_e",
        "driver_mod_f",
    },
}
FASTENER_PROP_GROUPINGS['FULL'] = set(
    chain.from_iterable((FASTENER_PROP_GROUPINGS.values()))
)
FASTENER_PROP_GROUPINGS['FULL'] = set.union(
    FASTENER_PROP_GROUPINGS['FULL'],
    {"scale", "tolerance", "trim"}
)

PRESET_CATEGORIES = (
    "PREMADE",
    "THREAD",
    "HEAD",
    "DRIVER",
)

THREAD_DIRS = (
    "RIGHT",
    "LEFT",
)

FASTENER_TYPES = (
    "BOLT",
    "SCREW",
    "NUT",
    "THREADED_ROD",
)

CUTTERS = (
    "CROSS",
    "HEXAGON",
    "SQUARE",
)

HEAD_NAMES = (
    "NONE",
    "FLAT",
    "HEX",
    "HEX_WASHER",
    "SOCKED",
    "CARRIAGE",
)

DRIVES_ENUM = (
    "NONE",
    "CROSS",
    "SLOTTED",
    "POLYGON",
)

NUT_TYPES = (
    "HEX",
    "SQUARE",
)
