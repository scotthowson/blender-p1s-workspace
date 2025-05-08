# context.area: VIEW_3D
import bpy
import bmesh
from bmesh.types import BMEdge, BMVert
from mathutils import Vector
from itertools import chain


def cutter_test():
    mesh = bpy.data.meshes.new(name='blah')
    bm = bmesh.new()
    bmesh.ops.create_monkey(bm)
    bm.faces.ensure_lookup_table()

    co = Vector((0, 0, 0))
    no = Vector((1, 0, 0))
    geom = bm.faces[:] + bm.edges[:] + bm.verts[:]
    cut = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)

    # Get cut edges
    cut_geom = cut["geom_cut"]
    is_edge = lambda g: isinstance(g, BMEdge)
    is_vert = lambda g: isinstance(g, BMVert)
    cut_edges = set(filter(is_edge, cut_geom))
    cut_verts = list(filter(is_vert, cut_geom))

    # unsorted_verts = cut_verts.copy()
    ordered_verts = []
    first_vert = cut_verts[0]
    ordered_verts.append(first_vert)

    last_vert = first_vert

    is_valid_edge = lambda e: e in cut_edges

    sanity_limit = 1000000
    iteration = 0

    cap_faces = bmesh.ops.edgeloop_fill(bm, edges=list(cut_edges))["faces"]
    bmesh.ops.triangulate(bm, faces=cap_faces, quad_method="BEAUTY", ngon_method="BEAUTY")

    # while True:
    #     valid_edges = filter(is_valid_edge, last_vert.link_edges)
    #     connected_verts = chain.from_iterable((edge.verts for edge in valid_edges))
    #     valid_verts = (vert for vert in connected_verts if vert not in ordered_verts)
    #     try:
    #         next_vert = next(valid_verts)
    #         ordered_verts.append(next_vert)
    #         last_vert = next_vert
    #     except Exception as e:
    #         print(e)
    #         break

    #     iteration += 1
    #     if iteration > sanity_limit:
    #         print("WARNING: Infinite loop encountered sorting cut edge:")
    #         break
    # fill_face = bm.faces.new(ordered_verts)
    

    bm.to_mesh(mesh)
    return bpy.data.objects.new('blah', object_data=mesh)


def main():
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj)

    new_object = cutter_test()
    bpy.context.collection.objects.link(new_object)

main()
