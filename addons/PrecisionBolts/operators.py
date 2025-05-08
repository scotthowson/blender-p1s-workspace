from __future__ import annotations
from ast import Delete
from csv import DictReader, DictWriter
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Generator, Iterable, List, Set, Tuple
import json
import os
import platform
import subprocess
import asyncio

import bpy
from bpy.types import Event, Operator, Context, Object
from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
    IntProperty,
)
from mathutils import Vector, Matrix
import bmesh

from .toolz import dicttoolz
from .preset_field_types import PRESET_TYPES
from . import (
    bmesh_helpers,
    config,
    mesh_gen,
    fasteners,
    properties,
    polls,
    idnames,
    presets,
)
from .properties import FastenerProps
from .custom_types import PropsUpdateDisabled
from . import async_loop
from .bpy_helpers import deselect_all


def is_active_fastener(context: Context) -> Generator[bool, None, None]:
    yield context.active_object is not None
    gear_props = getattr(context.active_object, config.PROPS_ALIAS)
    yield gear_props.is_fastener
    yield context.mode == "OBJECT"


def create_new_fastener(fastener_type: str, xform: Matrix = Matrix.Identity(4)) -> Object:
    """ Create new fastener object """
    if fastener_type not in config.FASTENER_TYPES:
        raise ValueError(f"{fastener_type} not in {config.FASTENER_TYPES}")

    # Create placeholder object
    fastener_mesh = mesh_gen.new_grid_mesh("placeholder", transform=xform)

    needs_4_1_0_api_change = bpy.app.version[0] >= 4 and bpy.app.version[1] > 0
    if not needs_4_1_0_api_change:
        fastener_mesh.use_auto_smooth = True

    fastener_name = fastener_type.title()
    fastener_obj = bpy.data.objects.new(
        name=f"{fastener_name}", object_data=fastener_mesh
    )

    # Add custom property used to identify a gear objet
    fastener_props = getattr(fastener_obj, config.PROPS_ALIAS)
    fastener_props.is_fastener = True

    with PropsUpdateDisabled(fastener_props) as paused_props:
        paused_props.fastener_type = fastener_type

    builder_class = fasteners.builders[fastener_type]
    builder = builder_class(fastener_props)

    builder.set_prop_defaults()
    return fastener_obj


def make_fastener_counterpart(source: Object, target: Object) -> None:
    """ Make target fastener compatible with source fastener """
    source_props = getattr(source, config.PROPS_ALIAS)
    target_props = getattr(target, config.PROPS_ALIAS)
    match_props = (
        "custom_thread_profile",
        # "thread_type",
        "thread_resolution",
        "pitch",
        "starts",
        "thread_angle",
        "major_diameter",
        "minor_diameter",
        "crest_weight",
        "root_weight",
    )

    with PropsUpdateDisabled(target_props) as paused_props:
        for key in match_props:
            value = getattr(source_props, key)
            setattr(paused_props, key, value)

        if source_props.fastener_type in {"THREADED_ROD", "BOLT"}:
            target_props.nut_diameter = source_props.major_diameter * 2
            target_props.length = source_props.length / 2
        else:
            target_props.length = source_props.length * 2


class OBJECT_OT_test_operator(Operator):
    bl_idname = "object.fasteners_debug_operator"
    bl_label = "FASTENERS TESTING OPERATOR"
    bl_description = "NOTHING"
    bl_options = {"REGISTER", "UNDO"}

    def test_func(self, context: Context):
        csv = config.USER_PRESETS_DIR / "BOLT/STANDARD_THREAD/metric_threads.csv"
        presets.validate_csv(csv)

    def execute(self, context: Context):
        try:
            self.test_func(context)
        except Exception as e:
            print(e)
        return {"FINISHED"}


class OBJECT_OT_add_new_fastener(Operator):
    bl_idname: str = idnames.get_caller_idname()
    bl_label = "Add Fastener"
    bl_description = "Add a New Fastener"
    bl_options = {"REGISTER", "UNDO"}

    fastener_type: EnumProperty(items=properties.FASTENERS_ENUM)

    def draw(self, context: Context):
        layout = self.layout
        layout.label(text="Edit Fastener in Object Data Panel")

    def execute(self, context: Context):
        # xform = context.scene.cursor.matrix
        fastener_obj = create_new_fastener(self.fastener_type)

        # Link in context
        # fastener_obj.matrix_world = context.scene.cursor.matrix
        fastener_obj.location = context.scene.cursor.location

        # Link to scene and select
        context.collection.objects.link(fastener_obj)
        context.view_layer.objects.active = fastener_obj
        deselect_all(context)
        fastener_obj.select_set(True)

        fastener_props = getattr(fastener_obj, config.PROPS_ALIAS)
        fasteners.update_fastener(fastener_props, context)

        # Set default thumb path
        fastener_props.preset_category = fastener_props.preset_category
        return {"FINISHED"}


