# context.area: VIEW_3D
from cmath import polar
from collections import deque
from math import cos, sin, pi, radians
from typing import Dict, Iterable, List, Set, Tuple, Union
from itertools import accumulate, chain

import bpy
import bmesh
from bpy.types import Mesh, Object
from mathutils import Vector, Matrix
from bmesh.types import BMVert, BMEdge, BMFace, BMesh, BMLayerCollection

from .bmesh_filters import dict_by_type

Geom = List[Union[BMVert, BMEdge, BMFace]]


def map_range(value: float, range_a: Tuple[float, float], range_b: Tuple[float, float]):
    (a1, a2), (b1, b2) = range_a, range_b
    remapped = b1 + ((value - a1) * (b2 - b1) / (a2 - a1))
    return remapped


def angle_crease_mesh(mesh: Union[Mesh, BMesh], crease: float) -> None:
    if isinstance(mesh, Mesh):
        bm = bmesh.new()
        bm.from_mesh(mesh)
    else:
        bm = mesh

    crease_layer = bm.edges.layers.crease.verify()
    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            edge[crease_layer] = 1
            continue
        if edge.calc_face_angle() > crease:
            edge[crease_layer] = 1

    if isinstance(mesh, Mesh):
        bm.to_mesh(mesh)


def polar_sort_verts(verts: Iterable[BMVert], axis: str = "xy") -> List[BMVert]:
    """
    TODO: Add custom origin arg
    TODO: Document
    """

    def _vert_co_as_polar_angle(vert: BMVert) -> float:
        co = getattr(vert.co, axis).to_tuple()
        co = complex(*co)
        angle = polar(co)[1]
        return angle

    return sorted(verts, key=_vert_co_as_polar_angle)


def axis_sorted_verts(verts: List[BMVert], axis: str):
    return sorted(verts, key=lambda v: getattr(v.co, axis))


def min_vert(verts: List[BMVert], axis: str) -> BMVert:
    return axis_sorted_verts(verts, axis)[0]


def max_vert(verts: List[BMVert], axis: str) -> BMVert:
    return axis_sorted_verts(verts, axis)[-1]


def min_max_verts(verts: List[BMVert], axis: str) -> Tuple[BMVert, BMVert]:
    sorted_verts = axis_sorted_verts(verts, axis)
    return sorted_verts[0], sorted_verts[-1]


def bm_as_list(bm):
    return bm.verts[:] + bm.edges[:] + bm.faces[:]


def verts_to_circle(verts: List[BMVert], radius):
    """ TODO: Give it proper features """
    angle = radians(-90)
    ref_circle, _, _ = circle_points(len(verts), radius, angle)
    ref_circle.reverse()
    for vert, ref_pt in zip(verts, ref_circle):
        vert.co = ref_pt
        # vert.co.x *= -1
        # vert.co.y *= -1


def circle_points(
    npoints: int, radius: float, init_angle: float = 0
) -> Tuple[List[Vector], List[Vector], List[Vector]]:
    """
    Return a circle of vectors with outward normals and tangents
    Clockwise from first position (0, 1, 0)
    Tangent is left handed
    Args:
        npoints: (int): Number of points in circle
        radius: (float): Radius of circle to generate
        init_angle: (float): Offset initial angle in radians

    Returns (positions, normals, tangents)
    """
    positions: List[Vector] = []
    normals: List[Vector] = []
    tangents: List[Vector] = []
    angle_step = (2 * pi) / npoints
    for index in range(npoints):
        angle = init_angle + (angle_step * index)
        position = Vector((sin(angle) * radius, cos(angle) * radius, 0))
        normal = position.normalized()
        tangent = normal.cross(Vector((0, 0, 1)))
        positions.append(position)
        normals.append(normal)
        tangents.append(tangent)

    return positions, normals, tangents


def islands(bm: BMesh, verts: Iterable[BMVert]) -> List[List[BMVert]]:
    input_verts = set(verts)
    ungrouped_verts = set(verts)
    islands = []

    while ungrouped_verts:
        search_queue = deque([ungrouped_verts.pop(),])
        island_verts = set()
        while search_queue:
            vert = search_queue.pop()
            island_verts.add(vert)

            neighbors = dict_by_type(
                bmesh.ops.region_extend(bm, geom=[vert], use_face_step=True)["geom"]
            )
            neighbor_verts = set(neighbors[BMVert]).intersection(input_verts)
            neighbor_verts -= island_verts

            search_queue.extend(neighbor_verts)
            island_verts = island_verts.union(neighbor_verts)

        ungrouped_verts -= island_verts
        islands.append(list(island_verts))

    return islands


