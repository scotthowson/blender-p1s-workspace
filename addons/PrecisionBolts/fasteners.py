"""
Fastener definitions and mesh generation functions
"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from math import pi, radians, tan
from typing import TYPE_CHECKING, List, Union
from itertools import chain

import bpy
from bpy.types import Context, Object, Mesh
import bmesh
from bmesh.types import BMesh, BMVert, BMEdge, BMFace
from mathutils import Vector, Matrix, Euler
import numpy as np

from .heads import HEADS
from .drivers import DRIVERS
from .config import NUTS_FILE
from .custom_types import (
    FastenerHead,
    FastenerVertLayers,
    MeshReader,
    PropertyMapping,
    Fastener,
    PropsUpdateDisabled,
)
from . import thread_profiles
from .bmesh_filters import dict_by_type, vert_axis_split, unique_edge_verts
from . import bmesh_helpers
from .bmesh_helpers import bm_as_list, boolean_bm, map_range, shared_edges

if TYPE_CHECKING:
    from .properties import FastenerProps


def update_fastener(self, context: Context) -> None:
    props: FastenerProps = self
    fastener: Object = self.id_data

    # Editing flag is a sign that other callbacks are editing the property group
    if props.editing:  # Early return to prevent infinite recursion
        return None

    # Cap Shank length
    with PropsUpdateDisabled(props) as static_props:
        static_props.shank_length = min(props.shank_length, props.length)
        static_props.runout_length = min(props.shank_length, props.runout_length)
        shank_true_radius = (props.major_diameter / 2) + props.runout_offset
        static_props.head_diameter = max(props.head_diameter, shank_true_radius)
        static_props.chamfer_length = min(
            props.chamfer_length, props.length - props.runout_length
        )

    builder = builders[props.fastener_type](props)
    builder.create(fastener.data)

    # Handle sharpness update, 
    # TODO: Using op is hacky and attribs should be done in mesh generation
    is_bpy_ver_over_4_1 = bpy.app.version[0] >=4 and bpy.app.version[1] > 0
    if is_bpy_ver_over_4_1 and props.shade_smooth:
        bpy.ops.object.shade_smooth_by_angle(angle=radians(30))




@dataclass
class Nut(Fastener):
    props: FastenerProps
    type = "NUT"
    heads = None
    drivers = None

    custom_thread_props = {
        "custom_thread_profile": PropertyMapping("Custom Profile", default=0),
        "major_diameter": PropertyMapping("Major Diameter", default=2),
        "minor_diameter": PropertyMapping("Minor Diameter", default=1.2),
        "crest_weight": PropertyMapping("Crest Weight", default=0.5),
        "root_weight": PropertyMapping("Root Weight", default=0.5),
    }

    standard_thread_props = {
        "custom_thread_profile": PropertyMapping("Custom Profile", default=0),
        "major_diameter": PropertyMapping("Major Diameter", default=2),
    }

    type_props = {
        "pitch": PropertyMapping("Pitch", default=0.2),
        "nut_type": PropertyMapping("Nut", default="HEX"),
        "nut_diameter": PropertyMapping("Diameter", default=2.14),
        "length": PropertyMapping("Length", default=1.8),
        "nut_chamfer": PropertyMapping("Chamfer", min_val=0.001, default=1),
        "thread_resolution": PropertyMapping("Thread Resolution", default=16),
        # "major_diameter": PropertyMapping("Major Diameter", default=2),
        "starts": PropertyMapping("Thread Starts", min_val=1, default=1),
    }

    general_props = {
        # "thread_direction": PropertyMapping("Direction Prop B", default="RIGHT"),
        "bisect": PropertyMapping("Bisect", default=False),
        "triangulate": PropertyMapping("Triangulate", default=False),
        "tolerance": PropertyMapping("Tolerance", default=0),
        "scale": PropertyMapping("Scale", default=1),
        "shade_smooth": PropertyMapping("Shade Smooth", default=False),
    }

    def create(self, mesh: Mesh) -> Mesh:
        self._load_body()
        body_geom = dict_by_type(bm_as_list(self.bm))
        boundary_verts = [v for v in body_geom[BMVert] if v.is_boundary]
        body_rim_top_verts, body_rim_bottom_verts = vert_axis_split(boundary_verts)
        body_loop_top = shared_edges(body_rim_top_verts)
        body_loop_bottom = shared_edges(body_rim_bottom_verts)

        # Transform body
        self._transform_body()

        # Mesh Threads
        body_geom = set(bm_as_list(self.bm))
        thread_bm = self._mesh_nut_threads()
        temp_mesh = bpy.data.meshes.new("temp")
        thread_bm.to_mesh(temp_mesh)
        thread_bm.free()
        self.bm.from_mesh(temp_mesh)
        bpy.data.meshes.remove(temp_mesh)
        thread_geom = set(bm_as_list(self.bm)) - body_geom
        thread_geom = dict_by_type(thread_geom)

        # Identity Thread boundary loops
        boundary_verts = [v for v in thread_geom[BMVert] if v.is_boundary]
        # for v in boundary_verts:
        #     v.co.z += 1

        thread_rim_top, thread_rim_bottom = vert_axis_split(boundary_verts, 0.001)
        thread_loop_top = shared_edges(thread_rim_top)
        thread_loop_bottom = shared_edges(thread_rim_bottom)

        # Smooth Thread Terminations
        self._smooth_thread_terminations(thread_geom[BMVert])

        # Bridge loop and body
        bridge_a = thread_loop_top + body_loop_top
        bridge_b = thread_loop_bottom + body_loop_bottom
        for edges in (bridge_a, bridge_b):
            bmesh.ops.bridge_loops(self.bm, edges=edges)

        # Bisect mesh
        if self.props.bisect:
            self._bisect()

        if self.props.triangulate:
            bmesh.ops.triangulate(self.bm, faces=self.bm.faces)

        # Apply tolerance transforms
        # if self.props.tolerance != 0:
        #     self._adjust_tolerance()

        # Apply scale
        if self.props.scale != 0.0:
            self._scale()

        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])

        for f in self.bm.faces:
            f.smooth = self.props.shade_smooth

        self.bm.to_mesh(mesh)

    def _smooth_thread_terminations(self, thread_verts: List[BMVert]) -> None:
        target_radius = self.props.major_diameter * 0.55 - (self.props.tolerance * 0.5)
        affected_distance = self.props.length * 0.1
        # From no effect to full (target_radius)
        top_range = (self.props.length - affected_distance, self.props.length)
        bottom_range = (affected_distance, 0)

        for vert in thread_verts:
            xy, z = vert.co.xy, vert.co.z
            if z <= bottom_range[0]:
                effect_range = bottom_range
            elif z >= top_range[0]:
                effect_range = top_range
            else:
                continue
            init_mag = xy.length
            target_mag = map_range(z, effect_range, (init_mag, target_radius))
            vert.co.xy = xy.normalized() * target_mag

    def _bisect(self) -> None:
        # TODO: Inconsistent mesh placement
        geom = bmesh_helpers.bm_as_list(self.bm)
        duplicate = bmesh.ops.duplicate(self.bm, geom=geom)
        front = dict_by_type(duplicate["geom_orig"])
        back = dict_by_type(duplicate["geom"])

        z_offset = -(self.props.length + self.props.head_length) / 2
        height_offset = Vector((0, 0, z_offset))
        bmesh.ops.translate(self.bm, vec=height_offset, verts=self.bm.verts)

        x_offset = self.props.length
        loc_offset = Vector((0, self.props.length, 0))
        front_rot = Euler((radians(90), 0, 0)).to_matrix()
        cent = Vector.Fill(3, 0)
        bmesh.ops.rotate(self.bm, cent=cent, verts=front[BMVert], matrix=front_rot)
        bmesh.ops.translate(self.bm, vec=loc_offset, verts=front[BMVert])

        back_rot = Euler((radians(-90), 0, 0)).to_matrix()
        bmesh.ops.rotate(self.bm, cent=cent, verts=back[BMVert], matrix=back_rot)
        bmesh.ops.translate(self.bm, vec=-loc_offset, verts=back[BMVert])

        geom = bmesh_helpers.bm_as_list(self.bm)
        co, no = Vector.Fill(3, 0), Vector((0, 0, -1))
        trimmed = bmesh.ops.bisect_plane(
            self.bm, geom=geom, clear_outer=True, plane_co=co, plane_no=no
        )

        cut = dict_by_type(trimmed["geom_cut"])
        edges = bmesh_helpers.shared_edges(cut[BMVert])
        fills = bmesh.ops.holes_fill(self.bm, edges=edges)
        bmesh.ops.triangulate(self.bm, faces=fills["faces"])
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.00001)

    def _transform_body(self) -> None:
        # Set Chamfer
        top_verts, bottom_verts = vert_axis_split(self.bm.verts)
        bmesh.ops.translate(self.bm, vec=Vector((0, 0, -1)), verts=top_verts)
        scaler = Vector((1, 1, self.props.nut_chamfer))
        bmesh.ops.scale(self.bm, vec=scaler, verts=top_verts + bottom_verts)
        # Set Length
        bmesh.ops.translate(
            self.bm, vec=Vector((0, 0, self.props.length)), verts=top_verts
        )

        # Set Radius
        scaler = Vector((self.props.nut_diameter, self.props.nut_diameter, 1))
        bmesh.ops.scale(self.bm, vec=scaler, verts=top_verts + bottom_verts)

    def _load_body(self) -> None:
        with MeshReader(self.props.nut_type, NUTS_FILE) as mesh_loader:
            self.bm.from_mesh(mesh_loader)

    def _mesh_nut_threads(self):
        """
        Create mesh threads in self.bm
        Returns: Tuple of bottom, top geom dicts whose keys are geometry types
        """
        thread_bm = bmesh.new()
        vert_layers = FastenerVertLayers(thread_bm)

        def _np2d_to_v3d(coord):
            """[a,b] np to [b, 0, a] vector"""
            return Vector((coord[1], 0, coord[0]))

        if self.props.custom_thread_profile:
            profile = thread_profiles.Custom(
                self.props.pitch,
                self.props.length - self.props.tolerance,
                self.props.minor_diameter - self.props.tolerance,
                self.props.major_diameter - self.props.tolerance,
                self.props.starts,
                self.props.root_weight,
                self.props.crest_weight,
            )
        else:
            profile = thread_profiles.ISO_68_1(
                self.props.pitch,
                self.props.length - self.props.tolerance,
                self.props.major_diameter - self.props.tolerance,
                self.props.starts,
                self.props.thread_angle,
            )

        # Create profile verts
        profile_points = deque(profile.points)
        profile_verts = []
        first_coord = profile_points.pop()
        prev_vert = thread_bm.verts.new(_np2d_to_v3d(first_coord))
        profile_verts.append(prev_vert)
        while profile_points:
            co = _np2d_to_v3d(profile_points.pop())
            new_vert = thread_bm.verts.new(co)
            thread_bm.edges.new((prev_vert, new_vert))
            prev_vert = new_vert
            profile_verts.append(new_vert)

        # Assign vert feature type to layer
        # List is revered because thread points are processed LIFO
        for index, vert in enumerate(reversed(thread_bm.verts[:])):
            if profile.feature_by_index(index) == "crest":
                vert[vert_layers.thread_crests] = 1
            else:
                vert[vert_layers.thread_roots] = 1

        start_verts = profile_verts
        # start_profile = start_verts + self.bm.edges[:]
        start_profile = shared_edges(start_verts)
        steps = self.props.thread_resolution
        step_z = self.props.pitch * self.props.starts / steps
        axis = Vector((0, 0, 1))
        dvec = Vector((0, 0, step_z))
        # if self.props.thread_direction == "RIGHT":
        angle = radians(360)
        # else:
        #     angle = radians(-360)

        spun = bmesh.ops.spin(
            thread_bm,
            geom=start_profile,
            angle=angle,
            steps=steps,
            # use_merge=True,
            dvec=dvec,
            axis=axis,
        )

        end_verts = dict_by_type(spun["geom_last"])[BMVert]
        merge_dist = 0.001
        boundary_verts = [
            vert for vert in chain(start_verts, end_verts) if vert.is_boundary
        ]
        bmesh.ops.remove_doubles(thread_bm, verts=boundary_verts, dist=merge_dist)

        # Cut Bottom
        geom = bmesh_helpers.bm_as_list(thread_bm)
        loc = Vector((0, 0, self.props.pitch * self.props.starts))
        norm = Vector((0, 0, -1))
        result = bmesh_helpers.trim(thread_bm, geom, loc=loc, norm=norm, cap=False)

        # Floor thread mesh
        min_z = bmesh_helpers.min_vert(thread_bm.verts[:], "z").co.z
        bmesh.ops.translate(
            thread_bm, vec=Vector((0, 0, -min_z)), verts=thread_bm.verts
        )

        # Cut Top
        geom = bmesh_helpers.bm_as_list(thread_bm)
        loc = Vector((0, 0, self.props.length))
        result = bmesh_helpers.trim(thread_bm, geom, loc=loc, norm=Vector((0, 0, 1)))
        bmesh.ops.reverse_faces(thread_bm, faces=thread_bm.faces)

        # Tri divide ngons
        ngons = [f for f in self.bm.faces if len(f.edges[:]) > 4]
        bmesh.ops.triangulate(self.bm, faces=ngons)

        return thread_bm


@dataclass
class Bolt(Fastener):
    props: FastenerProps
    type = "BOLT"
    heads = HEADS
    drivers = DRIVERS

    custom_thread_props = {
        "custom_thread_profile": PropertyMapping("Custom Profile", default=0),
        "major_diameter": PropertyMapping("Major Diameter", default=2),
        "minor_diameter": PropertyMapping("Minor Diameter", default=1.2),
        "crest_weight": PropertyMapping("Crest Weight", default=0.5),
        "root_weight": PropertyMapping("Root Weight", default=0.5),
    }

    standard_thread_props = {
        "custom_thread_profile": PropertyMapping("Custom Profile", default=0),
        "major_diameter": PropertyMapping("Major Diameter", default=2),
    }

    type_props = {
        "pitch": PropertyMapping("Pitch", default=0.2),
        "length": PropertyMapping("Length", default=4),
        "thread_resolution": PropertyMapping("Thread Resolution", default=16),
        "starts": PropertyMapping("Thread Starts", min_val=1, default=1),
        "shank_length": PropertyMapping("Shank Length", min_val=0, default=1),
        "chamfer": PropertyMapping("Chamfer", min_val=0, default=radians(15)),
        "chamfer_length": PropertyMapping("Chamfer Length", min_val=0, default=0.1),
        "chamfer_divisions": PropertyMapping("Chamfer Divisions", min_val=0, default=0),
        "runout_length": PropertyMapping("Runout Length", min_val=0, default=0),
        "runout_offset": PropertyMapping("Runout Offset", default=0),
    }

    general_props = {
        # "thread_direction": PropertyMapping("Direction Prop B", default="RIGHT"),
        "bisect": PropertyMapping("Bisect", default=False),
        "trim": PropertyMapping("Trim", default=0),
        "triangulate": PropertyMapping("Triangulate", default=False),
        "bisect": PropertyMapping("Bisect", default=False),
        "tolerance": PropertyMapping("Tolerance", default=0),
        "scale": PropertyMapping("Scale", default=1),
        "shade_smooth": PropertyMapping("Shade Smooth", default=False),
    }

    def create(self, mesh: Mesh):
        """Create new fastener in mesh datablock"""
        has_thread = self.props.shank_length < self.props.length
        if has_thread:
            threads_bottom, threads_top = self._mesh_threads()

            top_edges = threads_top[BMEdge]
            bottom_edges = threads_bottom[BMEdge]
            top_verts = threads_top[BMVert]

            # Round thread top termination (vanishing cone)
            top_verts = bmesh_helpers.polar_sort_verts(top_verts)
            for vert in top_verts:
                vert.co.z = (
                    self.props.length - self.props.shank_length - self.props.tolerance
                )

            # Smooth Thread termination
            end = self.props.length - self.props.shank_length - self.props.tolerance
            start = end - (self.props.pitch / 2)
            start_end = start, end
            bmesh_helpers.interp_vert_mag_along_axis(
                self.bm.verts,
                start_end,
                self.major_radius,
            )

        else:  # Only shank
            circle = bmesh.ops.create_circle(
                self.bm, radius=self.major_radius, segments=self.props.thread_resolution
            )
            top_edges = bmesh_helpers.shared_edges(circle["verts"])
            bottom_edges = top_edges
            bmesh.ops.triangle_fill(self.bm, use_dissolve=True, edges=bottom_edges)

        # Create Shank
        if self.props.shank_length != 0:
            top_edges = self._create_shank(top_edges)

        # Create Head
        if self.props.head_type != "NONE":
            # Create and merge head mesh
            head_bm = self._create_head()
            head_verts, head_faces = bmesh_helpers.merge_bmesh(head_bm, self.bm)

            # Set head height
            offset = Vector((0, 0, self.props.length - (self.props.tolerance * 2)))
            bmesh.ops.translate(self.bm, vec=offset, verts=head_verts)

            head_opening = filter(lambda v: v.is_boundary, head_verts)
            connection_loop = bmesh_helpers.shared_edges(head_opening)

            # Join shank/thread to head
            open_loops = connection_loop + top_edges
            # self.bm, edges=open_loops, use_pairs=True,
            # TODO: Fix this
            bmesh.ops.bridge_loops(
                self.bm,
                edges=open_loops,
            )
        else:
            bmesh.ops.triangle_fill(self.bm, use_dissolve=True, edges=top_edges)

        if self.props.chamfer_length > 0:
            self._chamfer()

        if self.props.driver_type != "NONE":
            driver_bm = self._create_driver()
            self.bm = boolean_bm(self.bm, driver_bm, xform=self._driver_xform)
            driver_bm.free()

        if self.props.triangulate:
            bmesh.ops.triangulate(self.bm, faces=self.bm.faces)

        if self.props.trim != 0:
            self.trim()

        # if self.props.tolerance != 0:
        #     self._adjust_tolerance()

        if self.props.bisect:
            self._bisect()

        if self.props.scale != 0.0:
            self._scale()

        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])

        for f in self.bm.faces:
            f.smooth = self.props.shade_smooth

        self.bm.to_mesh(mesh)

    def _mesh_threads(self):
        """
        Create mesh threads in self.bm
        Returns: Tuple of bottom, top geom dicts whose keys are geometry types
        """

        def _np2d_to_v3d(coord):
            """[a,b] np to [b, 0, a] vector"""
            return Vector((coord[1], 0, coord[0]))

        if self.props.custom_thread_profile:
            profile = thread_profiles.Custom(
                self.props.pitch,
                self.props.length - self.props.tolerance,
                self.props.minor_diameter - self.props.tolerance,
                self.props.major_diameter - self.props.tolerance,
                self.props.starts,
                self.props.root_weight,
                self.props.crest_weight,
                # tolerance=self.props.tolerance,
            )
        else:
            profile = thread_profiles.ISO_68_1(
                self.props.pitch,
                self.props.length - self.props.tolerance,
                self.props.major_diameter - self.props.tolerance,
                self.props.starts,
                self.props.thread_angle,
                # tolerance=self.props.tolerance,
            )

        profile_points = deque(profile.points)
        first_coord = profile_points.pop()
        prev_vert = self.bm.verts.new(_np2d_to_v3d(first_coord))

        # Create rest of profile verts
        while profile_points:
            # Create new vert
            co = _np2d_to_v3d(profile_points.pop())
            new_vert = self.bm.verts.new(co)

            # Create edge
            self.bm.edges.new((prev_vert, new_vert))

            # Assign new to last for next iteration
            prev_vert = new_vert

        # Assign vert feature type to layer
        # List is revered because thread points are processed LIFO
        for index, vert in enumerate(reversed(self.bm.verts[:])):
            if profile.feature_by_index(index) == "crest":
                vert[self.vert_layers.thread_crests] = 1
            else:
                vert[self.vert_layers.thread_roots] = 1

        start_verts = self.bm.verts[:]
        start_profile = start_verts + self.bm.edges[:]
        steps = self.props.thread_resolution
        step_z = self.props.pitch * self.props.starts / steps
        axis = Vector((0, 0, 1))
        dvec = Vector((0, 0, step_z))

        # NOTE: Not used
        # if self.props.thread_direction == "RIGHT":
        angle = radians(360)
        # else:
        #     angle = radians(-360)

        spun = bmesh.ops.spin(
            self.bm,
            geom=start_profile,
            angle=angle,
            steps=steps,
            dvec=dvec,
            axis=axis,
        )

        end_verts = dict_by_type(spun["geom_last"])[BMVert]
        merge_dist = 0.001
        boundary_verts = [
            vert for vert in chain(start_verts, end_verts) if vert.is_boundary
        ]
        bmesh.ops.remove_doubles(self.bm, verts=boundary_verts, dist=merge_dist)

        # Cut Bottom
        geom = bmesh_helpers.bm_as_list(self.bm)
        loc = Vector((0, 0, self.props.pitch * self.props.starts))
        norm = Vector((0, 0, -1))
        cut_merge_dist = 0.001
        result = bmesh_helpers.trim(
            self.bm, geom, dist=cut_merge_dist, loc=loc, norm=norm, cap=True
        )
        thread_bottom = dict_by_type(result["geom_cut"])

        # Floor thread mesh
        min_z = bmesh_helpers.min_vert(self.bm.verts[:], "z").co.z
        for v in self.bm.verts[:]:
            v.co.z -= min_z

        # Cut Top
        geom = bmesh_helpers.bm_as_list(self.bm)
        loc = Vector(
            (0, 0, self.props.length - self.props.shank_length - self.props.tolerance)
        )
        norm = Vector((0, 0, 1))
        merge_dist = 0.01

        thread_top = None

        result = bmesh.ops.bisect_plane(
            self.bm,
            geom=geom,
            plane_co=loc,
            plane_no=norm,
            dist=merge_dist,
            clear_outer=True,
        )

        thread_top = dict_by_type(result["geom_cut"])

        # Tri divide ngons
        ngons = [f for f in self.bm.faces if len(f.edges[:]) > 4]
        bmesh.ops.triangulate(self.bm, faces=ngons)

        # bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts[:], dist=merge_dist)

        return thread_bottom, thread_top

    @property
    def _driver_xform(self):
        boolean_buffer = 0.001
        z = (self.props.length - self.props.tolerance) + boolean_buffer
        if self.props.head_type != "NONE":
            z += self.props.head_length - self.props.tolerance
        location = Matrix.Translation((0, 0, z))
        rotation = Matrix.Rotation(radians(180), 4, "X")
        # scale = Matrix.Scale(self.props.driver_diameter, 4)
        return location @ rotation

    def _chamfer(self):
        start_z = self.props.chamfer_length
        end_z = 0
        start_radius = self.major_radius
        end_radius = start_radius - (
            tan(self.props.chamfer) * self.props.chamfer_length
        )

        # Add chamfer divisions
        extra_divisions = self.props.chamfer_divisions
        if extra_divisions > 0:
            cut_norm = Vector((0, 0, 1))
            cut_loc = Vector((0, 0, 0))
            for cut_z in np.linspace(start_z, end_z, num=extra_divisions):
                cut_loc.z = cut_z
                geom = self.bm.faces[:] + self.bm.edges[:]
                bmesh.ops.bisect_plane(
                    self.bm, geom=geom, dist=0.0001, plane_co=cut_loc, plane_no=cut_norm
                )

        affected_verts = filter(lambda v: v.co.z < start_z, self.bm.verts)
        for vert in affected_verts:
            xy, z = vert.co.xy, vert.co.z
            init_mag = xy.length
            target_mag = map_range(z, (start_z, end_z), (init_mag, end_radius))
            vert.co.xy = xy.normalized() * target_mag

    def _bisect(self) -> None:
        geom = bmesh_helpers.bm_as_list(self.bm)
        duplicate = bmesh.ops.duplicate(self.bm, geom=geom)
        front = dict_by_type(duplicate["geom_orig"])
        back = dict_by_type(duplicate["geom"])

        z_offset = -(self.props.length + self.props.head_length) / 2
        x_offset = max(self.props.head_diameter, self.props.major_diameter / 2 * 1.1)
        loc_offset = Vector((x_offset, 0, 0))
        height_offset = Vector((0, 0, z_offset))
        bmesh.ops.translate(self.bm, vec=height_offset, verts=self.bm.verts)

        front_rot = Euler((radians(90), 0, 0)).to_matrix()
        cent = Vector.Fill(3, 0)
        bmesh.ops.rotate(self.bm, cent=cent, verts=front[BMVert], matrix=front_rot)
        bmesh.ops.translate(self.bm, vec=loc_offset, verts=front[BMVert])

        back_rot = Euler((radians(-90), 0, 0)).to_matrix()
        bmesh.ops.rotate(self.bm, cent=cent, verts=back[BMVert], matrix=back_rot)
        bmesh.ops.translate(self.bm, vec=-loc_offset, verts=back[BMVert])

        geom = bmesh_helpers.bm_as_list(self.bm)
        co, no = Vector.Fill(3, 0), Vector((0, 0, -1))
        trimmed = bmesh.ops.bisect_plane(
            self.bm, geom=geom, clear_outer=True, plane_co=co, plane_no=no
        )

        cut = dict_by_type(trimmed["geom_cut"])
        edges = bmesh_helpers.shared_edges(cut[BMVert])
        fills = bmesh.ops.holes_fill(self.bm, edges=edges)
        bmesh.ops.triangulate(self.bm, faces=fills["faces"])
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.00001)

    # @property
    # def major_radius(self) -> float:
    #     return self.props.major_diameter / 2 - self.props.tolerance

    # def _create_shank(self, edges: Union[List[BMEdge], None]) -> List[BMEdge]:
    #     extrusion = bmesh.ops.extrude_edge_only(self.bm, edges=edges)["geom"]
    #     extrusion = dict_by_type(extrusion)

    #     init_verts = unique_edge_verts(edges)
    #     extrusion_verts = extrusion[BMVert]

    #     for vert in extrusion_verts:
    #         xy: Vector = vert.co.xy
    #         mag = xy.length
    #         vert.co.xy = xy.normalized() * (self.major_radius + self.props.runout_offset)

    #     for vert in init_verts:
    #         xy: Vector = vert.co.xy
    #         vert.co.xy = xy.normalized() * self.major_radius

    #     if self.props.runout_length != 0:
    #         runout_edges = extrusion[BMEdge]
    #         runout_verts = extrusion[BMVert]
    #         extrusion = bmesh.ops.extrude_edge_only(self.bm, edges=runout_edges)["geom"]
    #         extrusion = dict_by_type(extrusion)
    #         for vert in runout_verts:
    #             vert.co.z += self.props.runout_length

    #     for vert in extrusion[BMVert]:
    #         vert.co.z += self.props.shank_length - self.props.tolerance

    #     return extrusion[BMEdge]

    def _create_head(self) -> BMesh:
        # Create head mesh, apply modifiers and remove
        head: FastenerHead = self.heads[self.props.head_type](self.props)
        head.apply_transforms()
        return head.bm

    def _create_driver(self) -> BMesh:
        driver = self.drivers[self.props.driver_type](self.props)
        driver.apply_transforms()
        return driver.bm


@dataclass
class ThreadedRod(Fastener):
    props: FastenerProps
    type = "THREADED_ROD"

    custom_thread_props = {
        "custom_thread_profile": PropertyMapping("Custom Profile", default=0),
        "major_diameter": PropertyMapping("Major Diameter", default=2),
        "minor_diameter": PropertyMapping("Minor Diameter", default=1.2),
        "crest_weight": PropertyMapping("Crest Weight", default=0.5),
        "root_weight": PropertyMapping("Root Weight", default=0.5),
    }

    standard_thread_props = {
        "custom_thread_profile": PropertyMapping("Custom Profile", default=0),
        "major_diameter": PropertyMapping("Major Diameter", default=2),
    }

    type_props = {
        "pitch": PropertyMapping("Pitch", default=0.2),
        "length": PropertyMapping("Length", default=4),
        "thread_resolution": PropertyMapping("Thread Resolution", default=16),
        "starts": PropertyMapping("Thread Starts", min_val=1, default=1),
        "chamfer": PropertyMapping("Chamfer", min_val=0, default=radians(15)),
        "chamfer_length": PropertyMapping("Chamfer Length", min_val=0, default=0.1),
        "chamfer_divisions": PropertyMapping("Chamfer Divisions", min_val=0, default=0),
    }

    general_props = {
        # "thread_direction": PropertyMapping("Direction Prop B", default="RIGHT"),
        "bisect": PropertyMapping("Bisect", default=False),
        "trim": PropertyMapping("Trim", default=0),
        "triangulate": PropertyMapping("Triangulate", default=False),
        "bisect": PropertyMapping("Bisect", default=False),
        "tolerance": PropertyMapping("Tolerance", default=0),
        "scale": PropertyMapping("Scale", default=1),
        "shade_smooth": PropertyMapping("Shade Smooth", default=False),
    }

    def create(self, mesh: Mesh):
        """Create new fastener in mesh datablock"""
        threads_bottom, threads_top = self._mesh_threads()

        top_edges = threads_top[BMEdge]
        bottom_edges = threads_bottom[BMEdge]
        top_verts = threads_top[BMVert]

        # print(len(top_edges))
        # bounding_edges = [edge for edge in self.bm.edges if edge.is_boundary]
        # top_boundary = [edge for edge in bounding_edges if edge not in bottom_edges]

        # Round thread top termination (vanishing cone)
        top_verts = bmesh_helpers.polar_sort_verts(top_verts)

        # Create Head
        bmesh.ops.triangle_fill(self.bm, use_dissolve=True, edges=top_edges)
        # bmesh.ops.edgeloop_fill(self.bm, edges=top_boundary)

        if self.props.chamfer_length > 0:
            self._chamfer()

        if self.props.triangulate:
            bmesh.ops.triangulate(self.bm, faces=self.bm.faces)

        if self.props.trim != 0:
            self.trim()

        # if self.props.tolerance != 0:
        #     self._adjust_tolerance()

        if self.props.bisect:
            self._bisect()

        if self.props.scale != 0.0:
            self._scale()

        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])

        for f in self.bm.faces:
            f.smooth = self.props.shade_smooth

        self.bm.to_mesh(mesh)

    def _mesh_threads(self):
        """
        Create mesh threads in self.bm
        Returns: Tuple of bottom, top geom dicts whose keys are geometry types
        """

        def _np2d_to_v3d(coord):
            """[a,b] np to [b, 0, a] vector"""
            return Vector((coord[1], 0, coord[0]))

        if self.props.custom_thread_profile:
            profile = thread_profiles.Custom(
                self.props.pitch,
                self.props.length,
                self.props.minor_diameter - self.props.tolerance,
                self.props.major_diameter - self.props.tolerance,
                self.props.starts,
                self.props.root_weight,
                self.props.crest_weight,
                # tolerance=self.props.tolerance,
            )
        else:
            profile = thread_profiles.ISO_68_1(
                self.props.pitch,
                self.props.length - self.props.tolerance,
                self.props.major_diameter - self.props.tolerance,
                self.props.starts,
                self.props.thread_angle,
                # tolerance=self.props.tolerance,
            )

        profile_points = deque(profile.points)
        first_coord = profile_points.pop()
        prev_vert = self.bm.verts.new(_np2d_to_v3d(first_coord))

        # Create rest of profile verts
        while profile_points:
            # Create new vert
            co = _np2d_to_v3d(profile_points.pop())
            new_vert = self.bm.verts.new(co)

            # Create edge
            self.bm.edges.new((prev_vert, new_vert))

            # Assign new to last for next iteration
            prev_vert = new_vert

        # Assign vert feature type to layer
        # List is revered because thread points are processed LIFO
        for index, vert in enumerate(reversed(self.bm.verts[:])):
            if profile.feature_by_index(index) == "crest":
                vert[self.vert_layers.thread_crests] = 1
            else:
                vert[self.vert_layers.thread_roots] = 1

        start_verts = self.bm.verts[:]
        start_profile = start_verts + self.bm.edges[:]
        steps = self.props.thread_resolution
        step_z = self.props.pitch * self.props.starts / steps
        axis = Vector((0, 0, 1))
        dvec = Vector((0, 0, step_z))

        # NOTE: Not used
        # if self.props.thread_direction == "RIGHT":
        angle = radians(360)
        # else:
        #     angle = radians(-360)

        spun = bmesh.ops.spin(
            self.bm,
            geom=start_profile,
            angle=angle,
            steps=steps,
            dvec=dvec,
            axis=axis,
        )

        end_verts = dict_by_type(spun["geom_last"])[BMVert]
        merge_dist = 0.0001
        boundary_verts = [
            vert for vert in chain(start_verts, end_verts) if vert.is_boundary
        ]
        bmesh.ops.remove_doubles(self.bm, verts=boundary_verts, dist=merge_dist)

        # Cut Bottom
        geom = bmesh_helpers.bm_as_list(self.bm)
        loc = Vector((0, 0, self.props.pitch * self.props.starts))
        norm = Vector((0, 0, -1))
        cut_merge_dist = 0.001
        result = bmesh_helpers.trim(
            self.bm, geom, dist=cut_merge_dist, loc=loc, norm=norm, cap=True
        )
        thread_bottom = dict_by_type(result["geom_cut"])

        # Floor thread mesh
        min_z = bmesh_helpers.min_vert(self.bm.verts[:], "z").co.z
        for v in self.bm.verts[:]:
            v.co.z -= min_z

        # Cut Top
        geom = bmesh_helpers.bm_as_list(self.bm)
        loc = Vector((0, 0, self.props.length))
        norm = Vector((0, 0, 1))
        # merge_dist = 0.01
        # result = bmesh_helpers.trim(self.bm, geom, dist=merge_dist, loc=loc, norm=norm)
        # bmesh.ops.triangulate(self.bm, faces=self.bm.faces)

        result = bmesh.ops.bisect_plane(
            self.bm,
            geom=geom,
            plane_co=loc,
            plane_no=norm,
            # dist=merge_dist,
            clear_outer=True,
        )

        thread_top = dict_by_type(result["geom_cut"])

        return thread_bottom, thread_top

    def _chamfer(self):
        def _apply_chamfer(start_z, end_z):
            start_radius = self.major_radius
            end_radius = start_radius - (
                tan(self.props.chamfer) * self.props.chamfer_length
            )

            # Add chamfer divisions
            extra_divisions = self.props.chamfer_divisions
            if extra_divisions > 0:
                cut_norm = Vector((0, 0, 1))
                cut_loc = Vector((0, 0, 0))
                for cut_z in np.linspace(start_z, end_z, num=extra_divisions):
                    cut_loc.z = cut_z
                    geom = self.bm.faces[:] + self.bm.edges[:]
                    bmesh.ops.bisect_plane(
                        self.bm,
                        geom=geom,
                        dist=0.0001,
                        plane_co=cut_loc,
                        plane_no=cut_norm,
                    )

            min_z, max_z = sorted((start_z, end_z))
            value_in_range = lambda v: all((v.co.z >= min_z, v.co.z <= max_z))
            affected_verts = filter(value_in_range, self.bm.verts)
            for vert in affected_verts:
                xy, z = vert.co.xy, vert.co.z
                init_mag = xy.length
                target_mag = map_range(z, (start_z, end_z), (init_mag, end_radius))
                vert.co.xy = xy.normalized() * target_mag

        chamfer_len = self.props.chamfer_length
        bottom_range = (chamfer_len, 0)
        top_range = (self.props.length - chamfer_len, self.props.length)
        _apply_chamfer(*bottom_range)
        _apply_chamfer(*top_range)

    def _bisect(self) -> None:
        geom = bmesh_helpers.bm_as_list(self.bm)
        duplicate = bmesh.ops.duplicate(self.bm, geom=geom)
        front = dict_by_type(duplicate["geom_orig"])
        back = dict_by_type(duplicate["geom"])

        z_offset = -(self.props.length + self.props.head_length) / 2
        x_offset = max(self.props.head_diameter, self.props.major_diameter / 2 * 1.1)
        loc_offset = Vector((x_offset, 0, 0))
        height_offset = Vector((0, 0, z_offset))
        bmesh.ops.translate(self.bm, vec=height_offset, verts=self.bm.verts)

        front_rot = Euler((radians(90), 0, 0)).to_matrix()
        cent = Vector.Fill(3, 0)
        bmesh.ops.rotate(self.bm, cent=cent, verts=front[BMVert], matrix=front_rot)
        bmesh.ops.translate(self.bm, vec=loc_offset, verts=front[BMVert])

        back_rot = Euler((radians(-90), 0, 0)).to_matrix()
        bmesh.ops.rotate(self.bm, cent=cent, verts=back[BMVert], matrix=back_rot)
        bmesh.ops.translate(self.bm, vec=-loc_offset, verts=back[BMVert])

        geom = bmesh_helpers.bm_as_list(self.bm)
        co, no = Vector.Fill(3, 0), Vector((0, 0, -1))
        trimmed = bmesh.ops.bisect_plane(
            self.bm, geom=geom, clear_outer=True, plane_co=co, plane_no=no
        )

        cut = dict_by_type(trimmed["geom_cut"])
        edges = bmesh_helpers.shared_edges(cut[BMVert])
        fills = bmesh.ops.holes_fill(self.bm, edges=edges)
        bmesh.ops.triangulate(self.bm, faces=fills["faces"])
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.00001)

    # @property
    # def major_radius(self) -> float:
    #     return self.props.major_diameter / 2 - self.props.tolerance


@dataclass
class Screw(Fastener):
    props: FastenerProps
    type = "SCREW"
    heads = HEADS
    drivers = DRIVERS
    custom_thread_props = None

    type_props = {
        "pitch": PropertyMapping("Pitch", default=0.2),
        "length": PropertyMapping("Length", default=4),
        "thread_resolution": PropertyMapping("Thread Resolution", default=16),
        "major_diameter": PropertyMapping("Major Diameter", default=2),
        "starts": PropertyMapping("Thread Starts", min_val=1, default=1),
        "shank_length": PropertyMapping("Shank Length", min_val=0, default=1),
        # "chamfer": PropertyMapping("Chamfer", min_val=0, default=radians(15)),
        # "chamfer_length": PropertyMapping("Chamfer Length", min_val=0, default=0.1),
        # "chamfer_divisions": PropertyMapping("Chamfer Divisions", min_val=0, default=0),
        "screw_taper_factor": PropertyMapping("Taper Factor", min_val=0, default=0.1),
        "runout_length": PropertyMapping("Runout Length", min_val=0, default=0),
        "runout_offset": PropertyMapping("Runout Offset", default=0),
    }

    general_props = {
        # "thread_direction": PropertyMapping("Direction Prop B", default="RIGHT"),
        "triangulate": PropertyMapping("Triangulate", default=False),
        "bisect": PropertyMapping("Bisect", default=False),
        "tolerance": PropertyMapping("Tolerance", default=0),
        "scale": PropertyMapping("Scale", default=1),
        "shade_smooth": PropertyMapping("Shade Smooth", default=False),
    }

    def create(self, mesh: Mesh):
        """Create new fastener in mesh datablock"""
        # Create Threads
        if self.props.shank_length < self.props.length:
            threads_bottom, threads_top = self._mesh_threads()
            top_edges = threads_top[BMEdge]
            bottom_edges = threads_bottom[BMEdge]
            top_verts = threads_top[BMVert]

            # Round thread top termination (vanishing cone)
            top_verts = bmesh_helpers.polar_sort_verts(top_verts)
            bmesh_helpers.verts_to_circle(top_verts, self.major_radius)
            for vert in top_verts:
                vert.co.z = self.props.length - self.props.shank_length

            # Smooth Thread termination
            end = self.props.length - self.props.shank_length
            start = end - (self.props.pitch / 2)
            start_end = start, end
            bmesh_helpers.interp_vert_mag_along_axis(
                self.bm.verts,
                start_end,
                self.major_radius,
            )
        else:
            circle = bmesh.ops.create_circle(
                self.bm, radius=self.major_radius, segments=self.props.thread_resolution
            )
            top_edges = bmesh_helpers.shared_edges(circle["verts"])
            bottom_edges = top_edges
            bmesh.ops.triangle_fill(self.bm, use_dissolve=True, edges=bottom_edges)

        # Create Shank
        if self.props.shank_length != 0:
            top_edges = self._create_shank(top_edges)

        # Create Head
        if self.props.head_type != "NONE":
            # Create and merge head mesh
            head_bm = self._create_head()
            head_verts, head_faces = bmesh_helpers.merge_bmesh(head_bm, self.bm)

            # Set head height
            offset = Vector((0, 0, self.props.length - self.props.tolerance))
            bmesh.ops.translate(self.bm, vec=offset, verts=head_verts)

            head_opening = filter(lambda v: v.is_boundary, head_verts)
            connection_loop = bmesh_helpers.shared_edges(head_opening)

            # Join shank/thread to head
            open_loops = connection_loop + top_edges
            bmesh.ops.bridge_loops(self.bm, edges=open_loops)
            # bmesh.ops.triangle_fill(self.bm, edges=open_loops)
        else:
            bmesh.ops.triangle_fill(self.bm, use_dissolve=True, edges=top_edges)

        if self.props.chamfer_length > 0:
            self._chamfer()

        if self.props.driver_type != "NONE":
            driver_bm = self._create_driver()
            self.bm = boolean_bm(self.bm, driver_bm, xform=self._driver_xform)
            driver_bm.free()

        if (
            self.props.screw_taper_factor > 0
            and self.props.shank_length != self.props.length
        ):
            self._apply_screw_taper()

        if self.props.triangulate:
            bmesh.ops.triangulate(self.bm, faces=self.bm.faces)

        # if self.props.tolerance != 0:
        #     self._adjust_tolerance()

        if self.props.bisect:
            self._bisect()

        if self.props.scale != 0.0:
            self._scale()

        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])

        for f in self.bm.faces:
            f.smooth = self.props.shade_smooth

        self.bm.to_mesh(mesh)

    def _apply_screw_taper(self):
        taper_length = self.props.length * self.props.screw_taper_factor
        start_z = taper_length
        end_z = 0
        end_radius = 0
        affected_verts = list(filter(lambda v: v.co.z < start_z, self.bm.verts))
        for vert in affected_verts:
            is_crest = vert[self.vert_layers.thread_crests] == 1
            # else it's a root vert

            xy, z = vert.co.xy, vert.co.z
            init_mag = xy.length
            target_mag = map_range(z, (start_z, end_z), (init_mag, end_radius))
            new_root_xy = xy.normalized() * target_mag

            if not is_crest:
                vert.co.xy = new_root_xy
            else:
                vert.co.xy += new_root_xy - xy

        # Merge by distance to cleanup point
        bmesh.ops.remove_doubles(self.bm, verts=affected_verts, dist=0.0001)

    def _mesh_threads(self):
        """
        Create mesh threads in self.bm
        Returns: Tuple of bottom, top geom dicts whose keys are geometry types
        """

        def _np2d_to_v3d(coord):
            """[a,b] np to [b, 0, a] vector"""
            return Vector((coord[1], 0, coord[0]))

        profile = thread_profiles.ISO_68_1(
            self.props.pitch,
            self.props.length,
            self.props.major_diameter - self.props.tolerance,
            self.props.starts,
            self.props.thread_angle,
            sharp_crest=True,
            # tolerance=self.props.tolerance,
        )

        # Create profile verts
        profile_points = deque(profile.points)
        first_coord = profile_points.pop()
        prev_vert = self.bm.verts.new(_np2d_to_v3d(first_coord))
        while profile_points:
            co = _np2d_to_v3d(profile_points.pop())
            new_vert = self.bm.verts.new(co)
            self.bm.edges.new((prev_vert, new_vert))
            prev_vert = new_vert

        # Assign vert feature type to layer
        # List is revered because thread points are processed LIFO
        # TODO: Move to point initialization like bolt
        for index, vert in enumerate(reversed(self.bm.verts[:])):
            if profile.feature_by_index(index) == "crest":
                vert[self.vert_layers.thread_crests] = 1
            else:
                vert[self.vert_layers.thread_roots] = 1

        # Collapse sharp points
        bmesh.ops.dissolve_degenerate(self.bm, dist=0.0001)

        start_verts = self.bm.verts[:]
        start_profile = start_verts + self.bm.edges[:]
        steps = self.props.thread_resolution
        step_z = self.props.pitch * self.props.starts / steps
        axis = Vector((0, 0, 1))
        dvec = Vector((0, 0, step_z))
        # if self.props.thread_direction == "RIGHT":
        angle = radians(360)
        # else:
        #     angle = radians(-360)

        spun = bmesh.ops.spin(
            self.bm,
            geom=start_profile,
            angle=angle,
            steps=steps,
            dvec=dvec,
            axis=axis,
        )

        end_verts = dict_by_type(spun["geom_last"])[BMVert]
        merge_dist = 0.0001
        boundary_verts = [
            vert for vert in chain(start_verts, end_verts) if vert.is_boundary
        ]
        bmesh.ops.remove_doubles(self.bm, verts=boundary_verts, dist=merge_dist)

        # Cut Bottom
        geom = bmesh_helpers.bm_as_list(self.bm)
        loc = Vector((0, 0, self.props.pitch * self.props.starts))
        norm = Vector((0, 0, -1))
        merge_dist = 0.01
        result = bmesh_helpers.trim(
            self.bm, geom, dist=merge_dist, loc=loc, norm=norm, cap=True
        )
        thread_bottom = dict_by_type(result["geom_cut"])

        # Floor thread mesh
        min_z = bmesh_helpers.min_vert(self.bm.verts[:], "z").co.z
        for v in self.bm.verts[:]:
            v.co.z -= min_z

        # Cut Top
        geom = bmesh_helpers.bm_as_list(self.bm)
        loc = Vector((0, 0, self.props.length - self.props.shank_length))
        norm = Vector((0, 0, 1))
        result = bmesh_helpers.trim(self.bm, geom, loc=loc, norm=norm)
        thread_top = dict_by_type(result["geom_cut"])

        # Tri divide ngons
        ngons = [f for f in self.bm.faces if len(f.edges[:]) > 4]
        bmesh.ops.triangulate(self.bm, faces=ngons)

        return thread_bottom, thread_top

    @property
    def _driver_xform(self):
        boolean_buffer = 0.001
        z = (self.props.length - self.props.tolerance) + boolean_buffer
        if self.props.head_type != "NONE":
            z += self.props.head_length - self.props.tolerance
        location = Matrix.Translation((0, 0, z))
        rotation = Matrix.Rotation(radians(180), 4, "X")
        # scale = Matrix.Scale(self.props.driver_diameter, 4)
        return location @ rotation

    def _chamfer(self):
        start_z = self.props.chamfer_length
        end_z = 0
        start_radius = self.major_radius
        end_radius = start_radius - (
            tan(self.props.chamfer) * self.props.chamfer_length
        )

        # Add chamfer divisions
        extra_divisions = self.props.chamfer_divisions
        if extra_divisions > 0:
            cut_norm = Vector((0, 0, 1))
            cut_loc = Vector((0, 0, 0))
            for cut_z in np.linspace(start_z, end_z, num=extra_divisions):
                cut_loc.z = cut_z
                geom = self.bm.faces[:] + self.bm.edges[:]
                bmesh.ops.bisect_plane(
                    self.bm, geom=geom, dist=0.0001, plane_co=cut_loc, plane_no=cut_norm
                )

        affected_verts = filter(lambda v: v.co.z < start_z, self.bm.verts)
        for vert in affected_verts:
            xy, z = vert.co.xy, vert.co.z
            init_mag = xy.length
            target_mag = map_range(z, (start_z, end_z), (init_mag, end_radius))
            vert.co.xy = xy.normalized() * target_mag

    def _bisect(self) -> None:
        geom = bmesh_helpers.bm_as_list(self.bm)
        duplicate = bmesh.ops.duplicate(self.bm, geom=geom)
        front = dict_by_type(duplicate["geom_orig"])
        back = dict_by_type(duplicate["geom"])

        z_offset = -(self.props.length + self.props.head_length) / 2
        x_offset = max(self.props.head_diameter, self.props.major_diameter / 2 * 1.1)
        loc_offset = Vector((x_offset, 0, 0))
        height_offset = Vector((0, 0, z_offset))
        bmesh.ops.translate(self.bm, vec=height_offset, verts=self.bm.verts)

        front_rot = Euler((radians(90), 0, 0)).to_matrix()
        cent = Vector.Fill(3, 0)
        bmesh.ops.rotate(self.bm, cent=cent, verts=front[BMVert], matrix=front_rot)
        bmesh.ops.translate(self.bm, vec=loc_offset, verts=front[BMVert])

        back_rot = Euler((radians(-90), 0, 0)).to_matrix()
        bmesh.ops.rotate(self.bm, cent=cent, verts=back[BMVert], matrix=back_rot)
        bmesh.ops.translate(self.bm, vec=-loc_offset, verts=back[BMVert])

        geom = bmesh_helpers.bm_as_list(self.bm)
        co, no = Vector.Fill(3, 0), Vector((0, 0, -1))
        trimmed = bmesh.ops.bisect_plane(
            self.bm, geom=geom, clear_outer=True, plane_co=co, plane_no=no
        )

        cut = dict_by_type(trimmed["geom_cut"])
        edges = bmesh_helpers.shared_edges(cut[BMVert])
        fills = bmesh.ops.holes_fill(self.bm, edges=edges)
        bmesh.ops.triangulate(self.bm, faces=fills["faces"])
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.00001)

    # @property
    # def major_radius(self) -> float:
    #     return self.props.major_diameter / 2 - self.props.tolerance

    # def _create_shank(self, edges: Union[List[BMEdge], None]) -> List[BMEdge]:
    #     extrusion = bmesh.ops.extrude_edge_only(self.bm, edges=edges)["geom"]
    #     extrusion = dict_by_type(extrusion)

    #     for vert in extrusion[BMVert]:
    #         xy: Vector = vert.co.xy
    #         mag = xy.length
    #         # tolerance = xy.normalized() * self.props.tolerance
    #         new_xy = xy.normalized() * self.major_radius
    #         offset = xy.normalized() * self.props.runout_offset
    #         vert.co.xy = new_xy + offset

    #     if self.props.runout_length != 0:
    #         runout_edges = extrusion[BMEdge]
    #         runout_verts = extrusion[BMVert]
    #         extrusion = bmesh.ops.extrude_edge_only(self.bm, edges=runout_edges)["geom"]
    #         extrusion = dict_by_type(extrusion)
    #         for vert in runout_verts:
    #             vert.co.z += self.props.runout_length

    #     for vert in extrusion[BMVert]:
    #         vert.co.z += self.props.shank_length - self.props.tolerance

    #     return extrusion[BMEdge]

    def _create_head(self) -> BMesh:
        # Create head mesh, apply modifiers and remove
        head: FastenerHead = self.heads[self.props.head_type](self.props)
        head.apply_transforms()
        return head.bm

    def _create_driver(self) -> BMesh:
        driver = self.drivers[self.props.driver_type](self.props)
        driver.apply_transforms()
        return driver.bm


builders = {subclass.type: subclass for subclass in Fastener.__subclasses__()}
