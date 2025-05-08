from typing import Iterable, Union

import bpy
import bmesh
from bmesh.types import BMesh, BMVert, BMFace, BMEdge
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import numpy as np
from numpy import cos, sin, tau

from . import bmesh_helpers
from . import bmesh_filters

Geom = Union[
    Iterable[BMVert],
    Iterable[BMFace],
    Iterable[BMEdge],
]

identity = Matrix.Identity(4)


def polygon(
    bm: BMesh, geom: Geom, sides: int = 6, xform: Matrix = identity
) -> Geom:
    # Create cut place locations and normals
    angles = np.linspace(start=0, stop=tau, num=sides, endpoint=False, dtype=float)
    cut_locs = [Vector((sin(angle), cos(angle), 0)) for angle in angles]
    normals = [(v * -1).normalized() for v in cut_locs]

    # Assign unique vert layer to record bisection lines
    # Find a unique name for the layer
    layer_index = 0
    bisect_layer_name =f"bisect_lines{layer_index}"
    while bm.verts.layers.int.get(bisect_layer_name) is not None:
        layer_index += 1

    # Create the layer
    bisect_vert_layer = bm.verts.layers.int.new(bisect_layer_name)

    # Apply transformations
    cut_locs = [xform @ v for v in cut_locs]
    normals = [(xform @ n).normalized() for n in normals]

    # Cut Geometry
    bisect_geom = geom
    for loc, norm in zip(cut_locs, normals):
        cut_geom = bmesh_helpers.bisect_geometry(
            bm,
            geom=bisect_geom,
            loc=loc,
            norm=norm,
        )
        cut_verts = bmesh_filters.dict_by_type(cut_geom['cut'])[BMVert]
        for vert in cut_verts:
            vert[bisect_vert_layer] = 1

        next_geom_verts = cut_geom['above'] + cut_geom['cut'] + cut_geom['below']
        next_geom_faces = bmesh_helpers.shared_faces(next_geom_verts)
        next_geom_edges = bmesh_filters.unique_face_edges(next_geom_faces)
        bisect_geom = next_geom_faces + next_geom_edges

    # Find and return the expected polygon
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    search_results = tree.find_nearest_range(xform.translation)
    search_results.sort(key=lambda result: result[3])
    closest_face_id = search_results[0][2]

    closest_face_verts = bmesh_helpers.verts_from_faces([bm.faces[closest_face_id]])
    island_verts = bmesh_helpers.grow_vert_island(bm, closest_face_verts, bisect_vert_layer)
    bm.verts.layers.int.remove(bisect_vert_layer)
    return bmesh_helpers.shared_faces(island_verts)


def cross(
    bm: BMesh,
    geom: Geom,
    x_len: float = 0,
    x_width: float = 0,
    y_len: float = 0,
    y_width: float = 0,
    xform: Matrix = identity,
) -> Geom:

    def _is_x_rect():
        def _attrib_tests():
            yield y_len < x_len
            yield x_width != 0
        return all(_attrib_tests())

    def _is_y_rect():
        def _attrib_test():
            yield x_len < y_len
            yield y_width != 0
        return all(_attrib_test())

    if _is_x_rect():
        # Cut to width
        all_cut_verts = set()
        next_cut_geom = geom
        for cut_orient in (1, -1):
            cut_loc = Vector((0, x_width / 2, 0)) * cut_orient
            cut_norm = Vector((0, -1, 0)) * cut_orient

            cut_geom = bmesh_helpers.bisect_geometry(
                bm,
                geom=next_cut_geom,
                loc=cut_loc,
                norm=cut_norm,
            )

            cut_output = bmesh_filters.dict_by_type(cut_geom['cut'])
            cut_verts = cut_output[BMVert]
            all_cut_verts = all_cut_verts.union(cut_verts)
            next_cut_verts = cut_geom['above'] + cut_verts
            next_cut_faces = bmesh_helpers.shared_faces(next_cut_verts)
            next_cut_edges = bmesh_helpers.shared_edges(next_cut_verts)
            next_cut_geom = next_cut_edges + next_cut_faces

        inside_faces = bmesh_helpers.shared_faces(all_cut_verts)


cutters = {
    "POLYGON": polygon,
    "CROSS": cross,
}


def test_func():
    target_obj = bpy.context.object
    mesh = target_obj.data
    bm = bmesh.from_edit_mesh(mesh)
    bm.clear()
    bmesh.ops.create_grid(bm, x_segments=8, y_segments=8, size=5)
    bmesh.update_edit_mesh(mesh)
