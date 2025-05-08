"""
Convenience functions for filtering bmesh iterables by type and layer value
"""

from itertools import chain, cycle, zip_longest
from bmesh.types import (
    BMVert,
    BMFace,
    BMEdge,
    BMLayerItem,
    BMLayerAccessVert,
    BMLayerAccessFace,
)
from mathutils import Vector
from typing import Dict, Generator, Iterable, Iterator, List, Tuple, Union

BMESH_LAYER_VALUE_TYPES = (float, int, Vector, str)
_LayerValueType = Union[float, int, Vector, str]


def dict_by_type(
    target: Iterable[Union[BMVert, BMEdge, BMFace]],
) -> Dict[object, List[Union[BMVert, BMEdge, BMFace]]]:
    result = {}
    for item in target:
        item_type = type(item)
        result.setdefault(item_type, [])
        result[item_type].append(item)
    return result


def unique_face_verts(faces: Iterable[BMFace]) -> List[BMVert]:
    unique_verts = set()
    for face in faces:
        for vert in face.verts:
            unique_verts.add(vert)
    return list(unique_verts)


def unique_edge_verts(edges: Iterable[BMEdge]) -> List[BMVert]:
    unique_verts = set()
    for edge in edges:
        unique_verts = unique_verts.union(edge.verts)
    return list(unique_verts)


def unique_vert_edges(verts: Iterable[BMEdge]) -> List[BMVert]:
    unique_edges = set()
    for vert in verts:
        unique_edges = unique_edges.union(vert.link_edges)
    return list(unique_edges)


def unique_face_edges(faces: Iterable[BMEdge]) -> List[BMVert]:
    unique_edges = set()
    for face in faces:
        if not isinstance(face, BMFace):
            continue
        unique_edges = unique_edges.union(face.edges)
    return list(unique_edges)


def unique_vert_faces(verts: Iterable[BMVert]) -> List[BMFace]:
    vert_set = set(verts)
    faces = set()
    all_faces = chain.from_iterable(vert.link_faces for vert in vert_set)
    for face in all_faces:
        if set(face.verts).issubset(vert_set):
            faces.add(face)
    return list(faces)


def verts_by_layer(
    verts: Iterable[BMVert],
    layers: Union[BMLayerItem, Iterable[BMLayerItem]],
    values: Union[_LayerValueType, Iterable[_LayerValueType]] = 1,
) -> Iterator[BMVert]:
    # Check execution typeJ
    if isinstance(values, BMESH_LAYER_VALUE_TYPES):
        values = (values,)

    if isinstance(layers, BMLayerItem):
        layers = (layers,)

    # Check valid layer value
    def _test_value(vert):
        def _conditions():
            for layer, value in zip(layers, cycle(values)):
                yield vert[layer] == value

        return all(_conditions())

    return filter(_test_value, verts)


def vert_axis_split(
    verts: Iterable[BMVert], split_val: float = 0.5, axis: str = "z"
) -> Tuple[List[BMVert], List[BMVert]]:
    """Return tuples of vert lists split by axis at split val"""
    above, below = [], []
    for vert in verts:
        axis_val = getattr(vert.co, axis)
        if axis_val >= split_val:
            above.append(vert)
        else:
            below.append(vert)
    return above, below


def verts_in_range(
    verts: Iterable[BMVert], val_range: Tuple[float, float], axis: str = "z"
) -> Generator[BMVert, None, None]:
    for vert in verts:
        val = getattr(vert.co, axis)
        if all((val > val_range[0], val < val_range[1])):
            yield vert


def verts_longer_than(
    verts: Iterable[BMVert], length: float, axis: str = "xy"
) -> Generator[BMVert, None, None]:
    for vert in verts:
        if getattr(vert.co, axis).length >= length:
            yield vert
