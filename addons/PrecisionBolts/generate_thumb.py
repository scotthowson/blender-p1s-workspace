""" Render client run by thumbnail generator in presets.py """

from functools import partial
import sys
from typing import Any, Dict, Iterable
from pathlib import Path
import collections
from itertools import islice
import pickle
import asyncio
from dataclasses import dataclass

import bpy
from bpy.types import Object, PropertyGroup
import addon_utils


PROP_GROUP_ALIAS = "fastener_props"
ADDON_NAME = "PrecisionBolts"


def install_addons(addon_zips: Iterable[Path]):
    init_modules = set(addon_utils.modules()[:])
    for zipfile in addon_zips:
        print(f"installing {zipfile}")
        bpy.ops.preferences.addon_install(filepath=str(zipfile))

    addon_utils.modules_refresh()


def enable_addon():
    print("Ensuring Precision Bolts addon enabled")
    addon_utils.enable(ADDON_NAME)


def string_to_hex(input: str) -> str:
    return input.encode("utf-8").hex()


def hex_to_string(input: str) -> str:
    return bytes.fromhex(input).decode("utf-8")


@dataclass
class RenderJob:
    fastener_type: str
    preset_type: str
    presets: Dict[str, Dict[str, Any]]
    output_path: Path
    resolution: int

    def __post_init__(self):
        self.preset_type = self.preset_type.replace("STANDARD_", "")


class PropsUpdateDisabled:
    def __init__(self, props: PropertyGroup):
        self.props = props

    def __enter__(self):
        self.props.editing = True
        return self.props

    def __exit__(self, *args):
        self.props.editing = False


def consume(iterator, n=None):
    "Advance the iterator n-steps ahead. If n is None, consume entirely."
    # Use functions that consume iterators at C speed.
    if n is None:
        # feed the entire iterator into a zero-length deque
        collections.deque(iterator, maxlen=0)
    else:
        # advance to the empty slice starting at position n
        next(islice(iterator, n, n), None)


def revert_scene():
    bpy.ops.wm.revert_mainfile()


def normalize_scale(obj: Object) -> None:
    """Normalize object dimensions through uniform scale"""
    max_dim = max(obj.dimensions)
    obj.dimensions = obj.dimensions * (1 / max_dim)


def offset_by_half_z(obj: Object) -> None:
    """Quick and dirty object centering"""
    mid_z = obj.dimensions.z
    obj.location.z = -mid_z / 2


def prop_overrides(preset_type: str, prop_group: PropertyGroup) -> None:
    """Prop overrides based on preset type"""
    if preset_type == "THREAD":
        prop_group.head_type = None
        prop_group.driver_type = None
    elif preset_type == "HEAD":
        prop_group.driver_type = None
        prop_group.length = 0.00001
    elif preset_type == "DRIVER":
        prop_group.head_type = "HEX"
        prop_group.length = 0.00001


def remove_placeholder_objects(keep: str = ""):
    template_objects = {
        "camera",
        "ground",
        str.lower(keep),
    }

    def _is_extra(obj):
        return str.lower(obj.name) not in template_objects

    extra_objs = filter(_is_extra, bpy.data.objects)
    remove_extras = map(bpy.data.objects.remove, extra_objs)
    consume(remove_extras)


async def request_presets(ip: str, port: int, preset_type):
    reader, writer = await asyncio.open_connection(ip, port)
    print("CLIENT:Requesting Job")
    writer.write(preset_type.encode())
    await writer.drain()

    message = await reader.read()
    message = pickle.loads(message)
    print(f"CLIENT:Received response")
    writer.close()
    await writer.wait_closed()
    return message


def get_prop_group(obj: Object) -> PropertyGroup:
    return getattr(obj, PROP_GROUP_ALIAS)


def apply_preset(prop_group: Object, preset: Dict[str, Any], preset_type: str):
    with PropsUpdateDisabled(prop_group):
        for prop_name, value in preset.items():
            setattr(prop_group, prop_name, value)

    # Trigger update
    prop_group.scale = prop_group.scale


