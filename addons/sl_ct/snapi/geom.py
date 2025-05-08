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
from .logger import get_logger
from math import sqrt, atan2, radians, degrees
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
from mathutils import Matrix, Vector
from .units import Units
from .event import Events
logger = get_logger(__name__, 'ERROR')

# Constants
EPSILON = 0.00000001
CLOSE_ENOUGH = 0.0000001

# Minimum angle (radians), when out of range, lines are considered parallel
ANGLE_MIN = radians(0.1)
ANGLE_MAX = radians(179.9)
ANGLE_90 = radians(90)

# Prevent non uniform scale factor to grow to infinite when snap are aligned with axis
VERY_SMALL = 0.0001
TOO_FAR = 1000000.0
SQRT_2 = sqrt(2)

# Limit far clip plane distance to avoid precision issues in view origin and direction
ORTHO_CLAMP = 100000

# Matrix
MATRIX_WORLD = Matrix()

# Vectors
ZERO = Vector()
X_AXIS = Vector((1, 0, 0))
Y_AXIS = Vector((0, 1, 0))
Z_AXIS = Vector((0, 0, 1))

# Bounding box related
BBOX_THRESHOLD = 0.1
BBOX_THRESHOLD_VEC = Vector((BBOX_THRESHOLD, BBOX_THRESHOLD, BBOX_THRESHOLD))

# Colors
RED = (1, 0, 0, 1)
GREY = (0.5, 0.5, 0.5, 0.5)

# Grid main steps, still hardcoded, but may rely on pref
GRID_STEPS = 100