class OBJECT_OT_create_fastener_counterpart(Operator):
    bl_idname: str = idnames.get_caller_idname()
    bl_label = "Create Counterpart"
    bl_description = "Create Counterpart"
    bl_options = {"REGISTER", "UNDO"}

    def draw(self, context: Context):
        layout = self.layout
        layout.label(text="Edit Fastener in Object Data Panel")

    @classmethod
    def poll(cls, context):
        return all(is_active_fastener(context))

    def execute(self, context: Context):
        source_fastener: Object = context.object
        source_props = getattr(context.object, config.PROPS_ALIAS)
        source_type = source_props.fastener_type
        valid_types = ("NUT", "BOLT", "THREADED_ROD")
        if source_type not in valid_types:
            self.report(type={"ERROR"}, message="No Counterpart for Screw")
            return {"CANCELLED"}
        counterpart = {
            "NUT": "BOLT",
            "BOLT": "NUT",
            "THREADED_ROD": "NUT",
        }[source_type]

        counterpart = create_new_fastener(counterpart)
        # counterpart.location = source_fastener.location
        counterpart.matrix_world = source_fastener.matrix_world

        # Link to scene
        context.collection.objects.link(counterpart)
        context.view_layer.objects.active = counterpart
        deselect_all(context)
        counterpart.select_set(True)

        counterpart_props = getattr(counterpart, config.PROPS_ALIAS)
        fasteners.update_fastener(counterpart_props, context)

        # Assign appropriate attribs
        make_fastener_counterpart(source_fastener, counterpart)
        fasteners.update_fastener(counterpart_props, context)
        return {"FINISHED"}


def _load_thread_definitions(source: Path):
    def _load_preset(csv_dict: dict) -> str:
        """ Create json encoded dict of preset values """
        fields = {"thread_name": str, "major_diameter": float, "pitch": float, "thread_type": str}
        return {
            field: field_type(csv_dict[field]) for field, field_type in fields.items()
        }

    with open(source, "r") as thread_table:
        fieldnames = thread_table.readline().rstrip("\n").split(",")
        reader = DictReader(thread_table, fieldnames=fieldnames)
        for line in reader:
            yield _load_preset(line)


def _load_general_preset_definitions(source: Path):
    with open(source, "r") as thread_table:
        fieldnames = thread_table.readline().rstrip("\n").split(",")
        reader = DictReader(thread_table, fieldnames=fieldnames)
        for line in reader:
            if line.get("preset_name") is None:
                line["preset_name"] = source.stem
            yield line


def _get_thread_definition(thread_name: str, source_file: Path):
    definitions = _load_thread_definitions(source_file)
    return next(filter(lambda d: d["thread_name"] == thread_name, definitions))


def _load_general_presets_enum(source: Path) -> List[Tuple[str, str, str]]:
    preset_files = source.glob("*.csv")
    presets = (_load_general_preset_definitions(f) for f in preset_files)
    for preset in chain.from_iterable(presets):
        thread_preset_val = preset.get("thread_preset", None)
        if thread_preset_val is not None and thread_preset_val != "":
            thread_preset = _get_thread_definition(
                preset["thread_preset"], config.METRIC_THREADS_FILE
            )
            preset.update(thread_preset)

        # Type values
        # TODO: this is bad
        for key, value in preset.items():
            try:
                cast = PRESET_TYPES[key]
                if cast != bool:
                    preset[key] = cast(value)
                else:
                    if value.lower() == "false":
                        preset[key] = False
                    else:
                        preset[key] = True
            except:
                continue

        try:
            name = preset["preset_name"]
            encoded = json.dumps(preset)
            yield encoded, name, name
        except KeyError:
            continue


def _thread_definitions_enum(source: Path) -> Generator[Tuple[str, str, str], None, None]:
    """ Return json encoded thread definitions in prop enum"""
    thread_definitions = _load_thread_definitions(source)
    for definition in thread_definitions:
        name = definition["thread_name"]
        description = name
        value = json.dumps(definition)
        yield value, name, description


