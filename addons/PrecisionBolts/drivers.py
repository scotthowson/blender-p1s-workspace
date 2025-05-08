"""
Driver Mesh Generators

Supported Shapes:
    0. Cross (Phillips, Frearson )
    1. Hex
    2. Square
    3. Combination (Slotted and Cross)
    4. Slotted

"""

from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

import bmesh
from mathutils import Vector, Euler

from .bmesh_filters import vert_axis_split, verts_in_range, verts_longer_than
from .mesh_gen import new_cross_bmesh, new_cylinder_mesh
from .custom_types import FastenerDriver, MeshReader, PropertyMapping

if TYPE_CHECKING:
    from .properties import FastenerProps


@dataclass
class Cross(FastenerDriver):
    props: FastenerProps
    type = "CROSS"
    mesh_source = None
    prop_map = {
        "driver_mod_a": PropertyMapping("X Length", default=1),
        "driver_mod_b": PropertyMapping("X Width", default=1),
        "driver_mod_c": PropertyMapping("Y Length", default=1),
        "driver_mod_d": PropertyMapping("Y Width", default=1),
        "driver_mod_e": PropertyMapping("Taper", default=1),
    }

    def apply_transforms(self) -> None:
        depth = self.props.driver_depth
        x_length = self.props.driver_mod_a
        x_width = self.props.driver_mod_b
        y_length = self.props.driver_mod_c
        y_width = self.props.driver_mod_d
        taper = self.props.driver_mod_e

        self.bm = new_cross_bmesh(
            x_length, x_width, y_length, y_width, depth=depth, center=False
        )
        # print(len(self.bm.verts[:]))
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.0001)
        bmesh.ops.dissolve_degenerate(self.bm, edges=self.bm.edges, dist=0.0001)

        top_verts, bottom_verts = vert_axis_split(self.bm.verts)

        taper_amnt = self.props.driver_mod_e
        taper = Vector((taper_amnt, taper_amnt, 1))
        bmesh.ops.scale(self.bm, vec=taper, verts=top_verts)


@dataclass
class Polygon(FastenerDriver):
    props: FastenerProps
    type = "POLYGON"
    mesh_source = None
    prop_map = {
        "driver_diameter": PropertyMapping("Radius", default=0.2),
        "driver_mod_c": PropertyMapping("Taper", default=0.2),
        "driver_mod_f": PropertyMapping("Sides", default=6),
    }

    def apply_transforms(self) -> None:
        depth = self.props.driver_depth
        radius = self.props.driver_diameter / 2
        taper = self.props.driver_mod_c
        sides = self.props.driver_mod_f

        self.bm = new_cylinder_mesh(radius, sides, depth)

        top_verts, bottom_verts = vert_axis_split(self.bm.verts, 0.0001)
        taper_amnt = taper
        taper = Vector((taper_amnt, taper_amnt, 1))
        bmesh.ops.scale(self.bm, vec=taper, verts=top_verts)


@dataclass
class Slotted(FastenerDriver):
    props: FastenerProps
    type = "SLOTTED"
    mesh_source = None
    prop_map = {
        "driver_mod_a": PropertyMapping("Length", default=1),
        "driver_mod_b": PropertyMapping("Width", default=1),
        "driver_mod_c": PropertyMapping("Taper", default=1),
    }

    def apply_transforms(self) -> None:
        depth = self.props.driver_depth
        x_length = self.props.driver_mod_a
        x_width = self.props.driver_mod_b
        taper = self.props.driver_mod_c

        self.bm = new_cross_bmesh(x_length, x_width, 0, 0, depth=depth, center=False)
        top_verts, _ = vert_axis_split(self.bm.verts, 0.0001)

        taper_amnt = self.props.driver_mod_c
        taper = Vector((taper_amnt, taper_amnt, 1))
        bmesh.ops.scale(self.bm, vec=taper, verts=top_verts)


DRIVERS = {subclass.type: subclass for subclass in FastenerDriver.__subclasses__()}