def apply_preset_type_overrides(
    prop_group: PropertyGroup, fastener_type: str, preset_type: str
):
    # print(fastener_type.lower(), preset_type.lower())
    if fastener_type.lower() in {"bolt", "screw"}:
        if preset_type.lower() == "head":
            prop_group.length = 0.0001
        elif preset_type.lower() == "thread":
            prop_group.head_type = "NONE"
            prop_group.driver_type = "NONE"
            prop_group.shank_length = 0
            prop_group.length = prop_group.pitch * 5
        elif preset_type.lower() == "driver":
            prop_group.head_type = "HEX"
            prop_group.length = 0.0001
            prop_group.major_diameter = 0.0001
            prop_group.head_length = prop_group.driver_depth * 3
            if prop_group.driver_type == "CROSS":
                driver_diameter = max(
                    prop_group.driver_mod_a,
                    prop_group.driver_mod_b,
                    prop_group.driver_mod_c,
                    prop_group.driver_mod_d,
                )
                prop_group.head_diameter = driver_diameter * 1.4
            elif prop_group.driver_type == "POLYGON":
                prop_group.head_diameter = prop_group.driver_diameter * 1.4
            elif prop_group.driver_type == "SLOTTED":
                driver_diameter = max(
                    prop_group.driver_mod_a,
                    prop_group.driver_mod_b,
                )
                prop_group.head_diameter = driver_diameter * 1.4

    elif fastener_type.lower() in {"nut"}:
        if preset_type.lower() == "thread":
            prop_group.fastener_type = "BOLT"
            prop_group.head_type = "NONE"
            prop_group.shank_length = 0
            prop_group.length = prop_group.pitch * 5


def generate_thumbnails(job: RenderJob, save_debug: bool = False):
    print(f"Generating thumbnails for {job.fastener_type}:{job.preset_type}")
    for preset_name, preset in job.presets.items():
        # # Set render path
        # name_as_hex = string_to_hex(preset_name)
        output_path = str(job.output_path / bpy.path.clean_name(preset_name))
        # print(output_path)
        if Path(output_path).with_suffix(".png").exists():
            print(f"{output_path}.png already exists, skipping")
            continue

        view_layer = bpy.context.view_layer
        remove_placeholder_objects(keep=job.fastener_type)
        target_object = view_layer.objects.get(str.title(job.fastener_type))
        prop_group = get_prop_group(target_object)

        apply_preset(prop_group, preset, job.preset_type)
        apply_preset_type_overrides(prop_group, job.fastener_type, job.preset_type)

        bpy.context.view_layer.update()

        try:
            normalize_scale(target_object)
        except ZeroDivisionError:
            print("Normalization Error", job)
            pass
            # return None

        bpy.context.view_layer.update()

        # # Quick and dirty censoring
        offset_by_half_z(target_object)

        # output_path = f"/tmp/_blah/{preset_name}"
        bpy.context.scene.render.resolution_x = job.resolution
        bpy.context.scene.render.resolution_y = job.resolution
        bpy.context.scene.render.filepath = output_path

        # # Run render
        bpy.ops.render.render(write_still=True)
        if save_debug:
            debug_path = output_path + ".blend"
            print(f"Saving debug file to {debug_path}")
            bpy.ops.wm.save_as_mainfile(filepath=debug_path, copy=True)
        revert_scene()
        yield output_path


def run(ip: str = "127.0.0.1", port: int = 8888, save_debug: bool = False):
    enable_addon()
    # Request a preset
    print("RENDER CLIENT STARTING")
    preset_request = partial(request_presets, ip, port, "REQUEST:JOB")
    response = asyncio.run(preset_request())
    # print(response)
    while response != "TERMINATE":
        job = RenderJob(*response)
        results = [image for image in generate_thumbnails(job, save_debug)]
        if None in results:
            print(f"Error encountered rendering thumb for {job}")
        response = asyncio.run(preset_request())
    print("RENDER CLIENT TERMINATING")


if __name__ == "__main__":
    ip = sys.argv[-2]
    port = int(sys.argv[-1])
    run(ip, port, save_debug=False)