def show_ui_message_popup(
    message: str = "", title: str = "Precision Gears", icon: str = "INFO"
):
    """ Trigger a ui popup message """

    def draw(self, context: Context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


class OBJECT_OT_apply_preset_filter(bpy.types.Operator):
    """ Load threads preset and apply """

    bl_idname = "object.apply_fastener_preset_filter"
    bl_label = "Apply Fastener Preset Filter"
    bl_property = "preset"
    preset: bpy.props.EnumProperty(items=properties.populate_thumb_enum)

    def invoke(self, context: Context, event: Event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

    def execute(self, context: Context):
        props: FastenerProps  = getattr(context.active_object, config.PROPS_ALIAS)
        props.preset_filter = self.preset
        props.preset_thumbnail = self.preset
        props.apply_preset_filter = True
        return {"FINISHED"}


class RENDER_OT_generate_bolt_thumbnails(bpy.types.Operator):
    """ Async generate thumbnails in background subprocess """
    bl_idname = idnames.auto_operator_idname()
    bl_label = "Generate Precision Bolts Thumbnails"

    async def generate_thumbs(self):
        await presets.generate_thumbnails()

    @staticmethod
    def _completion_callback(props: FastenerProps, _):
        # show_ui_message_popup("Thumbnail Render Complete")
        # properties.trigger_preset_refresh(props)
        props.thumb_rendering = False
        pass

    def execute(self, context: Context):
        self.report({"INFO"}, "Generating thumbnails")

        props = getattr(context.active_object, config.PROPS_ALIAS)
        props.thumb_rendering = True
        async_task = asyncio.ensure_future(self.generate_thumbs())
        callback = partial(self._completion_callback, props)
        async_task.add_done_callback(callback)
        async_loop.ensure_async_loop()
        return {"FINISHED"}


class OBJECT_OT_save_fastener_preset(bpy.types.Operator):
    """ Save fastener fastener preset """
    bl_idname = idnames.auto_operator_idname()
    bl_label = "Save Fastener Preset"

    preset_name: StringProperty(name="Preset Name", default="", options={"SKIP_SAVE"})
    fastener_type: EnumProperty(items=properties.FASTENERS_ENUM, options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context: Context, event: Event):
        if not all(polls.is_active_fastener(context)):
            self.report({"ERROR"}, "Active object is not a fastener")
            return {"CANCELLED"}
        self.fastener = context.active_object
        self.props: FastenerProps = getattr(self.fastener, config.PROPS_ALIAS)
        self.fastener_type = self.props.fastener_type
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: Context) -> Set[str]:
        if self.preset_name == "":
            self.report({"ERROR"}, "No valid name provided")
            return {"CANCELLED"}


        category_tests = {
            "FULL": self.props.preset_save_component_full,
            "THREAD": self.props.preset_save_component_thread,
            "DRIVER": self.props.preset_save_component_driver,
            "HEAD": self.props.preset_save_component_head,
        }

        categories = []
        for category, toggled in category_tests.items():
            if toggled:
                categories.append(category)
            
        for cat in categories:
            self.write_preset(cat)
        
        # presets.clear_caches()
        bpy.ops.render.generate_bolt_thumbnails()
        return {"FINISHED"}

    def write_preset(self, category: str):
        prop_names = config.FASTENER_PROP_GROUPINGS.get(category)
        output_dir: Path = config.USER_PRESETS_DIR / self.fastener_type / category
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = (output_dir / self.preset_name).with_suffix(".csv")

        if output_path.exists():
            self.report({"ERROR"}, f"{output_path} already exists")
            return None

        with open(output_path, "w") as preset_file:
            preset = {key: getattr(self.props, key) for key in prop_names}
            # preset_name = f"{self.preset_name}_"
            preset = dicttoolz.merge({"preset_name": self.preset_name}, preset)
            preset["thumb"] = bpy.path.clean_name(self.preset_name)
            writer = DictWriter(preset_file, fieldnames=preset.keys())
            writer.writeheader()
            writer.writerow(preset)


class OBJECT_OT_apply_fastener_preset(bpy.types.Operator):
    """ Apply fastener preset """
    bl_idname = idnames.auto_operator_idname()
    bl_label = "Apply Fastener Preset"

    @classmethod
    def poll(cls, context: Context):
        if not all(polls.is_active_fastener(context)):
            return False
        return True

    def execute(self, context: Context):
        fastener = context.active_object
        props: FastenerProps = getattr(fastener, config.PROPS_ALIAS)
        preset_name = props.preset_thumbnail
        preset_dir = config.USER_PRESETS_DIR / props.fastener_type / props.preset_category
        try:
            preset = presets.find_preset_by_name(preset_name, preset_dir)
            preset.pop('preset_name')
            with PropsUpdateDisabled(props):
                for key, value in preset.items():
                    setattr(props, key, value)
            props.fastener_type = props.fastener_type

        except ValueError:
            self.report({"ERROR"}, "No preset file found for the thumbnail")
            return {"CANCELLED"}

        return {"FINISHED"}


# class OBJECT_OT_save_fastener_preset(bpy.types.Operator):
#     """ Save fastener preset threads preset and apply """
#     bl_idname = idnames.get_caller_idname()
#     bl_label = "Save Fastener Preset"

#     preset_name: StringProperty(name="Preset Name", default="")
#     fastener_type: EnumProperty(items=props.FASTENERS_ENUM, options={"HIDDEN"})

#     def invoke(self, context: Context, event: Event):
#         if not all(polls.is_active_fastener(context)):
#             self.report({"ERROR"}, "Active object is not a fastener")
#             return {"CANCELLED"}
#         fastener = context.active_object
#         props: props.FastenerProps = getattr(fastener, config.PROPS_ALIAS)
#         self.fastener_type = props.fastener_type
#         return context.window_manager.invoke_props_dialog(self)

#     @property
#     def preset_path(self) -> Path:
#         return config.PRESETS_DIR / self.fastener_type / (self.preset_name + ".csv")

#     def ensure_output_directory(self):
#         preset_root = config.PRESETS_DIR
#         preset_root.mkdir(exist_ok=True)
#         preset_directory = preset_root / self.fastener_type
#         preset_directory.mkdir(exist_ok=True)

#     def execute(self, context: Context) -> Set[str]:
#         if self.preset_name == "":
#             self.report({"ERROR"}, "No valid name provided")
#             return {"CANCELLED"}

#         if self.preset_path.exists():
#             self.report({"ERROR"}, f"{self.preset_path} already exists")
#             return {"CANCELLED"}

#         self.ensure_output_directory()

#         fastener = context.active_object
#         props = getattr(fastener, config.PROPS_ALIAS)
#         builder = fasteners.builders[self.fastener_type]

#         # Get used props and their values
#         prop_keys = list(props.bl_rna.properties.keys())

#         with open(self.preset_path, "w") as preset_file:
#             keys = []
#             prop_groups = builder.prop_groups
#             for grp in prop_groups:
#                 for key, _ in grp[1].items():
#                     keys.append(key)

#             if builder.heads is not None:
#                 keys += [key for key in prop_keys if key.startswith("head_")]

#             if builder.drivers is not None:
#                 keys += [key for key in prop_keys if key.startswith("driver")]

#             preset = {key: getattr(props, key) for key in keys}

#             writer = DictWriter(preset_file, fieldnames=preset.keys())
#             writer.writeheader()
#             writer.writerow(preset)

#         return {"FINISHED"}


class WM_OT_bolts_open_sys_folder(bpy.types.Operator):
    """ Save fastener preset threads preset and apply """
    bl_idname = idnames.get_caller_idname()
    bl_label = "Open System Folder"

    folder: StringProperty(default="")

    def execute(self, context: Context):
        folder = os.path.realpath(self.folder)
        if not os.path.isdir(folder):
            self.report({"WARNING"}, f"{folder} not a directory")
            return {"CANCELLED"}
        system = platform.system()
        if system == "Darwin":
            subprocess.call(("open", folder))
        elif system == "Windows":
            os.startfile(folder)
        else:
            subprocess.call(("xdg-open", folder))
        return {"FINISHED"}


operators = (
    # OBJECT_OT_test_operator,
    OBJECT_OT_apply_preset_filter,
    WM_OT_bolts_open_sys_folder,
    RENDER_OT_generate_bolt_thumbnails,
    OBJECT_OT_add_new_fastener,
    OBJECT_OT_create_fastener_counterpart,
    # OBJECT_OT_load_bolt_preset,
    # OBJECT_OT_load_threaded_rod_preset,
    # OBJECT_OT_load_screw_preset,
    # OBJECT_OT_load_nut_preset,
    # OBJECT_OT_apply_thread_preset,
    # OBJECT_OT_save_fastener_preset,
    OBJECT_OT_save_fastener_preset,
    OBJECT_OT_apply_fastener_preset,
)


def register():
    for op in operators:
        bpy.utils.register_class(op)


def unregister():
    for op in operators:
        bpy.utils.unregister_class(op)


if __name__ == "__main__":
    register()
