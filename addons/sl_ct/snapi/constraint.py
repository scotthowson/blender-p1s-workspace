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
from mathutils import Vector, Matrix
from math import pi, sqrt
from .geom import (
    Geom3d,
    Z_AXIS
)
from .types import (
    TransformType,
    ConstraintType,
    SnapItemType
)
from .logger import get_logger
logger = get_logger(__name__, 'ERROR')


class Constraint:

    @classmethod
    def _planes_intersection_as_line(cls, trs, about: Matrix):
        """
        :param trs: Transform operation with a valid Snapitem
        :param about: Matrix: space
        :return: pc, vi a line of intersection of both planes, and pa nearest point over axis pa
            pa: Vector nearest point of snap_from on transform axis
            pc: Vector closest intersection point on face perpendicular to the axis
            vi: Vector direction of line on face intersecting the plane
        """
        pa, pc, vi = None, None, None
        c = about.translation
        z = about.to_3x3() @ Z_AXIS
        # nearest point on axis
        pa = Geom3d.neareast_point_on_line(trs.snap_from, c, c + z)
        if -1.0 < z.dot(trs.snapitem.normal) < 1.0:
            # direction of line on face intersecting the arc plane
            vi = z.cross(trs.snapitem.normal)
            # direction of perpendicular between axis and intersection line
            vn = vi.cross(z)
            # intersection point perpendicular to the axis
            pc = Geom3d.intersect_line_plane(pa, pa + vn, trs.snapitem.coord, trs.snapitem.normal)

        return pa, pc, vi

    @classmethod
    def to_plane(cls, trs,  pos: Vector, about: Matrix) -> Vector:
        """
        Project a point on nearest plane location,
        with a snap segment, compute intersection plane / segment
        with a snap face, compute intersection arc / face
        :param trs: TransformAction
        :param pos: Vector
        :param about: Matrix of plane
        :return:
        """
        it = None
        if trs.has(TransformType.MOVE | TransformType.ROTATE | TransformType.SCALE):
            if trs.snapitem is not None:
                if trs.snapitem.type == SnapItemType.LINE and trs.has_not(TransformType.ALONG_SEGMENT):
                    if trs.has(TransformType.ROTATE) and trs.has_constraint(ConstraintType.PERPENDICULAR):
                        it = cls.to_perpendicular(trs, pos, about)
                    elif trs.has(TransformType.ROTATE) and trs.has_constraint(ConstraintType.PARALLEL):
                        it = cls.to_parallel(trs, pos, about)
                    else:
                        _about = about.copy()
                        _about.translation = trs.snap_from
                        # project line to the plane
                        p0, p1 = trs.snapitem.coords[0:2]
                        it = Geom3d.intersect_line_plane(p0, p1, about)

                elif trs.snapitem.type == SnapItemType.TRI:
                    pa, pc, vi = cls._planes_intersection_as_line(trs, about)
                    if pc is not None:

                        if trs.has(TransformType.ROTATE):

                            # minimal distance axis / intersection line
                            adj2 = (pc - pa).length_squared
                            # radius
                            hyp2 = (trs.snap_from - pa).length_squared
                            if 0 < adj2 < hyp2:
                                # nearest point on intersection line
                                p = Geom3d.neareast_point_on_line(pos, pc, pc + vi)
                                # direction of intersection along line
                                opp = p - pc
                                if opp.length_squared > 0:
                                    opp.length = sqrt(hyp2 - adj2)
                                    it = pc + opp
                        else:
                            it = Geom3d.neareast_point_on_line(pos, pc, pc + vi)

        if it is not None:
            return it

        # fallback to closest point
        return Geom3d.neareast_point_plane(pos, about)

    @classmethod
    def to_perpendicular(cls, trs, pos: Vector, about: Matrix) -> Vector:
        """
        Perpendicular to target segment about transform axis
        :param pos:
        :param about: Matrix transform space
        :return: Vector perpendicular point projected over rotation plane
        """
        if trs.snapitem and trs.snapitem.type == SnapItemType.LINE:
            z = about.to_3x3() @ Z_AXIS
            p0, p1 = trs.snapitem.coords[0:2]
            return about.translation + z.cross(p1 - p0)

        return pos

    @classmethod
    def to_parallel(cls, trs, pos: Vector, about: Matrix) -> Vector:
        """
        Parallel to target segment about transform axis
        :param pos:
        :param about: Matrix transform space
        :return: Vector parallel point
        """
        if trs.snapitem and trs.snapitem.type == SnapItemType.LINE:
            p0, p1 = [Geom3d.neareast_point_plane(p, about) for p in trs.snapitem.coords[0:2]]
            return about.translation + p1 - p0

        return pos

    @classmethod
    def to_normal(cls, pos: Vector, about: Matrix) -> Vector:
        """
        Project a point on nearest face normal location - perpendicular
        :param pos:
        :param about: Matrix of face at center with z axis aligned to normal
        :return: intersection
        """
        p0 = about.translation
        p1 = about @ Z_AXIS
        return Geom3d.neareast_point_on_line(pos, p0, p1)

    @classmethod
    def to_axis(cls, trs, pos: Vector, about: Matrix) -> Vector:
        """
        Project a point on nearest axis location
        :param trs: TransformAction
        :param pos:
        :param about:
        :return:
        """
        c = about.translation
        axis = about.to_3x3() @ Z_AXIS
        it = None
        if trs.snapitem is not None:
            if trs.has(TransformType.MOVE | TransformType.SCALE):

                # intersection of axis and line on axis
                # quite not certain about the meaning of this intersection
                # as intersection is in 3d (closest point) but may be projected - what is the relevant plane ?
                if trs.snapitem.type == SnapItemType.LINE:
                    # p0, p1 = [Geom3d.neareast_point_plane(p, about) for p in trs.snapitem.coords[0:2]]
                    # it = Geom3d.intersect_line_line(c, c + axis, p0, p1)
                    it = Geom3d.intersect_line_line(c, c + axis, *trs.snapitem.coords[0:2])

                elif trs.snapitem.type == SnapItemType.TRI:
                    it = Geom3d.intersect_ray_plane(c, axis, trs.snapitem.coord, trs.snapitem.normal)

        if it is not None:
            return it
        # fallback to closest point (perpendicular)
        return Geom3d.neareast_point_on_line(pos, c, c + axis)

    @staticmethod
    def rotation_plane(trs, about: Matrix) -> Matrix:
        """ Rotate about so z axis fit with a rotation axis
        :param trs:
        :param about:
        :return:
        """
        res = about

        if trs.has_constraint(ConstraintType.X):
            res = about @ Matrix.Rotation(pi / 2, 4, 'Y')
        elif trs.has_constraint(ConstraintType.Y):
            res = about @ Matrix.Rotation(pi / 2, 4, 'X')

        return res

    @classmethod
    def apply(cls, trs, pos: Vector, about: Matrix) -> Vector:
        """
        Apply a constraint to a pos
        :param trs: TransformAction
        :param pos:
        :param about: a snap target
        :return:
        """
        co = pos
        if trs.has_constraint(ConstraintType.PLANE):
            # Constraint to plane (this apply to rotation)
            co = cls.to_plane(trs, pos, cls.rotation_plane(trs, about))

        elif trs.has_constraint(ConstraintType.AXIS):
            co = cls.to_axis(trs, pos, cls.rotation_plane(trs, about))

        return co
