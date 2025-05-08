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
from .. import bl_info
from .logger import get_logger
from math import atan2
# noinspection PyUnresolvedReferences
import bmesh
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
from mathutils import Matrix, Vector
from .types import (
    SnapItemType,
    BatchType
)
from .geom import (
    View,
    Geom3d,
    MATRIX_WORLD,
    X_AXIS,
    Y_AXIS,
    Z_AXIS,
    VERY_SMALL
)
from .selection import Selection
from .widgets import SnapHelpers
logger = get_logger(__name__, 'ERROR')


class SnapItem:

    __slots__ = ('coord', 'coords', 'dist', 'type', 'fac', 'normal', 'z', 'ray_depth', 'target_type', 'target')

    def __init__(self, coord: Vector, coords: list,
                 dist: float = 0,
                 typ: int = SnapItemType.NONE,
                 fac: float = 0,
                 normal=None,
                 z: float = 0,
                 ray_depth: int = 1,
                 target_type: int = 0,
                 target=None
                 ):
        """
        :param coord: Vector location in world coord system
        :param coords: list of Vectors in world coord system
        :param dist: pixel distance
        :param typ: SnapItemType
        :param fac: t param of pt from co
        :param normal: Vector normal of hit face
        :param z: depth from view origin
        :param ray_depth: hit depth
        :param target_type: SnapTargetType [LINE | POINT | POLY | CIRCLE]
        """
        self.coord = coord
        self.coords = coords
        self.dist = dist
        self.type = typ
        self.fac = fac
        self.normal = normal
        self.z = z
        self.ray_depth = ray_depth
        self.target_type = target_type
        self.target = target
        logger.debug("SnapItem %s %.4f pos: %s coords: %s" % (typ, dist, coord, self.coords))

    def __eq__(self, other) -> bool:
        return \
            other is not None and \
            self.coord == other.coord and self.type == other.type and self.normal == other.normal

    def __str__(self) -> str:
        return "SnapItem pos: %s dist: %.4f z: %.4f fac: %.4f type: %s\ncoords: %s" % (
            self.coord, self.dist, self.z, self.fac, SnapItemType(self.type), self.coords
        )


class SnapItems:
    """
        Contains detected objects
        for further processing
    """
    _snapitems = []
    found = False
    active = None

    @classmethod
    def add(
            cls,
            pos: Vector,
            co: list,
            dist: float = 0,
            typ: int = SnapItemType.NONE,
            fac: float = 0,
            normal: Vector = None,
            z: float = 0,
            ray_depth: int = 1,
            target_type: int = 0,
            target=None
            ) -> bool:
        cls.found = True
        cls._snapitems.append(
            SnapItem(pos, co, dist, typ, fac, normal, z, ray_depth, target_type, target)
        )
        return True

    @classmethod
    def count(cls):
        return len(cls._snapitems)

    @classmethod
    def exit(cls) -> None:
        cls.found = False
        cls._snapitems.clear()

    @classmethod
    def find(cls, key) -> SnapItem:
        cls._snapitems.sort(key=key)
        logger.debug("find() : snapitems: \n\n" + "\n\n".join([
            "%s: %s" % (i, item) for i, item in enumerate(cls._snapitems)
        ]))
        closest = cls._snapitems[0]
        cls.active = closest
        cls.exit()
        return closest


class ContextResult:
    """
    Store a context evaluation result
    """
    __slots__ = ('name', 'coord', 'type', 'space')

    def __init__(self, name, coord: list, typ: int = BatchType.NONE, space: Matrix = MATRIX_WORLD):
        self.name = name
        # coord in world space
        self.coord = coord
        self.type = typ
        self.space = space


