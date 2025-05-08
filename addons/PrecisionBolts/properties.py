from __future__ import annotations
import configparser
from pathlib import Path
from math import radians
from typing import Iterable
import configparser

import bpy
from bpy.props import (
    BoolProperty,
    StringProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup, Context
import bpy.utils.previews

from .fasteners import update_fastener
from . import config
from . import presets


def _create_type_enum_prop(types: Iterable[str]):
    enum = []
    for i, type_string in enumerate(types):
        label = type_string.title().replace("_", " ")
        enum.append((type_string, label, label, i))
    enum.sort(key=lambda item: item[1])
    return enum


# Enums
FASTENERS_ENUM = _create_type_enum_prop(config.FASTENER_TYPES)
HEADS_ENUM = _create_type_enum_prop(config.HEAD_NAMES)
DRIVES_ENUM = _create_type_enum_prop(config.DRIVES_ENUM)
NUTS_ENUM = _create_type_enum_prop(config.NUT_TYPES)
THREAD_DIR_ENUM = _create_type_enum_prop(config.THREAD_DIRS)
PLACEHOLDER_ENUM = (("NONE", "None", "None", 0),)


# UI tooltips for props
_tooltips_cfg = configparser.ConfigParser()
_tooltips_cfg.read(config.TOOLTIPS_CFG)
prop_tooltips = _tooltips_cfg["Props"]

preview_collections = {}
global_thumb_ref = set()


def clear_preset_filter(self: FastenerProps, context: Context) -> None:
    if not self.apply_preset_filter:
        preview_collection = preview_collections[config.THUMB_COLLECTION_ALIAS]
        preview_collection.force_update = True


def populate_thumb_enum(self: FastenerProps, context: Context):
    """Callback for enum of png images for thumbnail preview collection"""
    enum_items = []
    props = self

    # Why?
    if not isinstance(props, FastenerProps):
        props = getattr(context.active_object, config.PROPS_ALIAS)

    preview_collection = preview_collections[config.THUMB_COLLECTION_ALIAS]

    if context is None:
        return enum_items

    preset_category = props.preset_category
    preset_dir = config.USER_PRESETS_DIR / props.fastener_type / preset_category

    n_thumbs = len(list(preset_dir.glob(f"*{config.PRESET_THUMB_SUFFIX}")))

    filter_is_applied = all(
        (
            props.apply_preset_filter,
            props.preset_filter != "",
        )
    )

    filter_has_changed = preview_collection.active_filter != props.preset_filter
    # preset_dir_changed =  preset_dir != preview_collection.active_directory
    # thumb_count_changed = n_thumbs != preview_collection.n_known_thumbs

    update_conditions = {
        "new preset dir": preset_dir != preview_collection.active_directory,
        "thumb count change": n_thumbs != preview_collection.n_known_thumbs,
        "filter string change": all((filter_is_applied, filter_has_changed)),
        "forced update": preview_collection.force_update,
    }

    changes = []
    for test, condition in update_conditions.items():
        if condition:
            # print(test)
            changes.append(test)
        
    if not changes or props.thumb_rendering:
        return preview_collection.previews
    
    preview_collection.active_directory = preset_dir
    preview_collection.active_filter = props.preset_filter

    # If preset_dir_changed or thumb_count_changed:
    try:
        preview_collection.clear()
    except ResourceWarning:
        pass

    preset_dict = presets.get(props.fastener_type)
    category_presets = preset_dict[preset_category]
    n_known_thumbs = 0

    if preset_dir.exists:
        for indx, preset in enumerate(category_presets.values()):
            thumb_fname = f"{preset['thumb']}{config.PRESET_THUMB_SUFFIX}"
            thumb_path = preset_dir / thumb_fname
            preset_name = preset["preset_name"]
            if not thumb_path.exists():
                print(preset_name, " has no thumb")
                continue

            n_known_thumbs += 1

            if filter_is_applied:
                if props.preset_filter not in preset_name:
                    continue

            value = preset["preset_name"]
            label = preset_name
            thumb_key = (
                f"{props.fastener_type}_{preset_category}_{preset['preset_name']}"
            )
            filepath = str(thumb_path)

            icon = preview_collection.get(thumb_key)
            if not icon:
                thumb = preview_collection.load(thumb_key, filepath, "IMAGE")
            else:
                thumb = preview_collection[thumb_key]

            item = (value, label, value, thumb.icon_id, indx)
            global_thumb_ref.add(item)
            enum_items.append(item)

    global_thumb_ref.union(enum_items)

    preview_collection.n_known_thumbs = n_known_thumbs
    preview_collection.previews = enum_items
    preview_collection.force_update = False
    preview_collection.active_directory = preset_dir
    return preview_collection.previews


class FastenerProps(PropertyGroup):
    """Property group of active fastener"""

    # Addon Props
    editing: BoolProperty(default=False)
    is_fastener: BoolProperty(default=False)

    # Presets
    preset_category: EnumProperty(items=presets.user_preset_categories_enum, default=0)
    preset_thumbnail: EnumProperty(items=populate_thumb_enum, default=0)
    # force_update: BoolProperty(default=False)

    # Preset filtering
    apply_preset_filter: BoolProperty(
        default=False, description=prop_tooltips["apply_preset_filter"],
        update=clear_preset_filter
    )
    preset_filter: StringProperty(
        default="", description=prop_tooltips["preset_filter"]
    )

    # Preset saving
    preset_save_component_full: BoolProperty(default=True)
    preset_save_component_thread: BoolProperty(default=False)
    preset_save_component_driver: BoolProperty(default=False)
    preset_save_component_head: BoolProperty(default=False)
    thumb_rendering: BoolProperty(default=False)

    # Type props
    fastener_type: EnumProperty(items=FASTENERS_ENUM, default=0, update=update_fastener)
    nut_type: EnumProperty(items=NUTS_ENUM, update=update_fastener)

    # General Props
    length: FloatProperty(
        min=0.0001,
        default=5,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["length"],
    )
    tolerance: FloatProperty(
        default=0.0, update=update_fastener, description=prop_tooltips["tolerance"]
    )
    thread_resolution: IntProperty(
        min=8,
        default=16,
        soft_max=64,
        update=update_fastener,
        description=prop_tooltips["thread_resolution"],
    )
    scale: FloatProperty(
        default=1, update=update_fastener, description=prop_tooltips["scale"]
    )
    # center_origin: BoolProperty(default=False, update=update_fastener)

    # Thread Props
    # thread_type: EnumProperty(items=THREAD_TYPES_ENUM, default=0, update=update_fastener)
    custom_thread_profile: BoolProperty(
        default=False,
        update=update_fastener,
        description=prop_tooltips["custom_thread_profile"],
    )
    pitch: FloatProperty(
        min=radians(5),
        description=prop_tooltips["pitch"],
        default=2,
        subtype="DISTANCE",
        update=update_fastener,
    )
    major_diameter: FloatProperty(
        default=2,
        min=0.0001,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["major_diameter"],
    )
    minor_diameter: FloatProperty(
        default=1.2,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["minor_diameter"],
    )
    crest_weight: FloatProperty(
        default=0.5,
        subtype="FACTOR",
        update=update_fastener,
        min=0,
        max=1,
        description=prop_tooltips["crest_weight"],
    )
    root_weight: FloatProperty(
        default=0.5,
        subtype="FACTOR",
        update=update_fastener,
        min=0,
        max=1,
        description=prop_tooltips["root_weight"],
    )
    thread_angle: FloatProperty(
        default=radians(60),
        description=prop_tooltips["thread_angle"],
        subtype="ANGLE",
        update=update_fastener,
    )
    starts: IntProperty(
        min=1,
        soft_max=10,
        default=1,
        update=update_fastener,
        description=prop_tooltips["starts"],
    )
    runout_length: FloatProperty(
        min=0,
        default=0,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["runout_length"],
    )
    runout_offset: FloatProperty(
        default=0,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["runout_offset"],
    )

    # Head Props
    # head_preset: EnumProperty(items=PLACEHOLDER_ENUM, default=0, update=update_fastener)
    head_type: EnumProperty(
        items=HEADS_ENUM,
        default="NONE",
        update=update_fastener,
        description=prop_tooltips["head_type"],
    )
    head_length: FloatProperty(
        name="Length",
        min=0.001,
        default=1,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["head_length"],
    )
    head_diameter: FloatProperty(
        name="Diameter",
        min=0.001,
        default=1.5,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["head_diameter"],
    )
    head_subdiv: IntProperty(
        name="Subdivide",
        min=0,
        default=0,
        soft_max=3,
        update=update_fastener,
        description=prop_tooltips["head_subdiv"],
    )
    head_mod_a: FloatProperty(
        default=0.22,
        min=0,
        update=update_fastener,
        description=prop_tooltips["head_mod_a"],
    )
    head_mod_b: FloatProperty(
        default=1,
        min=0,
        update=update_fastener,
        description=prop_tooltips["head_mod_b"],
    )
    head_mod_c: FloatProperty(
        default=1,
        min=0,
        update=update_fastener,
        description=prop_tooltips["head_mod_c"],
    )

    # Bolts/Screws
    shank_length: FloatProperty(
        min=0,
        default=1,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["shank_length"],
    )
    chamfer: FloatProperty(
        min=0,
        default=radians(15),
        description=prop_tooltips["chamfer"],
        subtype="ANGLE",
        update=update_fastener,
    )
    chamfer_length: FloatProperty(
        min=0,
        update=update_fastener,
        default=0.0,
        description=prop_tooltips["chamfer_length"],
    )
    chamfer_divisions: IntProperty(
        min=0,
        update=update_fastener,
        default=0,
        description=prop_tooltips["chamfer_divisions"],
    )
    screw_taper_factor: FloatProperty(
        subtype="FACTOR",
        min=0,
        max=1,
        update=update_fastener,
        default=0.33,
        description=prop_tooltips["screw_taper_factor"],
    )
    trim: FloatProperty(
        min=0,
        max=0.99,
        subtype="FACTOR",
        update=update_fastener,
        default=0,
        description=prop_tooltips["trim"],
    )

    # Drivers
    # driver_preset: EnumProperty(items=PLACEHOLDER_ENUM, default=0, update=update_fastener)
    driver_type: EnumProperty(
        items=DRIVES_ENUM,
        default="NONE",
        update=update_fastener,
        description=prop_tooltips["driver_type"],
    )
    driver_depth: FloatProperty(
        name="Depth",
        min=0.0001,
        default=0.3,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["driver_depth"],
    )
    driver_diameter: FloatProperty(
        name="Diameter",
        min=0,
        default=1.5,
        subtype="DISTANCE",
        update=update_fastener,
        description=prop_tooltips["driver_diameter"],
    )
    driver_mod_a: FloatProperty(
        default=1,
        min=0,
        update=update_fastener,
        description=prop_tooltips["driver_mod_a"],
    )
    driver_mod_b: FloatProperty(
        default=1,
        min=0,
        update=update_fastener,
        description=prop_tooltips["driver_mod_b"],
    )
    driver_mod_c: FloatProperty(
        default=1,
        min=0,
        update=update_fastener,
        description=prop_tooltips["driver_mod_c"],
    )
    driver_mod_d: FloatProperty(
        default=1,
        min=0,
        update=update_fastener,
        description=prop_tooltips["driver_mod_d"],
    )
    driver_mod_e: FloatProperty(
        default=1,
        min=0,
        update=update_fastener,
        description=prop_tooltips["driver_mod_e"],
    )
    driver_mod_f: IntProperty(
        default=6,
        min=3,
        update=update_fastener,
        description=prop_tooltips["driver_mod_f"],
    )

    # Nut Props
    nut_chamfer: FloatProperty(
        default=1,
        min=0.001,
        max=1,
        update=update_fastener,
        description=prop_tooltips["nut_chamfer"],
    )
    nut_diameter: FloatProperty(
        default=1,
        min=0.001,
        update=update_fastener,
        description=prop_tooltips["nut_diameter"],
    )

    # General
    # thread_direction: EnumProperty(items=THREAD_DIR_ENUM, default="RIGHT", update=update_fastener)
    shade_smooth: BoolProperty(
        default=False, update=update_fastener, description=prop_tooltips["shade_smooth"]
    )
    triangulate: BoolProperty(
        default=False, update=update_fastener, description=prop_tooltips["triangulate"]
    )
    bisect: BoolProperty(
        default=False, update=update_fastener, description=prop_tooltips["bisect"]
    )


classes = (FastenerProps,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    setattr(bpy.types.Object, config.PROPS_ALIAS, PointerProperty(type=FastenerProps))
    setattr(
        bpy.types.Scene, config.PRESET_UPDATE_PROP_ALIAS, BoolProperty(default=False)
    )

    preview_collection = bpy.utils.previews.new()
    preview_collection.names = []
    # preview_collection.category = ""
    preview_collection.filter = ""
    preview_collection.force_update = False
    preview_collection.active_filter = None
    preview_collection.active_directory = None
    preview_collection.n_known_thumbs = 0
    preview_collection.previews = ()
    preview_collections[config.THUMB_COLLECTION_ALIAS] = preview_collection


def unregister():
    # Remove preview collections
    for collection in preview_collections.values():
        bpy.utils.previews.remove(collection)
    preview_collections.clear()

    # Unregister props
    delattr(bpy.types.Object, config.PROPS_ALIAS)
    delattr(bpy.types.Scene, config.PRESET_UPDATE_PROP_ALIAS)
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
