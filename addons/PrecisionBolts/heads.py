from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING

from mathutils import Vector, Matrix, Euler
import bmesh
from bmesh.types import BMesh, BMVert, BMEdge, BMFace


from .bmesh_filters import vert_axis_split, verts_in_range
from .bmesh_helpers import shared_edges, shared_faces, temp_subd_modifier
from .custom_types import EditMesh, MeshReader, FastenerHead, PropertyMapping
from . import config

if TYPE_CHECKING:
    from .properties import FastenerProps


@dataclass
class Flat(FastenerHead):
    props: FastenerProps
    # bm: BMesh = field(init=False)
    type = "FLAT"
    mesh_source = partial(MeshReader, "FLAT", config.HEADS_FILE)
    # type_mod_a = "Bevel"
    # type_mod_b = "Scaler"

    prop_map = {
        "head_mod_a": PropertyMapping("Bevel", default=0),
        "head_mod_b": PropertyMapping("Cap Scale Offset", default=1),
    }

    def _apply_type_transforms(self) -> None:
        # bmesh.ops.subdivide_edges(self.bm, edges=self.bm.edges[:], smooth=1, cuts=2)
        # temp_subd_modifier(self.bm)
        top_verts, bottom_verts = vert_axis_split(self.bm.verts)
        # Apply Length
        length_v = Vector((1, 1, self.props.head_length))
        bmesh.ops.scale(self.bm, vec=length_v, verts=top_verts)

        # Apply radius
        diameter = self.props.head_diameter * 2
        base_scaler = Vector((diameter, diameter, 1))
        bmesh.ops.scale(self.bm, vec=base_scaler, verts=bottom_verts)

        top_scale_offset = self.props.head_mod_b
        top_scaler = base_scaler.copy()
        top_scaler.xy *= top_scale_offset
        bmesh.ops.scale(self.bm, vec=top_scaler, verts=top_verts)

        if self.props.head_mod_a > 0:
            geom = shared_edges(top_verts)
            bevel_amnt = self.props.head_mod_a
            bmesh.ops.bevel(
                self.bm,
                geom=geom,
                offset=bevel_amnt,
                segments=4,
                affect="EDGES",
                profile=0.5,
            )
        return None


@dataclass
class Hex(FastenerHead):
    props: FastenerProps
    type = "HEX"
    mesh_source = partial(MeshReader, "HEX", config.HEADS_FILE)
    # type_mod_a = "Chamfer Ofset"

    prop_map = {
        "head_mod_a": PropertyMapping("Chamfer Scale", default=0.5),
        # "head_mod_b": PropertyMapping("Mod B", default=2),
    }

    def _apply_type_transforms(self) -> None:
        top_verts, bottom_verts = vert_axis_split(self.bm.verts)

        # Apply radius
        diameter = self.props.head_diameter
        radius_scaler = Vector((diameter, diameter, 1))
        bmesh.ops.scale(self.bm, vec=radius_scaler, verts=self.bm.verts)

        chamfer_verts = []
        for vert in self.bm.verts:
            is_top_chamfer = vert.co.z > 0.8
            # is_bottom_chamfer = vert.co.z > 0.01 and vert.co.z < 0.22
            # if any((is_top_chamfer, is_bottom_chamfer)):
            if is_top_chamfer:
                chamfer_verts.append(vert)

        # Transform chamfer
        chamfer_scale = self.props.head_mod_a
        scaler = Vector((1, 1, chamfer_scale))
        bmesh.ops.translate(self.bm, vec=Vector((0, 0, -1)), verts=top_verts)
        bmesh.ops.scale(self.bm, vec=scaler, verts=self.bm.verts)
        bmesh.ops.translate(self.bm, vec=Vector((0, 0, 1)), verts=top_verts)

        # Apply Length
        length_v = Vector((1, 1, self.props.head_length))
        bmesh.ops.scale(self.bm, vec=length_v, verts=top_verts)

        if chamfer_scale <= 0.00001:
            bmesh.ops.dissolve_verts(self.bm, verts=chamfer_verts)

            # divide ngons
            is_ngon = lambda f: len(f.edges) > 4
            ngons = list(filter(is_ngon, self.bm.faces))
            bmesh.ops.triangulate(self.bm, faces=ngons)

        return None