class SnapContext:
    """
    Store / evaluate a selection of snap items as context
    """

    # Eval types
    NONE = 0
    POINT = 1
    LINE = 2
    SPACE = 4
    INTERSECTION = 8
    CLOSEST = 16
    # PROJECTION = 32
    AVERAGE = 64
    LINE_INTERSECT = 128

    # Name for objects and collection
    _name = bl_info['name']

    _items = []

    @classmethod
    def add(cls, snapitem: SnapItem):
        """
        Add a snap item to the context, will also select it
        :param snapitem:
        :return:
        """
        cls._items.append(snapitem)
        Selection.add(snapitem)

    @classmethod
    def is_empty(cls):
        return len(cls._items) == 0

    @classmethod
    def remove_last(cls):
        if len(cls._items) > 0:
            snapitem = cls._items.pop(-1)
            del snapitem
            Selection.remove_last()

    @classmethod
    def remove(cls, snapitem: SnapItem):
        to_remove = -1
        for i, item in enumerate(cls._items):
            if item == snapitem:
                to_remove = i
                break
        if to_remove > -1:
            cls._items.pop(to_remove)

    @classmethod
    def remove_by_index(cls, index: list):
        index.sort()
        for i in reversed(index):
            cls._items.pop(i)

    @classmethod
    def index(cls, snapitem: SnapItem) -> int:
        """
        Return index of snapitem
        :param snapitem:
        :return:
        """
        for i, item in enumerate(cls._items):
            if item == snapitem:
                return i
        return -1

    @classmethod
    def exit(cls):
        """
        Clear context and cleanup selection
        :return:
        """
        cls._items.clear()
        Selection.exit()

    @classmethod
    def has(cls, snapitem: SnapItem) -> bool:
        """
        :param snapitem:
        :return: True is snapitem is found
        """
        for item in cls._items:
            if item == snapitem:
                return True
        return False

    @classmethod
    def has_not(cls, snapitem: SnapItem) -> bool:
        """
        :param snapitem:
        :return: True is SnapItem is not found
        """
        return not cls.has(snapitem)

    @classmethod
    def find_by_type(cls, typ: int):
        """
        :param typ:
        :return: first SnapItem found by type
        NOTE: snapitem.type may be LINE|CENTER
        """
        for snapitem in cls._items:
            if snapitem.type == typ:
                return snapitem
        return None

    @classmethod
    def find_all_by_type(cls, typ: int, exclude: int = 0) -> list:
        """
        :param typ:
        :param exclude:
        :return: Available SnapItems by type
        NOTE: snapitem.type may be LINE|CENTER
        """
        return [snapitem for snapitem in cls._items if (snapitem.type & typ) > 0 and not (snapitem.type & exclude)]

    @classmethod
    def _context_id(cls, name: str, obj1, obj2) -> str:
        return name + '-' + str(id(obj1)) + str(id(obj2))

    @classmethod
    def _by_type(cls) -> tuple:
        """
        Return SnapItem by types
        :return:
        NOTE: points include center of lines and tris
        """
        pts = cls.find_all_by_type(SnapItemType.POINT | SnapItemType.CENTER)
        lines = cls.find_all_by_type(SnapItemType.LINE, SnapItemType.CENTER)
        tris = cls.find_all_by_type(SnapItemType.TRI, SnapItemType.CENTER)
        logger.debug("SnapContext._by_type() pts: %s lines: %s tris: %s" % (len(pts), len(lines), len(tris)))
        return pts, lines, tris

    @classmethod
    def _create_helper(cls, result: ContextResult):
        """
        Create snap helper from result
        :param result:
        :return:
        """
        # obj, co, mat: Matrix = MATRIX_WORLD, type: int = Detect.NONE
        # NOTE copy() is required as matrix update occurs in place
        SnapHelpers.create(
            ("helper:%s" % result.name), result.coord, result.space.copy(), result.type
        )

    @classmethod
    def _as_intersection(cls):
        """
        Find intersection
        :return: ContextResult or None
        """
        pts, lines, tris = cls._by_type()
        # Line + Line -> Perpendicular line between closest points on both lines
        if len(lines) == 2:
            if View.is_ortho:
                # Evaluate in 2d
                ispace = Geom3d.matrix_inverted(View.view_matrix)
                line0 = [(ispace @ co).to_2d().to_3d() for co in lines[0].coords]
                line1 = [(ispace @ co).to_2d().to_3d() for co in lines[1].coords]

            else:
                line0 = lines[0].coords
                line1 = lines[1].coords

            t0 = Geom3d.neareast_point_line_line_t(*line0, *line1)

            if t0 is not None:
                t1 = Geom3d.neareast_point_line_line_t(*line1, *line0)
                p0 = Geom3d.lerp(*lines[0].coords, t0)
                p1 = Geom3d.lerp(*lines[1].coords, t1)
                res = [p0, p1]

                if Geom3d.close_enough(p0, p1, VERY_SMALL):
                    typ = BatchType.POINTS
                    res.pop()
                else:
                    typ = BatchType.LINES
                return ContextResult(
                    cls._context_id('intersection', *lines), res, typ
                )

        # Tri + Line -> Intersection point
        if len(tris) == 1 and len(lines) == 1:
            o, x, y = tris[0].coords[0:3]
            p0, p1 = lines[0].coords[0:2]
            plane = Geom3d.matrix_from_3_points(o, x, y)
            co = Geom3d.intersect_ray_plane(p0, p1 - p0, plane)
            if co is not None:
                return ContextResult(
                    cls._context_id('intersection', tris[0], lines[0]), [co], BatchType.POINTS
                )

        return None

    @classmethod
    def _as_closest(cls):
        """
        Find closest points
        :return:
        """
        pts, lines, tris = cls._by_type()

        # Line + Point -> Perpendicular line from closest point on line to point
        if len(lines) == 1 and len(pts) == 1:
            p0 = pts[0].coord
            if View.is_ortho:
                ispace = Geom3d.matrix_inverted(View.view_matrix)
                line0 = [(ispace @ co).to_2d().to_3d() for co in lines[0].coords]
                _p0 = ispace @ pts[0].coord
                _p0.z = 0
            else:
                _p0 = p0
                line0 = lines[0].coords
            t1 = Geom3d.neareast_point_on_line_t(_p0, *line0)
            if t1 is not None:
                p1 = Geom3d.lerp(*line0, t1)
                return ContextResult(cls._context_id('closest', pts[0], lines[0]), [p0, p1], BatchType.LINES)

        # Line + Line -> Perpendicular line between closest points on both lines
        if len(lines) == 2:
            if View.is_ortho:
                # Evaluate in 2d
                ispace = Geom3d.matrix_inverted(View.view_matrix)
                line0 = [(ispace @ co).to_2d().to_3d() for co in lines[0].coords]
                line1 = [(ispace @ co).to_2d().to_3d() for co in lines[1].coords]

            else:
                line0 = lines[0].coords
                line1 = lines[1].coords

            t0 = Geom3d.neareast_point_line_line_t(*line0, *line1)

            if t0 is not None:

                t1 = Geom3d.neareast_point_line_line_t(*line1, *line0)
                p0 = Geom3d.lerp(*lines[0].coords, t0)
                p1 = Geom3d.lerp(*lines[1].coords, t1)
                res = [p0, p1]

                if Geom3d.close_enough(p0, p1, VERY_SMALL):
                    typ = BatchType.POINTS
                    res.pop()
                else:
                    typ = BatchType.LINES
                return ContextResult(
                    cls._context_id('closest', *lines), res, typ
                )

        # Tri + point -> Perpendicular line from closest point on tri to point
        if len(tris) == 1 and len(pts) == 1:
            p1 = pts[0].coord
            no = Geom3d.triangle_normal(*tris[0].coords)
            co = Geom3d.triangle_center(*tris[0].coords)
            p0 = Geom3d.neareast_point_plane(p1, co, no)
            if p0 is not None:
                return ContextResult(cls._context_id('closest', tris[0], pts[0]), [p0, p1], BatchType.POINTS)

        return None

    @classmethod
    def _as_average(cls):
        """
        Find projection along vector
        :return:
        """
        co = Vector()
        i = 0
        for items in cls._by_type():
            for item in items:
                if (item.type & SnapItemType.CENTER) > 0:
                    co += item.coord
                    i += 1
                else:
                    for pt in item.coords:
                        co += pt
                        i += 1
        if i > 0:
            co = (1.0 / i) * co
            return ContextResult('average', [co], BatchType.POINTS)

        return None

    @classmethod
    def _normal_from_matrix(cls, matrix_world):
        """
        Return a line matching with matrix_world normal
        :param matrix_world:
        :return:
        """
        origin = matrix_world.translation
        direction = matrix_world.col[2].xyz
        return [
            origin, origin + direction
        ]

    @classmethod
    def _as_space(cls):
        """
        Custom transform space
        :return: ContextResult as normal line on success or None
        """
        pts, lines, tris = cls._by_type()
        context_id = None

        if len(pts) == 1 and len(lines) == 1:
            # Use line as z axis
            o = pts[0].coord
            x, y = lines[0].coords
            matrix_world = Geom3d.matrix_from_normal(o, y - x)
            context_id = cls._context_id('plane', pts[0], lines[0])

        elif len(pts) == 1 and len(tris) == 1:
            # evaluate origin from tri closest point, use face normal
            matrix_world = Geom3d.matrix_from_normal(pts[0].coord, tris[0].normal)
            # o = Geom3d.neareast_point_plane(pts[0].coord, matrix_world)
            # matrix_world.translation = o
            context_id = cls._context_id('plane', pts[0], tris[0])

        elif len(pts) == 1:
            # Matrix world with origin at point
            o = pts[0].coord
            matrix_world = Matrix.Translation(o)
            context_id = cls._context_id('plane', pts[0], pts[0])

        elif len(pts) == 2:
            # Use points as direction for z axis
            o, x = [p.coord for p in pts]
            matrix_world = Geom3d.matrix_from_normal(o, x - o)
            context_id = cls._context_id('plane', *pts[0:2])

        elif len(pts) == 3:
            # plane by 3 points
            o, x, y = [p.coord for p in pts]
            matrix_world = Geom3d.matrix_from_3_points(o, x, y)
            context_id = cls._context_id('plane', *pts[0:2])

        elif len(lines) == 1:
            o, x = lines[0].coords
            matrix_world = Geom3d.matrix_from_normal(o, x - o)
            context_id = cls._context_id('plane', o, x)

        elif len(lines) == 2:
            # use lines as guides for x y axis
            o, x = lines[0].coords
            # vx = (x - o).normalized()
            y0, y1 = lines[1].coords
            y = o + y1 - y0
            matrix_world = Geom3d.matrix_from_3_points(o, x, y)
            context_id = cls._context_id('plane', *lines)

        elif len(tris) == 1:
            # Use tri normal and closest point as origin
            o = tris[0].coord
            normal = tris[0].normal

            if Geom3d.close_enough(normal, Z_AXIS, VERY_SMALL):
                guide = normal.cross(Y_AXIS)
            else:
                guide = normal.cross(Z_AXIS)

            matrix_world = Geom3d.safe_matrix(o, normal, guide, "Z", "X")
            # matrix_world = Geom3d.matrix_from_normal(o, tris[0].normal)
            context_id = cls._context_id('plane', tris[0], tris[0])

        else:
            matrix_world = Matrix()

        if context_id is not None:
            # return ContextResult(context_id, cls._normal_from_matrix(matrix_world), BatchType.LINES, matrix_world)
            return ContextResult(context_id, cls._normal_from_matrix(matrix_world), BatchType.TRIS, matrix_world)

        return None

    @classmethod
    def _as_point(cls):
        """
        Intersections / closest - perpendicular
        :return: ContextResult or None
        """
        pts, lines, tris = cls._by_type()
        # Line + Point -> perpendicular intersection point
        if len(lines) == 1 and len(pts) == 1:

            p0 = pts[0].coord
            if View.is_ortho:
                ispace = Geom3d.matrix_inverted(View.view_matrix)
                line0 = [(ispace @ co).to_2d().to_3d() for co in lines[0].coords]
                _p0 = ispace @ pts[0].coord
                _p0.z = 0
            else:
                _p0 = p0
                line0 = lines[0].coords
            t1 = Geom3d.neareast_point_on_line_t(_p0, *line0)
            if t1 is not None:
                p1 = Geom3d.lerp(*line0, t1)
                return ContextResult(cls._context_id('perpendicular', pts[0], lines[0]), [p0, p1], BatchType.LINES)

        # Line + Line / mouse -> intersection point / closest points using a line
        if len(lines) == 2:
            if View.is_ortho:
                # Evaluate in 2d
                ispace = Geom3d.matrix_inverted(View.view_matrix)
                line0 = [(ispace @ co).to_2d().to_3d() for co in lines[0].coords]
                line1 = [(ispace @ co).to_2d().to_3d() for co in lines[1].coords]

            else:
                line0 = lines[0].coords
                line1 = lines[1].coords

            t0 = Geom3d.neareast_point_line_line_t(*line0, *line1)

            if t0 is not None:

                t1 = Geom3d.neareast_point_line_line_t(*line1, *line0)
                p0 = Geom3d.lerp(*lines[0].coords, t0)
                p1 = Geom3d.lerp(*lines[1].coords, t1)
                res = [p0, p1]

                if Geom3d.close_enough(p0, p1, VERY_SMALL):
                    typ = BatchType.POINTS
                    res.pop()
                else:
                    typ = BatchType.LINES

                return ContextResult(
                    cls._context_id('intersection', *lines[0:2]), res, typ
                )
        # Tri + Line  -> intersection point
        if len(tris) == 1 and len(lines) == 1:
            o, x, y = tris[0].coords[0:3]
            p0, p1 = lines[0].coords[0:2]
            plane = Geom3d.matrix_from_3_points(o, x, y)
            co = Geom3d.intersect_ray_plane(p0, p1 - p0, plane)
            if co is not None:
                return ContextResult(
                    cls._context_id('intersection', tris[0], lines[0]), [co], BatchType.POINTS
                )

        return None

    @classmethod
    def _as_line_intersection(cls):
        pts, lines, tris = cls._by_type()
        n_lines = len(lines)
        res = []
        if n_lines > 1:

            if View.is_ortho:
                ispace = Geom3d.matrix_inverted(View.view_matrix)
                lines_co = [[(ispace @ co).to_2d().to_3d() for co in line.coords] for line in lines]
            else:
                lines_co = [line.coords for line in lines]

            for i in range(n_lines - 1):
                for j in range(i + 1, n_lines):

                    t0 = Geom3d.neareast_point_line_line_t(*lines_co[i], *lines_co[j])

                    if t0 is not None:
                        t1 = Geom3d.neareast_point_line_line_t(*lines_co[j], *lines_co[i])
                        p0 = Geom3d.lerp(*lines[i].coords, t0)
                        p1 = Geom3d.lerp(*lines[j].coords, t1)
                        co = [p0, p1]
                        if Geom3d.close_enough(p0, p1, VERY_SMALL):
                            typ = BatchType.POINTS
                            co.pop()
                        else:
                            typ = BatchType.LINES

                        res.append(
                            ContextResult(
                                cls._context_id('intersection', lines[i], lines[j]), co, typ
                            )
                        )
        return res

    @classmethod
    def as_mesh(cls, context):
        """
        Create a mesh from selected snap items in context
        :param context:
        :return: blender object of MESH type of None when context is empty
        """
        pts, lines, tris = cls._by_type()

        if not (tris or lines or pts):
            return None

        bm = bmesh.new()
        add_vert = bm.verts.new
        add_face = bm.faces.new
        add_edge = bm.edges.new

        for pt in pts:
            add_vert(pt.coord)

        # bm.verts.index_updaate()
        # bm.verts.ensure_lookup_table()

        for line in lines:
            p0, p1 = line.coords[0:2]
            v0 = add_vert(p0)
            v1 = add_vert(p1)
            add_edge((v0, v1))

        # bm.verts.index_updaate()
        # bm.edges.index_update()
        # bm.verts.ensure_lookup_table()
        # bm.edges.ensure_lookup_table()

        for tri in tris:
            pts = tri.coords
            v = [add_vert(p) for p in pts]
            add_face(v)

        bm.verts.index_update()
        bm.edges.index_update()
        bm.faces.index_update()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        me = bpy.data.meshes.new(cls._name)

        bm.to_mesh(me)
        bm.free()

        o = bpy.data.objects.new(cls._name, me)

        main = context.scene.collection
        coll = None
        for sub in main.children:
            if sub.name == cls._name:
                coll = sub
                break

        if coll is None:
            coll = bpy.data.collections.new(name=cls._name)
            main.children.link(coll)

        coll.objects.link(o)

        o.display_type = "WIRE"
        o.show_wire = True
        return o

    @classmethod
    def _as_line(cls):
        """
        Line between 2 points / parallel to / face normal
        :return: ContextResult or None
        """
        pts, lines, tris = cls._by_type()
        # Point + Point -> rely
        if len(pts) == 2:
            # rely on mouse point instead
            p0, p1 = [p.coord for p in pts]
            return ContextResult(
                cls._context_id('rely', *pts), [p0, p1], BatchType.LINES
            )

        # Line parallel to line crossing pt
        if len(lines) == 1 and len(pts) == 1:
            p0, p1 = lines[0].coords[0:2]
            return ContextResult(
                cls._context_id('parallel', pts[0], lines[0]), [p0, p1], BatchType.LINES
            )

        if len(lines) == 1 and len(pts) == 0 and len(tris) == 0:
            # rely on mouse point instead
            p0, p1 = lines[0].coords[0:2]
            return ContextResult(
                cls._context_id('line', lines[0], lines[0]), [p0, p1], BatchType.LINES
            )

        return None

    @classmethod
    def eval(cls, typ: int = NONE):
        """
        Eval selected snap items to create snap helpers
        :param typ: SnapContext.type
        :return:
        """
        if typ == cls.POINT:
            return cls._as_point()

        elif typ == cls.LINE:
            return cls._as_line()

        elif typ == cls.SPACE:
            return cls._as_space()

        elif typ == cls.INTERSECTION:
            return cls._as_intersection()

        elif typ == cls.CLOSEST:
            return cls._as_closest()

        elif typ == cls.AVERAGE:
            return cls._as_average()

        elif typ == cls.LINE_INTERSECT:
            return cls._as_line_intersection()

        return None

    @classmethod
    def eval_as_helper(cls, typ: int = NONE) -> bool:
        """
        Eval context and create a SnapHelper
        :param typ: Eval type  SnapContext.XXX
        :return: True on success
        """
        result = cls.eval(typ)
        if result is not None:
            if isinstance(result, list):
                if result:
                    for res in result:
                        cls._create_helper(res)
                    return True
            else:
                cls._create_helper(result)
            return True
        return False