class View:
    """
    Store relevant view and mouse event data from context
    """
    # Mouse event location
    pixel = Vector((0, 0))
    # Window size
    window = (0, 0)
    half_window = Vector((0, 0))
    # Mouse event vector
    origin = Vector()
    direction = Vector()
    perspective_matrix = Matrix()
    view_matrix = Matrix()
    is_perspective = False
    is_ortho = False
    region_id = 0
    # Flag, true when perspective change between 2 init calls
    # remains true until reset() call so we may call init() more than once
    dirty = True
    # Flag for grid recompute
    _dirty_grid = True
    # a normalized line starting at origin oriented in direction
    line = (ZERO, ZERO)

    # Cache grid matrix relative to Space.grid
    _grid_matrix = Matrix()
    _grid_sub_alpha = 1.0
    _has_12_subs = False

    @classmethod
    def as_string(cls):
        return "View\n\tmouse: %s\n\twindow: %s\n\torigin: %s\n\tdirection: %s\n\tperspective_matrix: %s" % (
            cls.pixel,
            cls.window,
            cls.origin,
            cls.direction,
            cls.perspective_matrix
        )

    def __str__(cls):
        return cls.as_string()

    @classmethod
    def get_pers_invert(cls, rv3d) -> Matrix:
        return Geom3d.matrix_inverted(rv3d.perspective_matrix, "perpective_matrix")

    @classmethod
    def get_view_invert(cls, rv3d) -> Matrix:
        return Geom3d.matrix_inverted(rv3d.view_matrix, "view_matrix")

    @classmethod
    def init(cls, context, event) -> bool:
        """
        :param context:
        :param event:
        :return: True when event occurs in view3d
        """
        if not cls.in_view3d(context):
            logger.info("View.init() not in 3d view !")
            return False

        region = context.region
        rv3d = context.space_data.region_3d
        cls.region_id = hash(region)
        cls.is_perspective = rv3d.is_perspective
        # TODO: check for camera view (and zoom ..)
        cls.is_ortho = not cls.is_perspective
        # Reset on_change by hand
        cls.dirty = cls.dirty or (cls.perspective_matrix != rv3d.perspective_matrix)
        cls.perspective_matrix[:] = rv3d.perspective_matrix.copy()
        cls.view_matrix[:] = rv3d.view_matrix.copy()
        cls.pixel = Events.mouse_pos(event)
        cls.window = (int(region.width), int(region.height))
        cls.half_window = (0.5 * region.width, 0.5 * region.height)
        cls.origin[:], cls.direction[:] = cls.origin_and_direction(rv3d, cls.pixel)
        cls.line = (cls.origin, cls.origin + cls.direction)
        cls._dirty_grid = cls._dirty_grid or cls.dirty

        logger.debug("View.init() dirty: %s\n%s" % (cls.dirty, cls.as_string()))
        return True

    @classmethod
    def vector(cls) -> Vector:
        """
        Compute view direction
        :return:
        """
        viewinv = Geom3d.matrix_inverted(cls.view_matrix, "view_matrix")
        direction = -viewinv.col[2].xyz
        return direction.normalized()

    @classmethod
    def in_view3d(cls, context):
        """
        Check if mouse event occurs in 3d view
        :return:
        """
        return context.area.type == 'VIEW_3D'

    @classmethod
    def in_region(cls, context):
        return hash(context.region) == cls.region_id

    @classmethod
    def in_window(cls, event) -> bool:
        """
        Check if mouse event occurs in 3d view window
        :param event: modal mouse event
        :return:
        """
        return 0 < event.mouse_region_x < cls.window[0] and 0 < event.mouse_region_y < cls.window[1]

    @classmethod
    def origin_and_direction(cls, rv3d, coord: Vector, clamp=ORTHO_CLAMP):
        """
        :param rv3d:
        :param coord: pixel coord
        :param clamp:
        :return:
        """
        viewinv = cls.get_view_invert(rv3d)
        persinv = cls.get_pers_invert(rv3d)
        dx = (coord[0] / cls.half_window[0]) - 1.0
        dy = (coord[1] / cls.half_window[1]) - 1.0

        if rv3d.is_perspective:
            origin = viewinv.translation.copy()
            out = Vector((dx, dy, -0.5))
            w = out.dot(persinv[3].xyz) + persinv[3][3]
            direction = ((persinv @ out) / w) - origin

        else:
            direction = -viewinv.col[2].xyz

            origin = (
                    (persinv.col[0].xyz * dx) +
                    (persinv.col[1].xyz * dy) +
                    persinv.translation
                )

            if rv3d.view_perspective != 'CAMERA':

                # this value is scaled to the far clip already
                origin_offset = persinv.col[2].xyz
                if clamp is not None:
                    # Since far clip can be a very large value,
                    # the result may give with numeric precision issues.
                    # To avoid this problem, you can optionally clamp the far clip to a
                    # smaller value based on the data you're operating on.
                    if clamp < 0.0:
                        origin_offset.negate()
                        clamp = -clamp

                    if origin_offset.length > clamp:
                        # Hey, length is settable (!!!!)
                        origin_offset.length = clamp

                origin -= origin_offset

        direction.normalize()
        return origin, direction

    @classmethod
    def width_at_dist(cls, context, pt: Vector) -> float:
        """
        :param context:
        :param pt:
        :return: Visible area width at point distance in blender units
        """
        v3d = context.space_data
        rv3d = v3d.region_3d

        if rv3d.is_perspective:
            d = -(rv3d.view_matrix @ pt).z
        else:
            # in orthographic mode, distance doesnt matter
            d = rv3d.view_distance

        # NOTE: this Assume a sensor size of 72mm to eval view lens
        # TODO: handle camera lens size when relevant
        width = max(0.0001, abs(d) / v3d.lens * 72.0)
        return width

    @classmethod
    def grid_scale(cls, context, plane: Matrix, grid_steps: float = 20):
        """
        Compute grid scale from visible area
        :param context:
        :param plane: Grid plane matrix_world
        :param grid_steps: Number of divisions
        :return: Main unit size and has_12_subs bool
        """
        if cls._dirty_grid:

            cls._dirty_grid = False
            us = context.scene.unit_settings

            # intersection of center of view with grid plane
            v3d = context.space_data
            rv3d = v3d.region_3d
            viewinv = cls.get_view_invert(rv3d)

            direction = viewinv.col[2].xyz

            if rv3d.is_perspective:
                origin = viewinv.translation
            else:
                persinv = cls.get_pers_invert(rv3d)
                origin = persinv.translation

            pt = Geom3d.intersect_ray_plane(origin, direction, plane)

            if pt is None:
                logger.error("ray does not intersect grid !")
                pt = plane.translation

            # View width
            width = cls.width_at_dist(context, pt)

            # TODO (?) rely on preferences
            main_units_visible = 4

            # user unit size
            unit_size = Units.user_unit_size(context)

            # available width for one unit
            max_width = width / main_units_visible          # 1: 25  -> 4
            min_width = width / (10 * main_units_visible)   # 1: 2.5 -> 40

            fac = 10

            # resize unit so it fit with max_units_visible
            if unit_size > min_width:
                # when scaling down if base unit are feet we do have 12 inches on first step
                if us.length_unit == "FEET":
                    fac = 12
                while unit_size > max_width:
                    unit_size /= fac
                    fac = 10
            else:
                # Zoom out
                # when grid is smaller than view, grow until it fit
                # result between width and max width
                if us.length_unit == "INCHES":
                    fac = 12
                while unit_size < min_width:
                    unit_size *= fac
                    fac = 10

            cls._has_12_subs = fac == 12

            # snap depends on precise grid size, remove rounding error
            # scale is main steps unit size
            scale = round(unit_size, 5)

            # Grid widget may not be at screen location and
            # grid gl is limited to GRID_STEPS units so center the grid gl
            # according view center (intersection between plane and view vector)

            x, y, _z = Geom3d.matrix_inverted(plane) @ pt

            half_grid = 0.5 * unit_size * grid_steps
            if x < 0:
                x += (-x % half_grid)
            else:
                x -= (x % half_grid)
            if y < 0:
                y += (-y % half_grid)
            else:
                y -= (y % half_grid)

            cls._grid_matrix[:] = Matrix.Translation(Vector((x, y, 0))) @ Matrix.Scale(scale, 4)
            # compute grid alpha so it is between 0.2 and 1.0
            cls._grid_sub_alpha = 1.0 - max(0.0, min(0.8, 2.0 * min_width / scale))

        # Return main unit size for the grid
        return cls._grid_matrix, cls._has_12_subs, cls._grid_sub_alpha

    @classmethod
    def screen_location(cls, co: Vector) -> Vector:
        """
        Compute pixel location from 3d coord
        :param co:
        :return:
        """
        pco = cls.perspective_matrix @ co.to_4d()
        pco.xy /= pco.w
        pco[0] = (pco[0] + 1.0) * cls.half_window[0]
        pco[1] = (pco[1] + 1.0) * cls.half_window[1]
        return pco.xy

    @classmethod
    def distance_pixels_from_2d(cls, pixel: Vector) -> float:
        """
        Squared length between mouse event and 3d coord
        :param pixel: Vector pixel coord
        :return: float distance
        """
        return (pixel - cls.pixel).length

    @classmethod
    def distance_pixels_from_3d(cls, coord: Vector) -> float:
        """
        Squared length between mouse event and 3d coord
        :param coord: Vector 3d coord
        :return: float distance
        """
        pixel = cls.screen_location(coord)
        return (pixel - cls.pixel).length

    @classmethod
    def distance_pixels_from_3d_sq(cls, coord: Vector) -> float:
        """
        Squared length between mouse event and 3d coord
        :param coord: Vector 3d coord
        :return: float distance
        """
        pixel = cls.screen_location(coord)
        return (pixel - cls.pixel).length_squared

    @classmethod
    def distance_from_origin(cls, coord: Vector) -> float:
        """
        Return distance from view origin (not really a z depth )
        :param coord:
        :return:
        """
        return (coord - cls.origin).length

    @classmethod
    def pixel_is_on_screen(cls, pt) -> bool:
        """
        Evaluate if a pixel coord is on screen
        :param pt: pixel location
        :return:
        """
        x, y = pt[0:2]
        wx, wy = cls.window
        return wx > x > 0 and wy > y > 0

    @classmethod
    def is_not_on_screen(cls, pt: Vector) -> bool:
        """
        Evaluate if a point is not on screen
        :param pt:  Vector world pos
        :return:
        """
        return not cls.pixel_is_on_screen(cls.screen_location(pt))

    @classmethod
    def is_on_screen(cls, pt: Vector) -> bool:
        """
        Evaluate if a point is on screen
        :param pt:  Vector world pos
        :return:
        """
        return cls.pixel_is_on_screen(cls.screen_location(pt))

    @classmethod
    def prepare_to_draw(cls, context):
        """ Compute required data for screen widgets
        :param context:
        :return:
        """
        if not cls.in_view3d(context):
            return False

        region = context.region
        rv3d = context.space_data.region_3d
        # Reset on_change by hand
        cls.dirty = cls.dirty or (cls.perspective_matrix != rv3d.perspective_matrix)
        cls._dirty_grid = cls._dirty_grid or cls.dirty
        cls.perspective_matrix[:] = rv3d.perspective_matrix.copy()
        cls.window = (int(region.width), int(region.height))

    @classmethod
    def viewport_2d_projection_matrix(cls, mvp: Matrix, coord: Vector, size: list = (10, 10)):
        """
        Compute a matrix to transform normalized coord and pixels location
        of 2d drawables for use in 3d shader
        :param mvp: projection matrix, alter "in place"
        :param coord: 3d world coord / 2d pixel
        :param size: size of item in pixels on both axis
        :return:
        """
        if len(coord) == 3:
            co = cls.perspective_matrix @ coord.to_4d()
            x, y = co.xy / co.w
        else:
            x, y = coord
            x = (x / cls.half_window[0]) - 1.0
            y = (y / cls.half_window[1]) - 1.0

        sx = size[0] / cls.half_window[0]
        sy = size[1] / cls.half_window[1]
        # normalized matrix in screen space
        mvp[:] = [
            [sx, 0, 0, x],
            [0, sy, 0, y],
            [0, 0, 1, 1],
            [0, 0, 0, 1]
        ]


