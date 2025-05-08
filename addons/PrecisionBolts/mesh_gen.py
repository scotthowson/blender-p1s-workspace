from itertools import chain
from math import pi, radians
from typing import Deque, List, Tuple

import bpy
import bmesh
from bmesh.types import BMVert, BMFace, BMEdge, BMesh
from bpy.types import Mesh
from mathutils import Matrix, Vector, Euler
from .bmesh_helpers import bm_as_list


def new_grid_mesh(
    name: str,
    divisions: Tuple[int, int] = (1, 1),
    transform: Matrix = Matrix.Identity(4),
) -> Mesh:
    """
    Create and return a new grid mesh
    """
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bm.loops.layers.uv.new("UV")
    bmesh.ops.create_grid(
        bm,
        x_segments=divisions[0],
        y_segments=divisions[1],
        size=1,
        matrix=transform,
        calc_uvs=True,
    )

    bm.to_mesh(mesh)
    bm.free()
    return mesh


def new_cylinder_mesh(
    radius: float = 1, segements: int = 6, depth: float = 1,
) -> BMesh:
    # mesh = bpy.data.meshes.new("cross")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=segements, radius=radius)

    extrusion = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    translate = Vector((0, 0, depth))
    verts = [i for i in extrusion["geom"] if isinstance(i, BMVert)]
    bmesh.ops.translate(bm, vec=translate, verts=verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def new_cross_bmesh(
    x_length: float = 4,
    x_width: float = 1,
    y_length: float = 4,
    y_width: float = 1,
    rotation: Euler = Euler((0, 0, 0)),
    depth: float = 1,
    center: bool = True,
) -> BMesh:
    x_corner = Vector((x_length, x_width, 0))
    y_corner = Vector((y_width, y_length, 0))
    has_equal_sides = (x_corner - y_corner).length < 0.0001
    is_x_rect = x_corner.y >= y_corner.y
    is_y_rect = y_corner.x >= x_corner.x
    is_rect = any((is_x_rect, is_y_rect, has_equal_sides))

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    # if is_rect:
    if is_rect:
        if is_x_rect or has_equal_sides:
            scaler = Vector((x_length, x_width, 1))
        else:
            scaler = Vector((y_width, y_length, 1))

        bmesh.ops.scale(bm, vec=scaler, verts=bm.verts)
    else:
        # Set max dimensions
        scaler = Vector((x_length, y_length, 1))
        bmesh.ops.scale(bm, vec=scaler, verts=bm.verts)

        # Add width cuts
        x_cut_dist = x_width / 2
        y_cut_dist = y_width / 2
        cuts = (
            Vector((0, -x_cut_dist, 0)),
            Vector((0, x_cut_dist, 0)),
            Vector((-y_cut_dist, 0, 0)),
            Vector((y_cut_dist, 0, 0)),
        )
        x_norm = Vector((1, 0, 0))
        y_norm = Vector((0, 1, 0))
        normals = (-y_norm, y_norm, -x_norm, x_norm)

        for co, no in zip(cuts, normals):
            geom = bm_as_list(bm)
            bmesh.ops.bisect_plane(bm, geom=geom, dist=0.0001, plane_co=co, plane_no=no)

        # Delete corners
        corners = filter(lambda v: len(v.link_faces) == 1, bm.verts)
        bmesh.ops.delete(bm, geom=list(corners))

    if depth != 0:
        extrusion = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        translate = Vector((0, 0, depth))
        verts = [i for i in extrusion["geom"] if isinstance(i, BMVert)]
        bmesh.ops.translate(bm, vec=translate, verts=verts)

    for v in bm.verts:
        v.co.rotate(rotation)

    if center:
        offset = Vector((0, 0, -depth * 0.5))
        bmesh.ops.translate(bm, vec=offset, verts=bm.verts[:])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def _new_cross_bmesh(
    x_length: float = 4,
    x_width: float = 1,
    y_length: float = 4,
    y_width: float = 1,
    rotation: Euler = Euler((0, 0, 0)),
    depth: float = 1,
    center: bool = True,
) -> BMesh:
    """ ONLY HERE FOR REFERENCE """
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=3, y_segments=3, size=0.5 * 3)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Remove corner points
    to_delete = (0, 3, 12, 15)
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in to_delete])
    bm.verts.ensure_lookup_table()

    ungrouped_pts = set(range(len(bm.verts)))
    x_corner_ids = set((2, 6, 5, 9))
    x_corners = [bm.verts[i] for i in x_corner_ids]
    y_corner_ids = set((0, 1, 10, 11))
    y_corners = [bm.verts[i] for i in y_corner_ids]
    ungrouped_pts = ungrouped_pts - x_corner_ids - y_corner_ids
    root_points = [bm.verts[i] for i in ungrouped_pts]
    to_delete = []

    delete_x = any((x_width <= 0, x_length <= 0, y_width > x_length))
    delete_y = any((y_width <= 0, y_length <= 0, x_width >= y_length))

    if delete_x:
        to_delete.extend(x_corners)
    else:
        # Set Initial Flank Scale
        x_scale = Vector((0.33, 1, 1))
        bmesh.ops.scale(bm, vec=x_scale, verts=x_corners)
        # Set Scale
        x_scale = Vector((x_length, x_width, 1))
        bmesh.ops.scale(bm, vec=x_scale, verts=x_corners)

    if delete_y:
        to_delete.extend(y_corners)
    else:
        # Set Initial Flank Scale
        y_scale = Vector((1, 0.33, 1))
        bmesh.ops.scale(bm, vec=y_scale, verts=y_corners)
        # Set Scale
        y_scale = Vector((y_width, y_length, 1))
        bmesh.ops.scale(bm, vec=y_scale, verts=y_corners)

    # Clear extra geo
    bmesh.ops.delete(bm, geom=to_delete)

    # Scale inside corners
    scale = Vector((y_width, x_width, 1))
    bmesh.ops.scale(bm, vec=scale, verts=root_points)

    if depth != 0:
        extrusion = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        translate = Vector((0, 0, depth))
        verts = [i for i in extrusion["geom"] if isinstance(i, BMVert)]
        bmesh.ops.translate(bm, vec=translate, verts=verts)

    for v in bm.verts:
        v.co.rotate(rotation)

    if center:
        offset = Vector((0, 0, -depth * 0.5))
        bmesh.ops.translate(bm, vec=offset, verts=bm.verts[:])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm

