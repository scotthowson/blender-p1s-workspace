"""
NOTE: This sucks. Nothing here should be used directly
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from csv import DictReader
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import List, NamedTuple, Any, Union, TYPE_CHECKING, Dict

import bpy
from bpy.types import Mesh, Object, UILayout
from mathutils import Vector
import bmesh
from bmesh.types import BMesh, BMLayerItem, BMVert
from bmesh.types import BMEdge, BMFace
import numpy as np

from .bmesh_filters import dict_by_type, unique_edge_verts
from . import bmesh_helpers
from .preset_field_types import PRESET_TYPES
from .bmesh_helpers import temp_subd_modifier
from .toolz import dicttoolz
from . import config


from .config import DEFAULTS_DIR

if TYPE_CHECKING:
    from .properties import FastenerProps


class PropsUpdateDisabled:
    def __init__(self, props: FastenerProps):
        self.props = props

    def __enter__(self):
        self.props.editing = True
        return self.props

    def __exit__(self, *args):
        self.props.editing = False


class EditMesh:
    def __init__(self, mesh: Mesh):
        self.mesh = mesh
        self.bm = bmesh.new()

    def __enter__(self):
        self.bm.from_mesh(self.mesh)
        return self.bm

    def __exit__(self, *args):
        self.bm.to_mesh(self.mesh)
        self.bm.free()


class PropertyMapping(NamedTuple):
    name: str  # Name of arg to use prop as on calculate function
    default: Any = None
    min_val: Union[None, Any] = None
    max_val: Union[None, Any] = None
    newline: bool = True


class FastenerDriver(ABC):
    type: str
    props: FastenerProps
    mesh_source: Union[None, MeshReader] = None
    bm: BMesh = field(init=False)

    def __post_init__(self):
        self.bm = bmesh.new()
        if self.mesh_source is not None:
            with self.mesh_source() as head_datablock:
                self.bm.from_mesh(head_datablock)

    @abstractmethod
    def apply_transforms(self) -> None:
        ...

    @property
    def object(self) -> Object:
        mesh = self.mesh
        obj = bpy.data.objects.new(self.type, object_data=self.mesh)

    @property
    def mesh(self) -> Mesh:
        mesh = bpy.data.meshes.new(self.type)
        self.bm.to_mesh(mesh)
        return mesh


@dataclass
class FastenerVertLayers:
    bm: BMesh
    thread_roots: BMLayerItem = field(init=False)
    thread_crests: BMLayerItem = field(init=False)

    def __post_init__(self):
        self.thread_roots = self._initalize_layer("thread_roots")
        self.thread_crests = self._initalize_layer("thread_crests")

    def _initalize_layer(self, name):
        return self.bm.verts.layers.int.new(name)


class Fastener(ABC):
    props: FastenerProps
    type: str
    bm: BMesh = field(init=False)
    heads: Union[Dict[str, FastenerHead], None] = None
    drivers: Union[Dict[str, FastenerDriver], None] = None
    type_props: Union[dict[str, PropertyMapping], None] = None
    general_props: Union[dict, None] = None
    vert_layers: FastenerVertLayers = field(init=False)
    driver_compatible: bool = False
    custom_thread_props: Union[dict, None] = None
    standard_thread_props: Union[dict, None] = None

    def __post_init__(self):
        self.bm = bmesh.new()
        self.vert_layers = FastenerVertLayers(self.bm)

    def _vert_by_layer_val(self, layer: BMLayerItem, val=1):
        return [vert for vert in self.bm.verts if vert[layer] == val]

    def _create_shank(self, edges: Union[List[BMEdge], None]) -> List[BMEdge]:
        extrusion = bmesh.ops.extrude_edge_only(self.bm, edges=edges)["geom"]
        extrusion = dict_by_type(extrusion)

        init_verts = unique_edge_verts(edges)
        extrusion_verts = extrusion[BMVert]

        for vert in extrusion_verts:
            xy: Vector = vert.co.xy
            mag = xy.length
            vert.co.xy = xy.normalized() * (self.major_radius + self.props.runout_offset)

        for vert in init_verts:
            xy: Vector = vert.co.xy
            vert.co.xy = xy.normalized() * self.major_radius

        if self.props.runout_length != 0:
            runout_edges = extrusion[BMEdge]
            runout_verts = extrusion[BMVert]
            extrusion = bmesh.ops.extrude_edge_only(self.bm, edges=runout_edges)["geom"]
            extrusion = dict_by_type(extrusion)
            for vert in runout_verts:
                vert.co.z += self.props.runout_length

        for vert in extrusion[BMVert]:
            vert.co.z += self.props.shank_length - self.props.tolerance

        return extrusion[BMEdge]

    @property
    def major_radius(self) -> float:
        return self.props.major_diameter / 2 - self.props.tolerance

    @property
    def default_values(self) -> Union[Dict, None]:
        defaults_path = DEFAULTS_DIR / self.type / "Default.csv"
        if not defaults_path.exists():
            return {}

        defaults = {}
        with open(defaults_path, "r") as defaults_reader:
            fieldnames = next(defaults_reader).rstrip("\n").split(",")
            reader = DictReader(defaults_reader, fieldnames=fieldnames)
            defaults_line = next(reader)

            for key, value in defaults_line.items():
                try:
                    cast = PRESET_TYPES[key]
                    if cast != bool:
                        defaults.setdefault(key, cast(value))
                    else:
                        if value.lower() == "false":
                            defaults.setdefault(key, False)
                        else:
                            defaults.setdefault(key, True)
                except KeyError:
                    continue

        return defaults

    def trim(self) -> None:
        """Mirrored mesh trimming through bisection and capping"""
        trim_fac = self.props.trim
        min_x_vert, max_x_vert = bmesh_helpers.min_max_verts(self.bm.verts, axis="x")
        min_x, max_x = min_x_vert.co.x, max_x_vert.co.x
        x_len = abs(min_x - max_x)
        trim_len = x_len * (1 - (trim_fac / 2))

        cut_locs = (Vector((min_x + trim_len, 0, 0)), Vector((max_x - trim_len, 0, 0)))
        cut_norms = (Vector((1, 0, 0)), Vector((-1, 0, 0)))
        for loc, norm in zip(cut_locs, cut_norms):
            geom = bmesh_helpers.bm_as_list(self.bm)
            trimmed = bmesh.ops.bisect_plane(
                self.bm, geom=geom, clear_outer=True, plane_co=loc, plane_no=norm
            )

            cut = dict_by_type(trimmed["geom_cut"])
            if BMVert not in cut.keys():
                continue

            edges = bmesh_helpers.shared_edges(cut[BMVert])
            fills = bmesh.ops.holes_fill(self.bm, edges=edges)
            bmesh.ops.triangulate(self.bm, faces=fills["faces"])
            bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.00001)

    @classmethod
    @property
    def prop_groups(cls) -> List[Dict[str, PropertyMapping]]:
        prop_groups = []
        attr_names = [attrib for attrib in dir(cls) if attrib.endswith("_props")]
        grp_names = [attr.replace("_props", "").title() for attr in attr_names]
        for name, grp in zip(grp_names, attr_names):
            attr = getattr(cls, grp)
            if callable(attr):
                continue
            group = (name, attr)
            prop_groups.append(group)
        return prop_groups

    def set_prop_defaults(self):
        """Set the values in prop group based on cls.properties"""
        defaults_file_values = self.default_values
        prop_keys = self.props.bl_rna.properties.keys()

        with PropsUpdateDisabled(self.props):
            for key, value in self.default_values.items():
                try:
                    setattr(self.props, key, value)
                except Exception as e:
                    print(e)
                    continue

    def _scale(self):
        scale = Vector.Fill(3, self.props.scale)
        bmesh.ops.scale(self.bm, vec=scale, verts=self.bm.verts)

    @classmethod
    def get_prop_map(cls) -> Dict[str, PropertyMapping]:
        """
        List of properties from active gear to use and their constraints
        """
        prop_map = {}
        for _, prop_group in cls.prop_groups:
            if prop_group is None:
                continue
            prop_map.update(prop_group)
        return prop_map

    @abstractmethod
    def create(self, mesh: Mesh) -> Mesh:
        raise NotImplementedError

    def _adjust_tolerance(self):
        return None
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        for vert in self.bm.verts:
            vert.co += vert.normal * self.props.tolerance

    @classmethod
    def _draw_prop_set(cls, layout, prop_set: dict, prop_grp: FastenerProps, label=""):
        if prop_set is None:
            return None

        row = layout.row()
        box = row.box()
        col = box.column(align=True)
        if label != "":
            col.label(text=label)
        for key, prop_mapping in prop_set.items():
            if prop_mapping.newline:
                row = col.row()
            row.prop(prop_grp, key, text=prop_mapping.name)

    @classmethod
    def _draw_thread_props(
        cls, layout, prop_set: dict, prop_grp: FastenerProps, label=""
    ):
        if prop_set is None:
            return None

        row = layout.row()
        box = row.box()
        col = box.column(align=True)
        if label != "":
            col.label(text=label)
        for key, prop_mapping in prop_set.items():
            if prop_mapping.newline:
                row = col.row()
            row.prop(prop_grp, key, text=prop_mapping.name)

    @classmethod
    def _draw_general_props(
        cls, layout, prop_set: dict, prop_grp: FastenerProps, label=""
    ):
        if prop_set is None:
            return None

        row = layout.row()
        box = row.box()
        col = box.column(align=True)
        if label != "":
            col.label(text=label)
        for key, prop_mapping in prop_set.items():
            if prop_mapping.newline:
                row = col.row()
            row.prop(prop_grp, key, text=prop_mapping.name)

    @classmethod
    def draw(cls, layout: UILayout, props: FastenerProps):
        cls._draw_presets(layout, props)

        # TODO: Thread prop handling could certainly be cleaner
        if cls.custom_thread_props is not None:
            if props.custom_thread_profile:
                thread_props = dicttoolz.merge(cls.custom_thread_props, cls.type_props)
            else:
                thread_props = dicttoolz.merge(
                    cls.standard_thread_props, cls.type_props
                )
        else:
            thread_props = cls.type_props

        # cls._draw_thread_props(layout, thread_props, props, cls.type.title())
        cls._draw_thread_props(layout, thread_props, props, "Thread")
        cls._draw_head_ui(layout, props)
        cls._draw_general_props(layout, cls.general_props, props, "General")

    @classmethod
    def _draw_presets(cls, layout: UILayout, prop_grp: FastenerProps):
        row = layout.row()
        box = row.box()
        col = box.column(align=True)
        col.label(text="Presets")

        # Presets Row
        row = col.row(align=True)

        # Thumb Presets Row
        row = col.row(align=True)
        col = box.column(align=True)
        row = col.row(align=True)
        row.prop(prop_grp, "preset_category", text="")

        apply_filter = getattr(prop_grp, "apply_preset_filter")

        if apply_filter:
            row.prop(prop_grp, "apply_preset_filter", icon="VIEWZOOM", text="")
        else:
            row.operator(
                "object.apply_fastener_preset_filter", icon="VIEWZOOM", text=""
            )

        save_preset = row.operator(
            "object.save_fastener_preset", icon="PRESET_NEW", text=""
        )

        # Oper User Preset Folder
        open_folder = row.operator(
            "wm.bolts_open_sys_folder", icon="FILE_FOLDER", text=""
        )
        folder = config.USER_PRESETS_DIR
        open_folder.folder = str(folder)

        # Open user website
        open_store = row.operator("wm.url_open", icon="URL")
        open_store.url = "https://makertales.gumroad.com/"

        refresh_preset = row.operator(
            "render.generate_bolt_thumbnails", icon="FILE_REFRESH", text=""
        )

        if apply_filter:
            row = box.row()
            row.prop(prop_grp, "preset_filter", icon="VIEWZOOM", text="")

        row = box.row()
        row.template_icon_view(prop_grp, "preset_thumbnail", show_labels=True, scale=7)
        row = box.row()
        if prop_grp.thumb_rendering:
            row.label(text="Thumbnail Rendering in Progress, please wait.")
        row = box.row()
        row.operator("object.apply_fastener_preset", text="Apply Preset")
        row = box.row()
        row.operator("object.create_fastener_counterpart")

        box.label(text="Create Preset")

        # NOTE: This is gross, I shoudn't be refering to child classes
        row = box.row(align=True)
        if cls.type in {"BOLT", "SCREW"}:
            row.prop(prop_grp, "preset_save_component_full", text="Full")
            row.prop(prop_grp, "preset_save_component_thread", text="Thread")
            row.prop(prop_grp, "preset_save_component_head", text="Head")
            row.prop(prop_grp, "preset_save_component_driver", text="Driver")
        else:
            row.prop(prop_grp, "preset_save_component_full", text="Full")
            row.prop(prop_grp, "preset_save_component_thread", text="Thread")

        row = box.row(align=True)
        save_preset = row.operator("object.save_fastener_preset", text="Save Preset")

    @classmethod
    def _draw_head_ui(cls, layout: UILayout, prop_grp: FastenerProps):
        if cls.heads is None:
            return None

        row = layout.row()
        box = row.box()
        col = box.column(align=True)
        col.label(text="Head and Driver")

        # Draw head props
        col = box.column(align=True)
        col.prop(prop_grp, "head_type", text="Head")
        head: FastenerHead = cls.heads.get(prop_grp.head_type, None)
        common_props = ("head_length", "head_diameter", "head_subdiv")
        if head is not None:
            for name in common_props:
                col.prop(prop_grp, name)
            if prop_grp.head_type != "NONE":
                for key, mapping in head.prop_map.items():
                    col.prop(prop_grp, key, text=mapping.name)

        col = box.column(align=True)
        col.prop(prop_grp, "driver_type", text="Driver")
        driver: FastenerDriver = cls.drivers.get(prop_grp.driver_type, None)
        common_props = ("driver_depth",)
        if driver is not None:
            for name in common_props:
                col.prop(prop_grp, name)
            if prop_grp.driver_type != "NONE":
                for key, mapping in driver.prop_map.items():
                    col.prop(prop_grp, key, text=mapping.name)


class FastenerHead:
    type: str
    props: FastenerProps
    mesh_source: MeshReader
    bm: BMesh = field(init=False)
    type_mod_a: Union[None, str] = None
    type_mod_b: Union[None, str] = None

    def __post_init__(self):
        self.bm = bmesh.new()
        with self.mesh_source() as head_datablock:
            self.bm.from_mesh(head_datablock)

    def apply_transforms(self) -> None:
        self._apply_type_transforms()
        subdiv = self.props.head_subdiv
        if subdiv > 0:
            temp_subd_modifier(self.bm, subdiv)

    def _apply_common_transforms(self) -> None:
        """Apply common transforms"""
        # Root scale
        bm = self.bm
        xy_scale = self.props.head_diameter
        # z_scale = self.props.head_length - self.props.tolerance
        z_scale = self.props.head_length
        scaler = Vector((xy_scale, xy_scale, z_scale))
        bmesh.ops.scale(bm, verts=bm.verts, vec=scaler)

        # z_offset = Vector((0, 0, self.props.length - self.props.tolerance))
        z_offset = Vector((0, 0, self.props.length))
        bmesh.ops.translate(bm, vec=z_offset, verts=bm.verts)

    def _apply_type_transforms(self) -> None:
        """Apply per type transforms"""
        return None


class MeshReader:
    """
    Mesh datablock reader.
    When used in a context manager will remove after completion
    """

    def __init__(self, mesh_name: str, blend: Path):
        self.mesh_name = mesh_name
        self.blend = blend
        self.datablock: Union[None, Mesh] = None

    def __enter__(self):
        self.datablock = self._append()
        return self.datablock

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._remove()

    def _append(self):
        with bpy.data.libraries.load(str(self.blend)) as (data_from, data_to):
            data_to.meshes = [self.mesh_name]
        return bpy.data.meshes[self.mesh_name]

    def _remove(self):
        bpy.data.meshes.remove(self.datablock)


class ThreadProfile(ABC):
    pitch: float
    length: float
    starts: int
    height: float  # Height of triangle
    depth: float  # Thread depth
    thread_angle: float
    helix_angle: float
    major_diameter: float
    minor_diameter: float
    pitch_diameter: float
    root_width: float  # Root length
    crest_width: float  # Crest length
    crest_truncation: float  # Distance between triangle crest and crest, for bevel
    root_truncation: float  # Distance between triangle root and root, for bevel
    sharp_crest: bool = False
    # tolerance: float = 0.0

    @property
    def flank_width(self):
        return (self.pitch - self.root_width - self.crest_width) / 2

    def feature_by_index(self, index) -> str:
        """Return feature name of a point by it's index"""
        index = index % 4
        if index < 2:
            return "root"
        return "crest"

    @property
    def section(self):
        """
        left to right, root to crest
        x_axis == screw_axis
        """
        a = np.array([0, (self.minor_diameter / 2)])
        b = a + (self.root_width, 0)
        c = np.array([self.flank_width + self.root_width, self.major_diameter / 2])
        d = c + (self.crest_width, 0)
        if self.sharp_crest:
            c += (self.crest_width / 2, 0)
            d = np.copy(c)
        return np.vstack((a, b, c, d))

    @property
    def points(self):
        # TODO: n_sections is incorrect, the scaling by 2  + 4is a hacky fix
        n_sections = int(self.length / self.pitch * self.starts) * 2 + 4
        full_profile = np.copy(self.section)
        for index in range(1, n_sections):
            offset_section = np.copy(self.section) + (self.pitch * index, 0)
            full_profile = np.vstack((full_profile, offset_section))
        return full_profile