class Geom2d:
    """
    Screen space (pixels) geometry utility
    """
    @classmethod
    def distance_point_segment(cls, pt: Vector, p0: Vector, p1: Vector) -> float:
        """ Distance point segment
        :param pt: point
        :param p0: line start point
        :param p1: line end point
        :return: distance
        """
        t = Geom3d.neareast_point_on_line_t(pt, p0, p1)
        if t > 1.0:
            return (pt - p1).length
        elif t < 0.0:
            return (pt - p0).length
        return (Geom3d.lerp(p0, p1, t) - pt).length

    @classmethod
    def distance_point_line(cls, pt: Vector, p0: Vector, p1: Vector) -> float:
        """ Distance point line
        :param pt: point
        :param p0: line start point
        :param p1: line end point
        :return: distance
        """
        t = Geom3d.neareast_point_on_line_t(pt, p0, p1)
        return (Geom3d.lerp(p0, p1, t) - pt).length

    @classmethod
    def point_in_area(cls, co, area):
        left, bottom, right, top = area
        return left < co[0] < right and bottom < co[1] < top

    @classmethod
    def line_cross_area(cls, line, area):
        # see https://github.com/w8r/liang-barsky/blob/master/src/liang-barsky.ts
        left, bottom, right, top = area
        p0, p1 = line[0:2]
        vx, vy = p1 - p0
        x, y = p0
        p = [-vx, vx, -vy, vy]
        q = [x - left, right - x, y - top, bottom - y]
        u1 = -1e32
        u2 = 1e23
        for i in range(4):
            if p[i] == 0:
                if q[i] < 0:
                    return False
            else:
                t = q[i] / p[i]
                if p[i] < 0 and u1 < t:
                    u1 = t
                elif p[i] > 0 and u2 > t:
                    u2 = t
        if u1 > u2 or u1 > 1 or u1 < 0:
            return False
        return True

    @classmethod
    def distance_point_point(cls, p0: Vector, p1: Vector) -> float:
        return (p1 - p0).length

    @classmethod
    def _positive(cls, x0, y0, x1, y1, x2, y2):
        return (x2 - x1) * (y0 - y1) - (x0 - x1) * (y2 - y1) > 0

    @classmethod
    def point_in_tri(cls, pt, v1, v2, v3):
        positive = cls._positive(*pt, *v1, *v2)
        if cls._positive(*pt, *v2, *v3) != positive:
            return False
        return cls._positive(*pt, *v3, *v1) == positive

    @classmethod
    def area(cls, verts: list) -> float:
        """
        :param verts:
        :return: positive area
        """
        return 0.5 * abs(
            sum(
                v0.x * v1.y - v1.x * v0.y
                for (v0, v1)
                in zip(verts, verts[1:] + [verts[0]])
            )
        )


