# -*- coding:utf-8 -*-

# #
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110- 1301, USA.
#
# 
# <pep8 compliant>

# ----------------------------------------------------------
# Author: Stephen Leger (s-leger)
#
# ----------------------------------------------------------
# noinspection PyUnresolvedReferences
import bmesh
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
from mathutils import Matrix, Vector
from math import atan2
from .geom import (
    Geom3d,
    Geom2d,
    Z_AXIS,
    VERY_SMALL
)
from .logger import get_logger
logger = get_logger(__name__, 'ERROR')


class BmeshUtils:

    @classmethod
    def ops_duplicate(cls, source_bm):
        """
        Separate selected items to a new bmesh
        Just because bmesh.ops.duplicate raise a "not implemented error" when "dest" keyword is in use (...)
        :param source_bm:
        :return: bmesh
        """
        bm = bmesh.new(use_operators=True)

        add_vert = bm.verts.new
        add_face = bm.faces.new
        add_edge = bm.edges.new
        bevel_layers = []

        if bpy.app.version[0] < 4:
            bevel = source_bm.verts.layers.bevel_weight.items()
            for name, src in bevel:
                dst = bm.verts.layers.bevel_weight.get(name)
                if dst is None:
                    dst = bm.verts.layers.bevel_weight.new(name)
                bevel_layers.append((src, dst))

        else:
            bevel = source_bm.verts.layers.float.items()
            for name, src in bevel:
                dst = bm.verts.layers.float.get(name)
                if dst is None:
                    dst = bm.verts.layers.float.new(name)
                bevel_layers.append((src, dst))

        index_map = {}
        i = 0
        for vert in source_bm.verts:
            if vert.select:
                index_map[vert.index] = i
                i += 1
                v = add_vert(vert.co)
                v.select = vert.select
                for src, dst in bevel_layers:
                    v[dst] = vert[src]

        bm.verts.index_update()
        bm.verts.ensure_lookup_table()

        if source_bm.faces:

            # vertex colors
            cols = source_bm.loops.layers.color.items()
            cols_layers = []
            for name, src in cols:
                dst = bm.loops.layers.color.get(name)
                if dst is None:
                    dst = bm.loops.layers.color.new(name)
                cols_layers.append((src, dst))

            # uvs
            uvs = source_bm.loops.layers.uv.items()
            uvs_layers = []
            for name, src in uvs:
                dst = bm.loops.layers.uv.get(name)
                if dst is None:
                    dst = bm.loops.layers.uv.new(name)
                uvs_layers.append((src, dst))

            for face in source_bm.faces:
                if face.select:
                    f = add_face(tuple(bm.verts[index_map[i.index]] for i in face.verts))
                    f.select = face.select
                    f.material_index = face.material_index
                    for j, loop in enumerate(face.loops):
                        for src, dst in uvs_layers:
                            f.loops[j][dst].uv = loop[src].uv
                        # vertex colors
                        for src, dst in cols_layers:
                            f.loops[j][dst] = loop[src]

            bm.faces.index_update()
            bm.faces.ensure_lookup_table()

        if source_bm.edges:

            crease_layers = []
            bevel_layers = []

            # bevel
            if bpy.app.version[0] < 4:
                bevel = source_bm.edges.layers.bevel_weight.items()
                for name, src in bevel:
                    dst = bm.edges.layers.bevel_weight.get(name)
                    if dst is None:
                        dst = bm.edges.layers.bevel_weight.new(name)
                    bevel_layers.append((src, dst))

                # crease
                crease = source_bm.edges.layers.crease.items()
                for name, src in crease:
                    dst = bm.edges.layers.crease.get(name)
                    if dst is None:
                        dst = bm.edges.layers.crease.new(name)
                    crease_layers.append((src, dst))

            else:
                # Generic float layers, handle anything
                bevel = source_bm.verts.layers.float.items()
                for name, src in bevel:
                    dst = bm.edges.layers.float.get(name)
                    if dst is None:
                        dst = bm.edges.layers.float.new(name)
                    bevel_layers.append((src, dst))

            for edge in source_bm.edges:
                if edge.select:
                    edge_seq = tuple(bm.verts[index_map[i.index]] for i in edge.verts)
                    try:
                        ed = add_edge(edge_seq)
                        ed.select = edge.select
                        for src, dst in bevel_layers:
                            ed[dst] = edge[src]
                        for src, dst in crease_layers:
                            ed[dst] = edge[src]
                    except ValueError:
                        # edge exists!
                        pass
            bm.edges.index_update()
            bm.edges.ensure_lookup_table()

        return bm

    @classmethod
    def _find_candidate(cls, vert: Vector, verts: list) -> tuple:
        """
        :param vert:
        :param verts:
        :return: First vertex far enough from reference one in list
        NOTE: may use farthest instead to increase precision
        """
        for i, candidate in enumerate(verts):
            if Geom3d.close_enough(candidate, vert, VERY_SMALL):
                continue
            return i, candidate
        return -1, None

    @classmethod
    def _proj_verts_to_2d(cls, face, ref: Vector, normal: Vector) -> list:
        """
        :param face:
        :param ref: vertex coordinate to use as origin
        :param normal: normal of face to eval space
        :return: list of vertex coordinates in face space using  reference vertex as origin
        NOTE: we do not care about z axis values
        """
        space = Geom3d.matrix_inverted(Geom3d.matrix_from_normal(ref, normal))
        return [space @ v.co for v in face.verts]

    @classmethod
    def _uv_matrix(cls, uv0: Vector, uv1: Vector) -> Matrix:
        """
        :param uv0:
        :param uv1:
        :return: A matrix to convert normalized vertex location to uv coord
        """
        duv = uv1 - uv0
        s = duv.length
        return Matrix.Rotation(atan2(duv.y, duv.x), 4, "Z") @ Geom3d.scale_matrix(s, s, s)

    @classmethod
    def _face_normalized_matrix(cls, p0: Vector, p1: Vector) -> Matrix:
        """
        :param p0:
        :param p1:
        :return: matrix at vert0, oriented to vert1 and inverse scale so it does normalize coord
        """
        vx = p1 - p0
        s = 1.0 / vx.length
        return Geom3d.scale_matrix(s, s, s) @ Geom3d.matrix_inverted(
            Geom3d.safe_matrix(p0, vx, Z_AXIS)
        )

    @classmethod
    def _map_uv(cls, face: list, vert: Vector, new_vert: Vector, uv: Vector, uvs: list) -> Vector:
        """
        :param face: list of vertex location of reference face
        :param vert: reference vertex
        :param new_vert: moved vertex
        :param uv: uv coord of reference vertex
        :param uvs: list of uv coord of reference face
        :return: uv coord of new_vert
        """
        # find index of reference vertex
        index, candidate = cls._find_candidate(vert, face)
        if candidate is None:
            return 0, 0
        co_matrix = cls._face_normalized_matrix(candidate, vert)
        # normalized new co in local system
        dst = co_matrix @ new_vert
        uv0 = uvs[index]
        return uv0 + (cls._uv_matrix(uv0, uv) @ dst).xy

    @classmethod
    def correct_face_attributes(cls, bm_src, bm_dst):
        """ Correct uv of transformed faces
        :param bm_src: source bmesh
        :param bm_dst: dest bmesh
        :return:
        """
        uvs = bm_src.loops.layers.uv
        for sface, dface in zip(bm_src.faces, bm_dst.faces):
            # find a reference vertex not moving if any
            # fallback to face center
            ref = sface.calc_center_bounds()
            for i, v in enumerate(sface.verts):
                if not v.select:
                    ref = v.co
                    break

            sverts = cls._proj_verts_to_2d(sface, ref, sface.normal)
            dverts = cls._proj_verts_to_2d(dface, ref, sface.normal)
            min_area = 0.5 * sface.calc_area()

            # Compute surface of destination face projection over source face
            if Geom2d.area(dverts) < min_area:
                # when surface is < 0.5 * source, rely on destination face normal
                # prevent degeneration as line or huge deformation in uv space
                # (eg: when destination is rotated about 90° over source)
                dverts = cls._proj_verts_to_2d(dface, ref, dface.normal)

            for name in uvs.keys():
                src_uv = bm_src.loops.layers.uv.get(name)
                dst_uv = bm_dst.loops.layers.uv.get(name)
                uvs_co = [loop[src_uv].uv for loop in sface.loops]
                for i, dv in enumerate(dverts):
                    if Geom3d.close_enough(sverts[i].xy, dv.xy, VERY_SMALL):
                        # skip unchanged vertex
                        continue
                    dface.loops[i][dst_uv].uv = cls._map_uv(sverts, sverts[i], dv, uvs_co[i], uvs_co)