def verts_in_range(
    verts: List[BMVert], bbox_min: Vector, bbox_max: Vector
) -> List[BMVert]:
    """Return verts whose coordinates are within the specified bounding box points

    Args:
        verts (List[BMVert]): List of vertex candidates
        bbox_min (Vector): Minimum bounding box point
        bbox_max (Vector): Maximum bounding box point
    """

    def _vert_in_range(vert):
        def _value_tests():
            yield vert.co.x >= bbox_min.x and vert.co.x <= bbox_max.x
            yield vert.co.y >= bbox_min.y and vert.co.y <= bbox_max.y
            yield vert.co.z >= bbox_min.z and vert.co.z <= bbox_max.z

        return all(_value_tests)

    return map(verts, _vert_in_range)


def shared_faces(verts: Iterable[BMVert]) -> List[BMFace]:
    vert_set = set(verts)
    faces = set()
    all_faces = chain.from_iterable(vert.link_faces for vert in vert_set)
    for face in all_faces:
        if set(face.verts).issubset(vert_set):
            faces.add(face)
    return list(faces)


def shared_edges(verts: Iterable[BMVert]) -> List[BMEdge]:
    vert_set = set(verts)
    edges = set()
    all_edges = chain.from_iterable(vert.link_edges for vert in vert_set)
    for edge in all_edges:
        if set(edge.verts).issubset(vert_set):
            edges.add(edge)
    return list(edges)


def verts_from_faces(faces: Iterable[BMFace]) -> Set[BMVert]:
    """ Return unique vertices used by faces """
    verts = set()
    for face in faces:
        valid_verts = [vert for vert in face.verts if vert.is_valid]
        verts = verts.union(valid_verts)
    return verts


def merge_bmesh(bm_a: BMesh, bm_b: BMesh) -> Tuple[List[BMVert], List[BMFace]]:
    """
    Copy faces and verts from bm_a to bm_b
    Return tuple containing the lists of the new verts and faces
    """
    bm_a.verts.ensure_lookup_table()
    verts = [bm_b.verts.new(vert.co) for vert in bm_a.verts]
    faces = []
    for face in bm_a.faces:
        indexes = [vert.index for vert in face.verts]
        face_verts = [verts[index] for index in indexes]
        faces.append(bm_b.faces.new(face_verts))
    return (verts, faces)


def interp_vert_mag_along_axis(
    verts: List[BMVert],
    start_end: Tuple[float, float],
    target_mag: float,
    scaler_axis: str = "z",
    mag_axis: str = "xy",
) -> None:
    """ Blend magnitude of mag_axig form existing value to target_mag along scaler_axis in start_end range"""
    # affected = "xyz".replace(axis, "")
    start, end = start_end
    for vert in verts:
        scaler_axis_val = getattr(vert.co, scaler_axis)
        if scaler_axis_val < start or scaler_axis_val > end:
            continue

        current_val: Vector = getattr(vert.co, mag_axis)
        from_range = start_end
        to_range = (current_val.length, target_mag)
        interp_amnt = map_range(scaler_axis_val, from_range, to_range)

        # Vector.slerp()
        # difference = (target_mag / current_val.length) * interp_amnt
        new_value = current_val.normalized() * interp_amnt
        setattr(vert.co, mag_axis, new_value)


def trim(
    bm: BMesh,
    geom: Geom,
    dist: float = 0.001,
    loc: Vector = Vector((0, 0, 0)),
    norm: Vector = Vector((0, 0, 1)),
    cap: bool = False,
) -> Dict[str, Geom]:
    result = bmesh.ops.bisect_plane(
        bm, geom=geom, plane_co=loc, plane_no=norm, dist=dist, clear_outer=True
    )

    if cap:
        caps = []
        cut_geo = dict_by_type(result["geom_cut"])
        # if BMVert in cut_geo:
        vert_islands = islands(bm, verts=cut_geo[BMVert])
        for verts in vert_islands:
            edges = shared_edges(verts)
            caps.append(bmesh.ops.edgeloop_fill(bm, edges=edges))
            # caps.append(
            #     bmesh.ops.triangle_fill(
            #         bm, use_beauty=True, edges=edges, use_dissolve=True
            #     )["geom"]
            # )

        result["cap"] = caps
    return result