class Geom3d:
    """
    3d space geometry utility
    """
    changeAxesDict = {
        ("X", "Z"): lambda x, y, z: (z, -y, x),
        ("X", "Y"): lambda x, y, z: (z, x, y),
        ("Y", "Z"): lambda x, y, z: (y, z, x),
        ("Y", "X"): lambda x, y, z: (x, z, -y),

        ("Z", "X"): lambda x, y, z: (x, y, z),
        ("Z", "Y"): lambda x, y, z: (-y, x, z),
        ("-X", "Z"): lambda x, y, z: (-z, y, x),
        ("-X", "Y"): lambda x, y, z: (-z, x, -y),

        ("-Y", "Z"): lambda x, y, z: (-y, -z, x),
        ("-Y", "X"): lambda x, y, z: (x, -z, y),
        ("-Z", "X"): lambda x, y, z: (x, -y, -z),
        ("-Z", "Y"): lambda x, y, z: (y, x, -z),
    }

    RIGHT = 0
    LEFT = 1
    MIDDLE = 2

    @classmethod
    def matrix_inverted(cls, matrix: Matrix, name="") -> Matrix:
        try:
            return matrix.inverted()
        except ValueError:
            logger.error("matrix %s has no inverse, fallback to inverted_safe()" % name)
            return matrix.inverted_safe()
            pass

    @classmethod
    def mouse_to_plane(cls, p_co: Vector = ZERO, p_no: Vector = Z_AXIS) -> Vector:
        """
            convert mouse pos to 3d point over plane defined by origin and normal
            return ZERO if the point is behind camera view
        """

        if isinstance(p_co, Matrix):
            p_no = p_co.col[2].xyz
            p_co = p_co.translation

        origin, direction = View.origin, View.direction

        pt = cls.intersect_ray_plane(origin, direction, p_co, p_no)

        # fix issue with parallel plane (front or left ortho view)
        if pt is None:
            pt = cls.intersect_ray_plane(origin, direction, p_co, Y_AXIS)

        if pt is None:
            pt = cls.intersect_ray_plane(origin, direction, p_co, X_AXIS)

        if pt is None:
            pt = cls.intersect_ray_plane(origin, direction, p_co, Z_AXIS)

        if pt is None:
            # fallback to a null vector
            pt = ZERO

        # if is_perspective:
        #     # Check if point is behind point of view (mouse over horizon)
        #     res = self._view_matrix_inverted(origin, direction) @ pt
        #     if res.z < 0:
        #         print("not behind camera")

        return pt

    @classmethod
    def intersect_ray_box(
            cls, origin_local: Vector, direction_local: Vector, bbmin: Vector, bbmax: Vector
    ) -> bool:
        """
        Does a ray intersect with bounding box
        Pure python port of GraphicGems ray_box()
        source : https://github.com/erich666/GraphicsGems/blob/master/gems/RayBox.c
        :param origin_local:
        :param direction_local:
        :param bbmin:
        :param bbmax:
        :return:
        """

        inside = True
        dims = 3
        quadrant = [0] * dims
        witch_plane = 0
        max_t = Vector()
        candidate_plane = [0] * dims
        coord = Vector()
        # Find candidate planes; this loop can be avoided if
        # rays cast all from the eye(assume perpsective view) */

        for i in range(dims):
            if origin_local[i] < bbmin[i]:
                quadrant[i] = cls.LEFT
                candidate_plane[i] = bbmin[i]
                inside = False
            elif origin_local[i] > bbmax[i]:
                quadrant[i] = cls.RIGHT
                candidate_plane[i] = bbmax[i]
                inside = False
            else:
                quadrant[i] = cls.MIDDLE

        # Ray origin inside bounding box */
        if inside:
            # coord = origin_local
            return True

        # Calculate T distances to candidate planes */
        for i in range(dims):
            if quadrant[i] != cls.MIDDLE and direction_local[i] != 0:
                max_t[i] = (candidate_plane[i] - origin_local[i]) / direction_local[i]
            else:
                max_t[i] = -1

        # Get largest of the max_t's for final choice of intersection */
        for i in range(dims):
            if max_t[witch_plane] < max_t[i]:
                witch_plane = i

        # Check final candidate actually inside box * /
        if max_t[witch_plane] < 0:
            return False

        for i in range(dims):
            if witch_plane != i:
                coord[i] = origin_local[i] + max_t[witch_plane] * direction_local[i]
                if coord[i] < bbmin[i] or coord[i] > bbmax[i]:
                    return False
            else:
                coord[i] = candidate_plane[i]

        return True  # ray hits box

    # ---------------
    # matrix
    # ---------------

    @classmethod
    def _safe_vectors(cls, direction: Vector, guide: Vector, main_axis: str = "X", guide_axis: str = "Z") -> tuple:
        """
        :param direction: Vector, main axis, will be preserved if guide is not perpendicular
        :param guide: Vector or None, may change if not perpendicular to main axis
        :param main_axis: ("X", "Y", "Z", "-X", "-Y", "-Z")
        :param guide_axis: ("X", "Y", "Z")
        :return: 3 non null Vectors as x, y, z axis for orthogonal Matrix
         where direction is on main_axis, guide is on guide_axis
        """
        if guide_axis[-1:] == main_axis[-1:]:
            return X_AXIS, Y_AXIS, Z_AXIS

        if direction == ZERO:
            z = Z_AXIS
        else:
            z = direction.normalized()

        # skip invalid guide
        if guide is None:
            y = ZERO
        else:
            y = z.cross(guide.normalized())

        if y.length < 0.5:
            logger.debug("Safe vectors : y(%.4f) < 0.5" % y.length)
            if guide_axis == "X":
                y = z.cross(X_AXIS)
                if y.length < 0.5:
                    y = Z_AXIS
            elif guide_axis == "Y":
                y = z.cross(Y_AXIS)
                if y.length < 0.5:
                    y = Z_AXIS
            elif guide_axis == "Z":
                y = z.cross(Z_AXIS)
                if y.length < 0.5:
                    y = Y_AXIS

        x = y.cross(z)

        logger.debug("Safe vectors %.4f %.4f %.4f" % (x.length, y.length, z.length))

        unsafe = any([v.length < 0.0001 for v in [x, y, z]])

        if unsafe:
            raise ValueError("Null vector found %s %s / %s %s %s" % (direction, guide, x, y, z))

        return cls.changeAxesDict[(main_axis, guide_axis)](x, y, z)

    @classmethod
    def normalized(cls, m: Matrix) -> Matrix:
        """Return a normalized matrix"""
        return m.normalized()

    @classmethod
    def debug(cls, m: Matrix, label: str = ""):
        for i, col in enumerate(m.col[0:3]):
            if not -EPSILON < col.xyz.length - 1.0 < EPSILON:
                logger.error("%s matrix: %s axis has a scale issue %.8f %s" % (
                    label, "xyz"[i], col.xyz.length, col.xyz
                ))

    @classmethod
    def pre_transform(cls, about: Matrix, transform: Matrix) -> Matrix:
        """
        Return
        :param about:
        :param transform:
        :return: a pre-transformed of transform about matrix
        """
        return about @ transform @ Geom3d.matrix_inverted(about)

    @classmethod
    def safe_matrix(cls, o: Vector, x: Vector, z: Vector, main_axis: str = "X", guide_axis: str = "Z") -> Matrix:
        """
        :param o: origin
        :param x: x axis direction
        :param z: z axis direction
        :param main_axis: 
        :param guide_axis: 
        :return: normalized matrix
        """
        vx, vy, vz = cls._safe_vectors(x, z, main_axis, guide_axis)
        return cls._make_matrix(o, vx, vy, vz).normalized()

    @classmethod
    def _make_matrix(cls, o: Vector, x: Vector, y: Vector, z: Vector) -> Matrix:
        """
        Create a matrix from origin and axis vectors
        :param o: 
        :param x: 
        :param y: 
        :param z: 
        :return: Matrix
        """
        return Matrix([
            [x.x, y.x, z.x, o.x],
            [x.y, y.y, z.y, o.y],
            [x.z, y.z, z.z, o.z],
            [0, 0, 0, 1]
        ])

    @classmethod
    def scale_matrix(cls, x: float, y: float, z: float) -> Matrix:
        """
        :param x: scale of x axis
        :param y: scale of y axis
        :param z: scale of z axis
        :return: scale Matrix
        """
        return Matrix([
            [x, 0, 0, 0],
            [0, y, 0, 0],
            [0, 0, z, 0],
            [0, 0, 0, 1]
        ])

    @classmethod
    def matrix_as_rotation(cls, matrix: Matrix) -> Matrix:
        """
        :param matrix:
        :return: Normalized rotation matrix without translation
        """
        rot = cls.normalized(matrix)
        rot.translation[:] = ZERO
        return rot

    @classmethod
    def matrix_from_up_and_direction(cls, o: Vector, x: Vector, z: Vector) -> Matrix:
        """
        :param o: origin
        :param x: direction of x axis
        :param z: up vector
        :return: Matrix, x axis aligned to given x,
            scale part is taken into account,
            must normalize axis inputs to get a scale of 1.0
        """
        xl = x.length
        zl = z.length
        vx, vy, vz = cls._safe_vectors(x, z)
        if xl > 0.0001:
            vx = xl * vx
        if zl > 0.0001:
            vz = zl * vz
        return cls._make_matrix(o, vx, vy, vz)

    @classmethod
    def matrix_from_normal(cls, o: Vector, z: Vector) -> Matrix:
        """
        Matrix, z axis aligned to given z 
        :param o: origin
        :param z: direction of z axis
        :return: normalized matrix
        """
        return cls.safe_matrix(o, z, Z_AXIS, "Z", "Y")

    @classmethod
    def matrix_from_view(cls, o: Vector, z: Vector) -> Matrix:
        """
        Matrix, z axis aligned to given z, with x horizontal 
        :param o: origin
        :param z: direction
        :return: normalized matrix
        """
        dz = abs(z.dot(Z_AXIS))
        if dz == 1:
            y = Y_AXIS
        else:
            y = Z_AXIS
        return cls.safe_matrix(o, z, y, "Z", "Y")

    @classmethod
    def matrix_from_3_points(
            cls, o: Vector, x: Vector, y: Vector, main_axis: str = "X", guide_axis: str = "Y"
    ) -> Matrix:
        """
        Matrix from 3 points, with x axis as main, and y axis as guide by default 
        :param o: origin
        :param x: x axis as main axis
        :param y: y axis as guide axis
        :param main_axis: axis name for main axis
        :param guide_axis: axis name for guide axis 
        :return: normalized matrix
        """
        return cls.safe_matrix(o, x - o, y - o, main_axis, guide_axis)

    @classmethod
    def view_vector(cls, context) -> Vector:
        """
        Compute view direction
        :param context: 
        :return: 
        """
        viewinv = View.get_view_invert(context.space_data.region_3d)
        direction = -viewinv.col[2].xyz
        return direction.normalized()

    # ---------------------------
    # intersections / proximity
    # ---------------------------

    @classmethod
    def lerp(cls, p0, p1, t: float):
        """
        Interpolate between p0 and p1
        :param p0: any float / Vector
        :param p1: any float / Vector
        :param t: t param normalized of location
        :return: Interpolated value
        """
        return p0 + (p1 - p0) * t

    @classmethod
    def along_segment(cls, p0: Vector, p1: Vector, dist: float) -> Vector:
        # TODO: better method name (...)
        """
        :param p0:
        :param p1:
        :param dist:
        :return: Vector of distance length in p0 p1 direction
        """
        v = p1 - p0
        v.length = dist
        return v

    @classmethod
    def intersect_ray_plane_t(cls, origin: Vector, direction: Vector, p_co, p_no=None):
        """ Intersection of ray and plane
        :param origin:, origin of ray
        :param direction: direction of ray
        :param p_co: a point on the plane (plane coordinate) or a Matrix.
        :param p_no: a normal vector defining the plane direction; (does not need to be normalized).
        :return: t param of intersection or None (when the intersection can't be found).
        """
        if isinstance(p_co, Matrix):
            p_no = p_co.col[2].xyz.normalized()
            p_co = p_co.translation
        # Skip when line is nearly parallel to plane (delta > ANGLE_MIN)
        if direction.length_squared < EPSILON or -ANGLE_MIN < p_no.angle(direction, 0) - ANGLE_90 < ANGLE_MIN:
            logger.debug("intersect_ray_plane_t ray nearly parallel, skipping")
            return None

        w = origin - p_co
        # t param of intersection from origin along direction
        t = -p_no.dot(w) / p_no.dot(direction)

        # skip when intersection is too far from line origin (low angle)
        if (t * direction).length > TOO_FAR:
            logger.debug("intersect_ray_plane_t intersection occurs too far, skipping")
            return None
        return t

    @classmethod
    def intersect_ray_plane(cls, origin: Vector, direction: Vector, p_co, p_no=None):
        """ Intersection of ray and plane
        :param origin:, origin of ray
        :param direction: direction of ray
        :param p_co: a point on the plane (plane coordinate) or a Matrix.
        :param p_no: a normal vector defining the plane direction; (does not need to be normalized).
        :return: a Vector or None (when the intersection can't be found).
        """
        t = cls.intersect_ray_plane_t(origin, direction, p_co, p_no)
        if t is None:
            return None

        return origin + t * direction

    @classmethod
    def intersect_line_plane(cls, p0: Vector, p1: Vector, p_co, p_no=None):
        """ Intersection of line and plane not limited in line interval
        :param p0: line point 0
        :param p1: line point 1
        :param p_co: a point on the plane (plane coordinate) or a Matrix.
        :param p_no: a normal vector defining the plane direction; (does not need to be normalized).
        :return: a Vector or None (when the intersection can't be found)
        """
        direction = (p1 - p0).normalized()
        return cls.intersect_ray_plane(p0, direction, p_co, p_no)

    @classmethod
    def intersect_segment_plane(cls, p0: Vector, p1: Vector, p_co, p_no=None):
        """ Intersection of line and plane limited in line interval [0 | 1]
        :param p0: line point 0
        :param p1: line point 1
        :param p_co: a point on the plane (plane coordinate) or a Matrix.
        :param p_no: a normal vector defining the plane direction; (does not need to be normalized).
        :return: a Vector or None (when the intersection can't be found) limited in line interval [0 | 1]
        """
        direction = p1 - p0
        t = cls.intersect_ray_plane_t(p0, direction, p_co, p_no)
        # The segment is either parallel to plane or not crossing the plane
        if t is None or not 0 <= t <= 1:
            return None
        return p0 + t * direction

    @classmethod
    def neareast_point_plane(cls, pt: Vector, p_co, p_no=None) -> Vector:
        if isinstance(p_co, Matrix):
            plane = p_co
        else:
            plane = cls.matrix_from_normal(p_co, p_no)
        pos = cls.matrix_inverted(plane) @ pt
        pos.z = 0
        return plane @ pos

    @classmethod
    def neareast_point_on_line_t(cls,  pt: Vector, v0: Vector, v1: Vector) -> float:
        """
        :param v0:
        :param v1:
        :param pt:
        :return: t param of nearest point over line
        """
        d = v1 - v0
        a = pt - v0
        dl = d.length_squared
        if dl == 0:
            # Prevent division by zero errors
            return 0
        return a.dot(d) / dl

    @classmethod
    def neareast_point_on_line(cls, pt: Vector, v0: Vector, v1: Vector) -> Vector:
        """Return
       :param v0:
       :param v1:
       :param pt:
       :return: location of nearest point over line
       """
        t = cls.neareast_point_on_line_t(pt, v0, v1)
        return cls.lerp(v0, v1, t)

    @classmethod
    def neareast_point_ray_line_t(cls, origin: Vector, direction: Vector, p0: Vector, p1: Vector):
        """ NOTE: ~10x faster than numpy.linalg (..)
        :param p0:
        :param p1:
        :param origin:
        :param direction: normalized vector to prevent precision issues
        :return: t param of line p0 - p1 nearest point or None if parallel / coincident
        """
        a = p1 - p0
        fac = 1.0
        n = a.cross(direction)
        nlen = n.length_squared

        # may be very small or large with small or huge segment, leading to precision issue
        if nlen < EPSILON or 1.0 / nlen < EPSILON:
            fac = a.length
            a = a.normalized()
            n = a.cross(direction)
            nlen = n.length_squared

        angle = a.angle(direction, 0)
        # Skip nearly parallel / too small / large to prevent precision issues
        if angle > ANGLE_MAX or angle < ANGLE_MIN or nlen < EPSILON or 1.0 / nlen < EPSILON:
            logger.debug("Segment too small / big (%.8f), or nearly parallel (min %.4f° < angle %.4f° < max %.4f°)" % (
                    nlen,
                    degrees(ANGLE_MIN),
                    degrees(angle),
                    degrees(ANGLE_MAX)
            ))
            return None
        c = n + origin - p0
        cray = c.cross(direction)
        return cray.dot(n) / (fac * nlen)

    @classmethod
    def neareast_point_ray_line(cls, origin: Vector, direction: Vector, p0: Vector, p1: Vector):
        """
        :param origin:
        :param direction:
        :param p0:
        :param p1:
        :return: nearest point or None if parallel / coincident
        """
        t = cls.neareast_point_ray_line_t(origin, direction, p0, p1)
        if t is None:
            return None
        return cls.lerp(p0, p1, t)

    @classmethod
    def neareast_point_line_line_t(cls, p0: Vector, p1: Vector, p2: Vector, p3: Vector):
        """
        :param p0: first knot of ref line
        :param p1: last knot of ref line
        :param p2: first knot of target line
        :param p3: last knot of target line
        :return:  t param of intersection on ref line or none if parallel or coincident
        """
        direction = (p3 - p2).normalized()
        return cls.neareast_point_ray_line_t(p2, direction, p0, p1)

    @classmethod
    def neareast_point_line_line(cls, p0: Vector, p1: Vector, p2: Vector, p3: Vector):
        """
       :param p0: first knot of ref line
       :param p1: last knot of ref line
       :param p2: first knot of target line
       :param p3: last knot of target line
       :return: nearest point on ref line or none if parallel or coincident
       """
        t = cls.neareast_point_line_line_t(p0, p1, p2, p3)
        if t is None:
            return None
        return cls.lerp(p0, p1, t)

    @classmethod
    def intersect_line_line(cls, p0: Vector, p1: Vector, p2: Vector, p3: Vector):
        """
       :param p0: first knot of ref line
       :param p1: last knot of ref line
       :param p2: first knot of target line
       :param p3: last knot of target line
       :return: intersection point on ref line or none if parallel or coincident, not limited by line interval
       """
        t = cls.neareast_point_line_line_t(p0, p1, p2, p3)
        if t is None:
            return None
        return cls.lerp(p0, p1, t)

    @classmethod
    def intersect_ray_tri_t(cls, origin: Vector, direction: Vector, v0: Vector, v1: Vector, v2: Vector):
        edge1 = v1 - v0
        edge2 = v2 - v0
        if any([ed.length_squared < EPSILON for ed in [edge1, edge2]]):
            return None
        # Skip when line is nearly parallel to this triangle.
        if -ANGLE_MIN < edge2.cross(edge1).angle(direction, 0) - ANGLE_90 < ANGLE_MIN:
            return None
        h = direction.cross(edge2)
        s = origin - v0
        q = s.cross(edge1)
        # At this stage we can compute t to find out where the intersection point is on the line.
        t = edge2.dot(q) / edge1.dot(h)
        return t

    @classmethod
    def intersect_line_tri(cls, p0: Vector, p1: Vector, v0: Vector, v1: Vector, v2: Vector):
        t = cls.intersect_ray_tri_t(p0, p1 - p0, v0, v1, v2)
        if t is None:
            return None
        return cls.lerp(p0, p1, t)

    @classmethod
    def triangle_normal(cls, p0: Vector, p1: Vector, p2: Vector) -> Vector:
        v0 = (p1 - p0).normalized()
        v2 = (p2 - p0).normalized()
        return v0.cross(v2)

    @classmethod
    def triangle_center(cls, p0: Vector, p1: Vector, p2: Vector) -> Vector:
        return (1.0/3.0) * (p0 + p1 + p2)

    @classmethod
    def signed_angle(cls, v0: Vector, v1: Vector, z: Vector = None) -> float:
        """
        :param v0:
        :param v1:
        :param z: Plane normal to evaluate angle, will be cross vectors if None
        :return: signed angle radians in range [-pi | pi]
        """
        _v0 = v0.normalized()
        _v1 = v1.normalized()
        if z is None:
            _z = _v0.cross(_v1)
        else:
            _z = z.normalized()
        return atan2((_v0.cross(_v1)).dot(_z), _v0.dot(_v1))

    @classmethod
    def close_enough(cls, p0: Vector, p1: Vector, tolerance: float = CLOSE_ENOUGH) -> bool:
        """
        Return True when points are at same location
        :param p0:
        :param p1:
        :param tolerance:
        :return:
        """
        for i, axis in enumerate(p0):
            if not (-tolerance < axis - p1[i] < tolerance):
                return False
        return True