@dataclass
class HexWasher(FastenerHead):
    props: FastenerProps
    type = "HEX_WASHER"
    mesh_source = partial(MeshReader, "HEX_WASHER", config.HEADS_FILE)
    # type_mod_a = "Chamfer Offset"
    # type_mod_b = "Washer Size"

    prop_map = {
        "head_mod_a": PropertyMapping("Chamfer Scale", default=1),
        "head_mod_b": PropertyMapping("Washer Radius", default=1),
        "head_mod_c": PropertyMapping("Washer Length", default=1),
    }

    def _apply_type_transforms(self) -> None:
        # Identify groups
        top_verts, bottom_verts = vert_axis_split(self.bm.verts)
        washer_top_range = (0.20, 0.30)
        washer_top_verts = list(verts_in_range(bottom_verts, washer_top_range))
        washer_outside_verts = [v for v in bottom_verts if v.co.xy.length > 0.55]

        # Set Total Radius
        diameter = self.props.head_diameter
        radius_scaler = Vector((diameter, diameter, 1))
        bmesh.ops.scale(self.bm, vec=radius_scaler, verts=self.bm.verts)

        chamfer_verts = []
        for vert in self.bm.verts:
            if vert.co.z > 0.8:
                chamfer_verts.append(vert)

        # Set washer radius
        for v in washer_outside_verts:
            v.co.xy = v.co.xy.normalized()
            v.co.xy *= self.props.head_mod_b

        # Set washer length
        for v in washer_top_verts:
            v.co.z = self.props.head_mod_c

        # Set chamfer scale
        chamfer_scale = self.props.head_mod_a
        scale = Vector((1, 1, chamfer_scale))
        origin = Matrix.Translation(Vector((0, 0, -1)))
        bmesh.ops.scale(self.bm, vec=scale, verts=top_verts, space=origin)

        # Set Total Length
        length_v = Vector((1, 1, self.props.head_length))
        bmesh.ops.scale(self.bm, vec=length_v, verts=top_verts)

        if chamfer_scale <= 0.00001:
            bmesh.ops.dissolve_verts(self.bm, verts=chamfer_verts)

            # divide ngons
            is_ngon = lambda f: len(f.edges) > 4
            ngons = list(filter(is_ngon, self.bm.faces))
            bmesh.ops.triangulate(self.bm, faces=ngons)

        return None


@dataclass
class Carriage(FastenerHead):
    props: FastenerProps
    type = "CARRIAGE"
    mesh_source = partial(MeshReader, "CARRIAGE", config.HEADS_FILE)

    prop_map = {
        # "head_mod_a": PropertyMapping("Cap Radius", default=1),
        "head_mod_b": PropertyMapping("Nut Radius", default=1),
        "head_mod_c": PropertyMapping("Nut Length", default=1),
    }

    def _apply_type_transforms(self) -> None:
        # Identify groups
        cap_verts, nut_verts = vert_axis_split(self.bm.verts, split_val=0.55)
        nut_top_verts, _ = vert_axis_split(nut_verts, split_val=0.25)

        # Reset cap verts
        bmesh.ops.translate(self.bm, vec=Vector((0, 0, -0.5)), verts=cap_verts)

        # Set Nut Length
        cap_length = self.props.head_length
        cap_diameter = self.props.head_diameter
        nut_diameter = self.props.head_mod_b
        nut_length = self.props.head_mod_c
        offset = Vector((0, 0, -0.5 + nut_length))
        bmesh.ops.translate(self.bm, vec=offset, verts=cap_verts + nut_top_verts)

        # Set Nut Radius
        diameter = nut_diameter
        radius_scaler = Vector((diameter, diameter, 1))
        bmesh.ops.scale(self.bm, vec=radius_scaler, verts=nut_verts)

        # Set Cap Radius
        diameter = cap_diameter
        radius_scaler = Vector((diameter, diameter, 1))
        bmesh.ops.scale(self.bm, vec=radius_scaler, verts=cap_verts)

        # Set Cap Length
        scale = Vector((1, 1, cap_length * 2))
        origin = Matrix.Translation(Vector((0, 0, -nut_length)))
        bmesh.ops.scale(self.bm, vec=scale, verts=cap_verts, space=origin)
        return None


@dataclass
class Socked(FastenerHead):
    props: FastenerProps
    type = "SOCKED"
    mesh_source = partial(MeshReader, "SOCKED", config.HEADS_FILE)
    # type_mod_a = "Bevel"

    prop_map = {
        "head_mod_a": PropertyMapping("Bevel", default=0),
    }

    def _apply_type_transforms(self) -> None:

        # bmesh.ops.subdivide_edges(self.bm, edges=self.bm.edges[:], smooth=1, cuts=2)
        # Identify groups
        top_verts, bottom_verts = vert_axis_split(self.bm.verts)

        # Set Total Radius
        diameter = self.props.head_diameter
        radius_scaler = Vector((diameter, diameter, 1))
        bmesh.ops.scale(self.bm, vec=radius_scaler, verts=self.bm.verts)

        # Set Total Length
        length_v = Vector((1, 1, self.props.head_length))
        bmesh.ops.scale(self.bm, vec=length_v, verts=top_verts)

        # Do Set bevel
        if self.props.head_mod_a > 0:
            geom = shared_edges(top_verts)
            bevel_amnt = self.props.head_mod_a
            bmesh.ops.bevel(
                self.bm,
                geom=geom,
                offset=bevel_amnt,
                segments=4,
                affect="EDGES",
                profile=0.5,
            )

        return None


HEADS = {subclass.type: subclass for subclass in FastenerHead.__subclasses__()}