def bisect_geometry(
    bm: BMesh,
    geom: Geom,
    dist: float = 0.00001,
    loc: Vector = Vector((0, 0, 0)),
    norm: Vector = Vector((0, 0, 1)),
) -> Dict[str, Geom]:
    """ Bisect Bmesh Wrapper
    TODO: Better type sorting

    Args:
        bm (BMesh): bmesh
        geom (Geom): geometry to bisect, needs faces, edges, verts
        dist (float): Distance to create new cut
        loc (Vector): Location of cut
        norm (Vector): Cutter normal

    Returns:
        Dict[str, List[Geom]]:
            "above": Verts above cut.
            "below": Verts below cut.
            "cut": New cut geometry, verts and edges
    """

    def _vert_in_front(vert) -> bool:
        """ Check wether vert position is in front of location and normal"""
        # return norm.dot(vert.co - loc) >= 0
        return norm.dot((vert.co - loc).normalized()) >= 0

    # input_faces = [i for i in geom if isinstance(i, BMFace)]
    input_faces = dict_by_type(geom)[BMFace]
    input_verts = verts_from_faces(input_faces)
    result = bmesh.ops.bisect_plane(
        bm, geom=geom, dist=dist, plane_co=loc, plane_no=norm
    )
    cut_geom = result["geom_cut"]
    above_verts = set(filter(_vert_in_front, input_verts))
    below_verts = input_verts - above_verts
    above_verts -= set(cut_geom)
    result = {
        "above": list(above_verts),
        "below": list(below_verts),
        "cut": cut_geom,
    }
    return result


def calc_vertex_normals(
    verts: Iterable[BMVert], face_mask: Union[None, Iterable[BMFace]] = None
) -> List[Vector]:
    """Caclulate vertex normal from link faces with optional face masking

    Args:
        verts (List[BMVert]): verts to calculate normals for
        face_mask (Union[None, List[BMFace]]): Optional list of faces to limit calculation to
    """
    if face_mask is not None:
        face_mask = set(face_mask)

    def _calc_normal(vert: BMVert) -> Vector:
        if face_mask is not None:
            link_faces = set(vert.link_faces).intersection(face_mask)
        else:
            link_faces = vert.link_faces
        # print("link_faces", link_faces)
        if len(link_faces) == 0:
            return Vector((0, 0, 0))
        normals = [face.normal for face in link_faces]
        scaler = 1 / len(normals)

        # Average and normalize
        sum_normals = deque(accumulate(normals), maxlen=1).pop()
        average = sum_normals * scaler
        return average.normalized()

    return [_calc_normal(vert) for vert in verts]


def grow_vert_island(bm: BMesh, verts: Iterable[BMVert], stop_layer: BMLayerCollection):
    """
    Grow all vertices across faces until the hit named attribute with a value > 1 and stop
    """
    island_verts = set(verts)
    active_verts = deque(verts)
    while active_verts:
        vert = active_verts.pop()
        # Don't grow stop layer value is 0
        if vert[stop_layer] != 0:  #
            continue

        geom = [vert]
        neighbors = dict_by_type(
            bmesh.ops.region_extend(bm, geom=geom, use_face_step=True)["geom"]
        )
        neighbor_verts = set(neighbors[BMVert]) - island_verts
        island_verts = island_verts.union(neighbor_verts)
        active_verts.extend(neighbor_verts)

    return list(island_verts)


def bmesh_to_object(bm: BMesh, name: str) -> Object:
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    return bpy.data.objects.new(name, object_data=mesh)


def temp_subd_modifier(bm: BMesh, levels: int = 2):
    # Setup
    mesh = bpy.data.meshes.new("_temp")
    bm.to_mesh(mesh)
    temp_obj = bpy.data.objects.new("_temp", object_data=mesh)
    bpy.context.scene.collection.objects.link(temp_obj)
    subd = temp_obj.modifiers.new('subd', type="SUBSURF")
    subd.levels = levels

    # Apply subd
    dg = bpy.context.evaluated_depsgraph_get()
    evaled = temp_obj.evaluated_get(dg)
    mesh_result = evaled.data.copy()
    bm.clear()
    bm.from_mesh(mesh_result)

    # Cleanup
    bpy.data.objects.remove(temp_obj)
    return bm




def boolean_bm(
    target: BMesh,
    bool_mesh: BMesh,
    operation: str = "DIFFERENCE",
    xform: Matrix = Matrix.Identity(4),
    solver: str = "EXACT",
) -> Mesh:
    # valid_operations = ("UNION", "INTERSECT", "DIFFERENCE")

    bool_obj_a = bmesh_to_object(target, "__TEMP_BOOL_A")
    bool_obj_b = bmesh_to_object(bool_mesh, "__TEMP_BOOL_B")
    bpy.context.scene.collection.objects.link(bool_obj_a)
    bpy.context.scene.collection.objects.link(bool_obj_b)

    # Transform object b
    bool_obj_b.matrix_world = xform

    modifier = bool_obj_a.modifiers.new(name="temp_bool", type="BOOLEAN")
    modifier.solver = solver
    modifier.object = bool_obj_b
    modifier.operation = operation

    # Get resulting mesh
    dg = bpy.context.evaluated_depsgraph_get()
    evaled = bool_obj_a.evaluated_get(dg)
    mesh_result = evaled.data.copy()
    target.clear()
    target.from_mesh(mesh_result)

    # Cleanup
    for obj in (bool_obj_a, bool_obj_b):
        mesh = obj.data
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)

    return target
