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
import os
import time
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
from mathutils import Vector, Matrix
from .types import (
    ShaderType,
    State,
    BatchType,
    TransformType,
    SnapType,
    SpaceType,
    TextType,
    ConstraintType
)
from .units import Units
from .transform import (
    Transform,
    Space,
)
from .constraint import Constraint
from .drawable import (
    Drawable,
    Line,
    Circle,
    Square,
    Pie,
    Text,
    Image
)
from .event import Events
from .offscreen import OffscreenShader
from .geom import (
    View,
    Geom2d,
    Geom3d,
    MATRIX_WORLD,
    ZERO,
    X_AXIS,
    Y_AXIS,
    Z_AXIS,
    RED
)
from .preferences import Prefs
from .i18n import i18n
logger = get_logger(__name__, 'ERROR')


# ------------------------
# Selectable
# ------------------------


class Selectable:
    """
    Represent a "selectable" handle with 3 states colors
    """
    def __init__(self, colors):
        self.colors = colors
        # kept here
        self.state = State.NORMAL

    def _compute_hover(self, context) -> bool:
        """ Compute hover state
        :param context:
        :return: True when HOVER
        """
        return False

    def detect_hover(self, context):
        """
        Alter state on mouse move
        :param context:
        :return:
        """
        if self.state == State.ACTIVE:
            logger.debug("Handle skip ACTIVE")
            return
        if self._compute_hover(context):
            logger.debug("Handle: set HOVER")
            self.state = State.HOVER
        else:
            self.state = State.NORMAL

    @property
    def hover(self) -> bool:
        """
        :return: HOVER state
        """
        return self.state == State.HOVER

    @property
    def active(self) -> bool:
        """
        :return: ACTIVE state
        """
        return self.state == State.ACTIVE

    def press(self, context) -> bool:
        """
        Alter state on press
        :param context:
        :return:  True when ACTIVE
        """
        if self.state == State.HOVER:
            self.state = State.ACTIVE
            return True
        return False

    def release(self):
        """
        Alter state to NORMAL on release
        :return:
        """
        self.state = State.NORMAL


# ------------------------
# Detectable
# ------------------------


class Detectable(Drawable):
    """
        Represent a virtual snap-able object
    """

    def __init__(
            self, obj, mat: Matrix = MATRIX_WORLD, mode: int = 0, batch_type: int = BatchType.POINTS,
            co: list = None,  indices: list = None
    ):
        """
        :param obj: Mixed blender object or Virtual unique ID
        :param mat: Matrix to transform coord into world
        :param mode: flag snap mode to enable
        :param batch_type: batch type
        :param co:
        :param indices:
        """
        prefs = Prefs.get()
        color = prefs.color_detectable
        Drawable.__init__(self, mat, co, indices, batch_type, ShaderType.UNIFORM_3D, color)

        self.obj = obj
        # snap mode
        self.mode = mode
        # Snap buffer related
        self.offset = 0
        self.buffer_size = 0
        self.offscreen_batch = None
        self.ibo = None
        self.offscreen_vbo = None
        # flag to prevent mesh isolated re-evaluation
        self.is_empty = False
        # Colors for detectable points
        self.colors = {
            SnapType.NONE: color,
            SnapType.VIRTUAL | SnapType.BOUNDS: prefs.color_detectable_center,
            SnapType.VIRTUAL | SnapType.ORIGIN: prefs.color_detectable_median,
            SnapType.BOUNDS: prefs.color_detectable_bounds,
            SnapType.ORIGIN: prefs.color_detectable_origin,
            SnapType.ISOLATED | SnapType.VERT: prefs.color_detectable_isolated,
            SnapType.CENTER: prefs.color_detectable_center
        }
        # Bounding rectangle pixels
        self.bound_rect = [0, 0, 0, 0]

    @property
    def color(self):
        """
        :return: Color according to mode
        """
        if self.mode in self.colors:
            return self.colors[self.mode]
        return self.colors[SnapType.NONE]

    @property
    def world_coords(self) -> list:
        """
        Compute coord in world system
        :return:
        """
        return [self.matrix_world @ co for co in self.co]

    def __str__(self):
        if hasattr(self.obj, 'name'):
            name = self.obj.name
        else:
            name = self.obj

        return "%s offset: %s size: %s %s  %s" % (
            self.batch_type,
            self.offset,
            self.buffer_size,
            SnapType(self.mode),
            name
        )

    @property
    def normal(self):
        return self.matrix_world.col[2].to_3d()

    def create_batch(self):
        """
        Create off screen batch in lazy fashion
        :return:
        """
        if self.co is None or len(self.co) == 0:
            logger.info("Detectable.create_batch() self.co is either None or len < 1")
            return

        self.offscreen_batch, self.offscreen_vbo, self.ibo, self.buffer_size = OffscreenShader.batch(self)

    def get_co(self, index):
        """
        :param index: index of coord item detected
        :return: coord of item with given index in world coord system
        """
        raise NotImplementedError

    def _update_offscreen_batch(self):
        self._delete_offscreen_batch()
        View.dirty = True

    def _delete_offscreen_batch(self):
        del self.offscreen_vbo
        if self.ibo is not None:
            del self.ibo
        del self.offscreen_batch
        self.offscreen_vbo = None
        self.ibo = None
        self.offscreen_batch = None

    def __del__(self):
        self._delete_offscreen_batch()


class DetectablePoints(Detectable):
    """
        A generic points container
    """
    def __init__(self, obj, mat: Matrix = MATRIX_WORLD, mode: int = 0, co: list = None, indices: list = None):
        Detectable.__init__(self, obj, mat, mode, BatchType.POINTS, co, indices)
        prefs = Prefs.get()
        self.point_size = prefs.detectable_point_size

    def get_co(self, index):
        return self.matrix_world @ Vector(self.co[index])


class DetectableLines(Detectable):
    """
        A generic lines container
    """

    def __init__(self, obj, mat: Matrix = MATRIX_WORLD, mode: int = 0, co: list = None, indices: list = None):
        Detectable.__init__(self, obj, mat, mode, BatchType.LINES, co, indices)

    def get_co(self, index):
        i = index * 2
        if i + 2 > 2 * self.buffer_size:
            logger.error("index", i, ">", 2 * self.buffer_size)
            i = 0
        return [self.matrix_world @ Vector(co) for co in self.co[i:i + 2]]


class DetectableTris(Detectable):
    """
        A generic tris container
    """
    def __init__(self, obj, mat: Matrix = MATRIX_WORLD, mode: int = 0, co: list = None, indices: list = None):
        Detectable.__init__(self, obj, mat, mode, BatchType.TRIS, co, indices)

    def get_co(self, index):
        i = index * 3
        if index + 3 > 3 * self.buffer_size:
            logger.error("index", i, ">", 3 * self.buffer_size)
            i = 0

        return [self.matrix_world @ Vector(co) for co in self.co[i:i + 3]]


# ------------------------
# Snap helpers
# ------------------------


class SnapHelper(Selectable):
    """
        Virtual snap target not found in scene
        set complex constraints
        through user interaction
        drawn on screen

        IMPORTANT:
        Child class must inherit from Detectable

        NOTE :
        Should rely on local matrix so we are able to
        manipulate location using that matrix and components in local space
        Ideally rely on fixed coord and matrix to set size, location and orientation.
    """

    def __init__(self):
        """
        """
        prefs = Prefs.get()
        colors = {
            State.NORMAL: prefs.color_helpers_normal,
            State.HOVER: prefs.color_helpers_hover,
            State.ACTIVE: prefs.color_active
        }
        Selectable.__init__(self, colors)

    @property
    def color(self):
        """
        NOTE: defined here as detectable use .mode for colors,
        where helpers expect .state based colors
        :return: Color according to state
        """
        return self.colors[self.state]

    def edit(self):
        """
        Refresh target component
        :return:
        """
        pass

    def confirm(self, context):
        """
        :return:
        """
        if self.state == State.ACTIVE:
            self.release()

    def _create_handles(self, context):
        """
        Create handles to modify the object on screen
        :param context:
        :return:
        """
        raise NotImplementedError

    def press(self, context) -> bool:
        """
        When HOVER, create handles and set state to ACTIVE
        This will also clear other handles and set SnapHelpers to NORMAL state
        :return: True when ACTIVE
        """
        if self.state == State.HOVER:
            # remove any active handle / reset other helpers state
            Handles.exit()
            # Create handles
            self._create_handles(context)
            self.state = State.ACTIVE
            return True
        return False


class SnapHelperPoints(SnapHelper, DetectablePoints):
    """
        Freeform point
    """
    def __init__(
        self, obj, mat: Matrix = MATRIX_WORLD, mode: int = SnapType.VIRTUAL, co: list = None, indices: list = None
    ):
        DetectablePoints.__init__(self, obj, mat, mode, co, indices)
        SnapHelper.__init__(self)
        self.co = [ZERO.copy()]
        self.matrix_world[:] = Matrix.Translation(co[0])
        prefs = Prefs.get()
        self.point_size = prefs.point_size

    def copy(self):
        return SnapHelperPoints(self.obj, Matrix(), self.mode, self.world_coords, self.indices)

    def _compute_hover(self, context) -> bool:
        co = self.world_coords
        prefs = Prefs.get(context)
        return View.distance_pixels_from_3d(co[0]) < prefs.snap_radius

    def _create_handles(self, context):

        Handles.add(
            SquareHandle(self.matrix_world.copy(), TransformType.MOVE, self.matrix_world.translation)
        )


class SnapHelperLines(SnapHelper, DetectableLines):
    """
        Freeform segment
    """
    def __init__(
        self, obj, mat: Matrix = MATRIX_WORLD, mode: int = SnapType.VIRTUAL, co: list = None, indices: list = None
    ):
        """
        :param obj:
        :param mat:
        :param mode:
        :param co: world coord of 2 points
        :param indices:
        """
        # prefs = Prefs.get()
        DetectableLines.__init__(self, obj, mat, mode, None, indices)
        SnapHelper.__init__(self)
        # Normalized coord for batch, location, rotation and size are stored in matrix_world
        self.co = [ZERO.copy(), X_AXIS.copy()]
        # self.center = 0.5 * X_AXIS
        self._compute_matrix(co)

    def copy(self):
        return SnapHelperLines(self.obj, Matrix(), self.mode, self.world_coords, self.indices)

    def _compute_matrix(self, co: list):
        """
        Compute a matrix so
            origin is the first point
            x axis is aligned with the line
            scale match with line length
        So coord remains normalized
        :param co: world coord
        :return:
        NOTE: rely on in place assignment as we use the matrix reference in handles
        """
        o, p = co[0:2]
        x = p - o
        # this method handle input axis scale
        self.matrix_world[:] = Geom3d.matrix_from_up_and_direction(o, x, Z_AXIS)

    def edit(self):
        """
        On edit using handles, we do update matrix_world so we never need rebuild batch whatever the size
        :return:
        """
        # if self.center != 0.5 * X_AXIS:
        #     self.matrix_world.translation[:] = self.matrix_world @ (self.center - 0.5 * X_AXIS)

        self._compute_matrix(self.world_coords)
        # reset changed location as transformation are now stored in matrix
        # self.co[0][:] = ZERO
        self.co[1][:] = X_AXIS
        # self.center[:] = 0.5 * X_AXIS

    def _compute_hover(self, context) -> bool:
        prefs = Prefs.get(context)
        pt = View.pixel
        co = self.world_coords[0:2]
        pix = [View.screen_location(p) for p in co]
        for i, p1 in enumerate(pix[1:]):
            p0 = pix[i]
            dist = Geom2d.distance_point_segment(pt, p0, p1)
            # logger.debug("hover : %s %.4f" % (dist < 0.5 * prefs.snap_radius, dist))
            if dist < prefs.snap_radius:
                return True
        return False

    def _create_handles(self, context):
        logger.debug("SnapHelperLines._create_handles()")

        p0, p1 = self.world_coords
        s = SquareHandle(Matrix.Translation(p0), TransformType.MOVE, self.matrix_world.translation)
        # s = SquareHandle(Matrix.Translation(0.5 * (p0 + p1)), TransformType.MOVE, self.center, self.matrix_world)
        # c0 = CircleHandle(Matrix.Translation(p0), TransformType.MOVE, self.co[0], self.matrix_world)
        c1 = CircleHandle(Matrix.Translation(p1), TransformType.MOVE, self.co[1], self.matrix_world)
        Handles.add(s)
        # Handles.add(c0)
        Handles.add(c1)

# TODO: implement SnapHelperCircle and other shapes


class SnapHelperTris(SnapHelper, DetectableTris):
    """
        Freeform tri
    """
    def __init__(
        self, obj, mat: Matrix = MATRIX_WORLD, mode: int = SnapType.VIRTUAL, co: list=None, indices: list=None
    ):
        """
        :param obj:
        :param mat:
        :param mode:
        :param co: world coord of 3 points, origin, x axis, y axis
        :param indices:
        """
        DetectableTris.__init__(self, obj, mat, mode, co, indices)
        SnapHelper.__init__(self)

        self.indices = [(0, 1, 2)]
        self.co = [ZERO.copy(), X_AXIS.copy(), Y_AXIS.copy()]
        self._compute_matrix((mat @ i for i in self.co))

    def copy(self):
        return SnapHelperTris(self.obj, Matrix(), self.mode, self.world_coords, self.indices)

    def _compute_matrix(self, co, main_axis: str="X", guide_axis: str="Y"):
        """
        Compute a matrix so
            origin is the first point
            axis are aligned with the points
            scale match with line length
        So coord remains normalized
        :param co: world coord
        :return:
        NOTE: rely on in place assignment as we use the matrix reference in handles
        """
        self.matrix_world[:] = Geom3d.matrix_from_3_points(*co, main_axis, guide_axis)

    def edit(self):
        main_axis, guide_axis = "X", "Y"
        o, x, y = self.world_coords[0:3]

        if self.co[1] != X_AXIS:
            main_axis, guide_axis = guide_axis, main_axis
            x, y = y, x

        self._compute_matrix([o, x, y], main_axis, guide_axis)

        self.co[1][:] = X_AXIS
        self.co[2][:] = Y_AXIS

    def _compute_hover(self, context) -> bool:
        pt = View.pixel
        co = self.world_coords
        for index in self.indices:
            i, j, k = index
            p0 = View.screen_location(co[i])
            p1 = View.screen_location(co[j])
            p2 = View.screen_location(co[k])
            if Geom2d.point_in_tri(pt, p0, p1, p2):
                return True
        return False

    def _create_handles(self, context):

        p0, p1, p2 = self.world_coords[0:3]
        s = SquareHandle(Matrix.Translation(p0), TransformType.MOVE, self.matrix_world.translation)
        x = CircleHandle(Matrix.Translation(p1), TransformType.MOVE, self.co[1], self.matrix_world)
        y = CircleHandle(Matrix.Translation(p2), TransformType.MOVE, self.co[2], self.matrix_world)
        Handles.add(s)
        Handles.add(x)
        Handles.add(y)


class SnapHelpers:
    """
    Store virtual snap helpers
    """

    # separated to control the draw order
    _points = []
    _lines = []
    _tris = []

    # Enable display and hover detection
    _enabled = False

    # SnapHelper in ACTIVE state
    active = None

    @classmethod
    def helpers(cls) -> list:
        return cls._tris + cls._lines + cls._points

    @classmethod
    def draw(cls, context):
        if cls._enabled and View.in_region(context):
            # logger.debug("SnapHelpers.draw()")
            for helper in cls.helpers():
                helper.draw()

    @classmethod
    def remove_active(cls, context):
        """
        Remove active helper from stack
        :return:
        """
        if cls.active is not None:
            cls.remove(cls.active.obj)
            helpers = cls.helpers()
            if helpers:
                # Make last one active
                # This is not the last selected one, but sorted by type
                cls.active.state = State.HOVER
                # Create handles
                cls.active.press(context)
                # Remove ACTIVE state
                cls.release()
                cls.active = helpers[-1]
            else:
                cls.active = None

    @classmethod
    def detect_hover(cls, context):
        """
        Compute HOVER state
        :param context:
        :return:
        """
        if cls._enabled:
            for helper in cls.helpers():
                helper.detect_hover(context)

    @classmethod
    def release(cls):
        """
        Set MORMAL state, remove active
        :return:
        """
        for helper in cls.helpers():
            helper.release()
        cls.active = None

    @classmethod
    def press(cls, context) -> bool:
        """
        When HOVER, create handles and set state to ACTIVE
        Clear other handles
        Set SnapHelpers to NORMAL state
        Store ACTIVE SnapHelper
        :return: True when ACTIVE
        """
        if cls._enabled:
            for helper in cls.helpers():
                if helper.press(context):
                    cls.release()
                    cls.active = helper
                    return True
        return False

    @classmethod
    def edit(cls):
        """
        Refresh screen coord on edit, update handle location
        :return:
        """
        if cls._enabled:
            for helper in cls.helpers():
                helper.edit()
            Handles.update_location()

    @classmethod
    def confirm(cls, context):
        """
        Restore NORMAL state, refresh matrix_world
        :return:
        """
        cls.edit()
        if cls._enabled:
            for helper in cls.helpers():
                helper.confirm(context)

    @classmethod
    def show(cls):
        """
        Enable display
        :return:
        """
        cls._enabled = True

    @classmethod
    def hide(cls):
        """
        Disable display
        :return:
        """
        cls._enabled = False

    @classmethod
    def clear(cls):
        """
        Clear all helpers
        :return:
        """
        helpers = cls.helpers()
        for i in range(len(helpers) - 1, 0, -1):
            del helpers[i]
        cls._points.clear()
        cls._lines.clear()
        cls._tris.clear()
        cls.active = None

    @classmethod
    def exit(cls):
        """
        Clear all SnapHelpers
        :return:
        """
        cls.clear()
        cls.hide()

    @classmethod
    def _detectable_by_type(cls, obj, typ):
        # TODO: Use SnapTargetType instead of BatchType to support Circle
        for detectable in cls.helpers():
            if detectable.obj == obj and detectable.batch_type == typ:
                return detectable
        return None

    @classmethod
    def create(cls, obj, co, mat: Matrix = MATRIX_WORLD, typ: int = BatchType.NONE):

        # TODO: Use SnapTargetType instead of BatchType to support Circle

        target = None

        if typ == BatchType.POINTS:
            target = SnapHelperPoints(obj, mat, SnapType.VERT | SnapType.VIRTUAL, co)
            cls._points.append(target)

        elif typ == BatchType.LINES:
            target = SnapHelperLines(obj, mat, SnapType.EDGE | SnapType.VIRTUAL, co)
            cls._lines.append(target)

        elif typ == BatchType.TRIS:
            target = SnapHelperTris(obj, mat, SnapType.FACE | SnapType.VIRTUAL, co)
            cls._tris.append(target)

        return target

    @classmethod
    def add(cls, snaphelper):

        logger.debug("Add %s" % snaphelper)

        if snaphelper.batch_type == BatchType.POINTS:
            cls._points.append(snaphelper)
        elif snaphelper.batch_type == BatchType.LINES:
            cls._lines.append(snaphelper)
        elif snaphelper.batch_type == BatchType.TRIS:
            cls._tris.append(snaphelper)
        else:
            logger.error("batch type not found: %s" % snaphelper.batch_type)

    @classmethod
    def _remove(cls, obj, _from):
        for i, detectable in enumerate(_from):
            if detectable.obj == obj:
                _from.pop(i)
                # trigger snap buffer redraw
                View.dirty = True
                return True
        return False

    @classmethod
    def remove(cls, obj):
        """
        Remove a helper by obj
        :param obj:
        :return:
        """
        if cls._remove(obj, cls._lines):
            return
        elif cls._remove(obj, cls._points):
            return
        elif cls._remove(obj, cls._tris):
            return


# ------------------------
# Editable handles
# ------------------------


class Handle(Selectable):
    """
    Handle transform action and target of the handle
    NOTE:
        Matrix world must be normalized

        May either transform "pos" property of Drawable (matrix_world.translation)
        or coord of components

        Component coord are in local space, but transform occurs in world space
        Pos coord are in world space

    """
    def __init__(
            self, action: int = TransformType.NONE, target=None,
            space: Matrix = MATRIX_WORLD, space_type: int = SpaceType.WORLD
    ):
        prefs = Prefs.get()
        colors = {
            State.NORMAL: prefs.color_handle_normal,
            State.HOVER: prefs.color_handle_hover,
            State.ACTIVE: prefs.color_handle_active
        }
        Selectable.__init__(self, colors)
        self.action = action
        self.target = target
        self.space_type = space_type
        self.space = space


class CircleHandle(Handle, Circle):
    """
    A handle to transform helper's coord in local space
    """
    def __init__(
            self, mat: Matrix, action: int = TransformType.NONE, target=None,
            space: Matrix = MATRIX_WORLD, batch_type: int = BatchType.LINES, space_type: int = SpaceType.WORLD
    ):
        """
        :param mat: normalized Matrix with location set
        :param action: TransformType
        :param target: component coord Vector
        :param space: object matrix_world to compute coord in local space
        :param batch_type: BatchType.LINES | TRIS
        """

        Circle.__init__(self, mat, RED, batch_type)
        Handle.__init__(self, action, target, space, space_type)

    def update_target(self):
        """
        Handle Transformation.move
        The operation alter handle matrix_world, but we still need to transform target according
        There are 2 kind of target -> we may handle the 2 cases using different handles
            Main matrix world
            Sub coord
        """
        self.target[0:3] = self.space.inverted_safe() @ self.pos

    def update_location(self):
        """
        Refresh handle location using target
        :return:
        """
        if self.state != State.ACTIVE:
            self.pos[0:3] = self.space @ self.target

    def _compute_hover(self, context) -> bool:
        # prefs = Prefs.get(context)
        dist = View.distance_pixels_from_3d(self.pos)
        return dist < 0.6 * self.size[0]


class SquareHandle(Handle, Square):
    """
    A handle to transform helper's matrix world
    """
    def __init__(
            self, mat: Matrix, action: int = TransformType.NONE, target=None,
            space: Matrix = MATRIX_WORLD, batch_type: int = BatchType.TRIS, space_type: int = SpaceType.WORLD
    ):
        """
        :param mat: normalized Matrix with location set
        :param action: TransformType
        :param target: object's .pos (matrix_world.translation)
        :param batch_type: BatchType.LINES | TRIS
        """
        Square.__init__(self, mat, RED, batch_type)
        Handle.__init__(self, action, target, space, space_type)

    def update_target(self):
        """
        Handle Transformation.move
        The operation alter handle matrix_world, but we still need to transform target according
        There are 2 kind of target -> we may handle the 2 cases using different handles
            Main matrix world
            Sub coord
        """
        self.target[0:3] = self.space.inverted_safe() @ self.pos

    def update_location(self):
        """
        Refresh handle location using target
        :return:
        """
        if self.state != State.ACTIVE:
            self.pos[0:3] = self.space @ self.target

    def _compute_hover(self, context) -> bool:
        # prefs = Prefs.get(context)
        dist = View.distance_pixels_from_3d(self.pos)
        return dist < 0.6 * self.size[0]


class Handles:
    """
    A store for handles
    """
    _handles = []
    _transformation = None

    @classmethod
    def update_location(cls):
        """
        Apply transformation
        :return:
        """
        # logger.debug("Hamdles.update_location()")
        for handle in cls._handles:
            handle.update_location()

    @classmethod
    def detect_hover(cls, context):
        """
        compute HOVER state
        :param context:
        :return:
        """
        for handle in cls._handles:
            # compute HOVER state
            handle.detect_hover(context)

    @classmethod
    def press(cls, context):
        """
        Start transform operation
        :return: active Handle or None
        """
        for handle in cls._handles:
            if handle.press(context):
                logger.debug("Hamdles.press() found handle")
                return handle
        return None

    @classmethod
    def release(cls):
        """
        restore NORMAL state
        :return:
        """
        logger.debug("Handles.release()")
        for handle in cls._handles:
            handle.release()

    @classmethod
    def cancel(cls, context):
        # if cls._transformation is not None:
        #    cls._transformation.cancel(context)
        logger.debug("Handles.cancel()")
        cls.exit()

    @classmethod
    def draw(cls, context):
        if View.in_region(context):
            for handle in cls._handles:
                # logger.debug("Handles.draw()")
                handle.update_location()
                handle.draw()

    @classmethod
    def add(cls, handle: Handle):
        cls._handles.append(handle)

    @classmethod
    def exit(cls):
        for handle in cls._handles[:]:
            del handle
        cls._handles.clear()


# ------------------------
# Editable widgets
# ------------------------


class Tripod:

    """
    A Matrix snap-able widget with 4 points : origin and xyz axis
    """

    def __init__(self, context):
        """
        :param context:
        :return:
        """
        self.matrix_world = Matrix()
        self._display_matrix = Matrix()

        self.co = [ZERO, X_AXIS, Y_AXIS, Z_AXIS]
        x = [ZERO, X_AXIS]
        y = [ZERO, Y_AXIS]
        z = [ZERO, Z_AXIS]
        line = [(0, 1)]
        # Create axis tripod, may rely on preferences widget scale
        theme = context.preferences.themes[0].user_interface

        self.axis = [
            Drawable(self._display_matrix, x, line, BatchType.LINES, ShaderType.UNIFORM_3D, (*theme.axis_x, 1)),
            Drawable(self._display_matrix, y, line, BatchType.LINES, ShaderType.UNIFORM_3D, (*theme.axis_y, 1)),
            Drawable(self._display_matrix, z, line, BatchType.LINES, ShaderType.UNIFORM_3D, (*theme.axis_z, 1))
        ]
        self.labels = [
            Text(context, "X", TextType.TEXT_3D | TextType.CENTER, (*theme.axis_x, 1)),
            Text(context, "Y", TextType.TEXT_3D | TextType.CENTER, (*theme.axis_y, 1)),
            Text(context, "Z", TextType.TEXT_3D | TextType.CENTER, (*theme.axis_z, 1))
        ]
        self.scale = 0.025
        # disabled by default
        self.enabled = False

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    @property
    def pos(self) -> Vector:
        return self.matrix_world.translation

    @property
    def world_coords(self) -> list:
        return [self._display_matrix @ co for co in self.co]

    def draw(self, context):
        if self.enabled and View.in_region(context) and View.is_on_screen(self.pos):
            # logger.debug("%s.draw()" % self.__class__.__name__)
            scale = self.scale * View.width_at_dist(context, self.pos)
            self._display_matrix[:] = self.matrix_world @ Matrix.Scale(scale, 4)
            for axis in self.axis:
                axis.draw()
            co = [self._display_matrix @ (1.2 * p) for p in self.co[1:4]]
            for i, label in enumerate(self.labels):
                label.draw(context, co[i])


class Pivot(Tripod):

    """
    A Matrix snap-able widget with 4 points : origin and xyz axis
    """

    def __init__(self, context, matrix_world: Matrix):
        """
        :param matrix_world: a matrix_world
        :return:
        """
        Tripod.__init__(self, context)
        self.matrix_world = matrix_world
        self.scale = 0.05
        self.enabled = True


class Grid:

    def __init__(self, context, matrix_world: Matrix, steps: int = 20):

        # Do not display by default
        self.enabled = False

        # NOTE:
        # grid main steps are of 1 size
        # so we may round from this space to snap using step factor
        self.matrix_world = matrix_world

        # number of "main" units lines
        self.steps = steps
        x0, x1 = -0.5 * steps, 0.5 * steps

        main_co = []
        for i in range(steps + 1):
            if i == int(steps / 2):
                continue
            y = round(x0 + i, 0)
            main_co.extend([(x0, y, 0), (x1, y, 0), (y, x0, 0), (y, x1, 0)])

        main_idx = [(i, i + 1) for i in range(0, len(main_co), 2)]

        sub_10 = []
        subs = 10
        for i in range(steps):
            for j in range(subs - 1):
                y = round(x0 + i + (j + 1) / subs, 5)
                sub_10.extend([(x0, y, 0), (x1, y, 0), (y, x0, 0), (y, x1, 0)])

        sub_idx_10 = [(i, i + 1) for i in range(0, len(sub_10), 2)]

        sub_12 = []
        subs = 12
        for i in range(steps):
            for j in range(subs - 1):
                y = round(x0 + i + (j + 1) / subs, 5)
                sub_12.extend([(x0, y, 0), (x1, y, 0), (y, x0, 0), (y, x1, 0)])

        sub_idx_12 = [(i, i + 1) for i in range(0, len(sub_12), 2)]

        theme = context.preferences.themes[0]
        x_color = (*theme.user_interface.axis_x, 0.5)
        y_color = (*theme.user_interface.axis_y, 0.5)

        main_color = theme.view_3d.grid
        sub_color = (*theme.view_3d.grid[0:3], 0.2)

        # Space.grid is a display only matrix, kept in Space across session
        self._display_matrix = Matrix()

        mat = self._display_matrix
        half = 0.5 * steps
        self.grid = Drawable(mat, main_co, main_idx, BatchType.LINES, ShaderType.UNIFORM_3D, main_color)
        self.grid_10 = Drawable(mat, sub_10, sub_idx_10, BatchType.LINES, ShaderType.UNIFORM_3D, sub_color)
        self.grid_12 = Drawable(mat, sub_12, sub_idx_12, BatchType.LINES, ShaderType.UNIFORM_3D, sub_color)
        self.x = Drawable(mat, [(-half, 0, 0), (half, 0, 0)], [(0, 1)], BatchType.LINES, ShaderType.UNIFORM_3D, x_color)
        self.y = Drawable(mat, [(0, -half, 0), (0, half, 0)], [(0, 1)], BatchType.LINES, ShaderType.UNIFORM_3D, y_color)

    @property
    def pos(self) -> Vector:
        return self.matrix_world.translation

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def draw(self, context):
        """
        Draw the grid widget
        The idea is to temporary adapt grid scale to width of viewport and unit settings
        :param context:
        :return:
        """
        if self.enabled and View.in_region(context):
            # logger.debug("%s.draw()" % self.__class__.__name__)
            grid_matrix, has_12_subs, sub_alpha = View.grid_scale(context, self.matrix_world, self.steps)

            # Assign in place
            self._display_matrix[:] = self.matrix_world @ grid_matrix
            theme = context.preferences.themes[0]
            color = (*theme.view_3d.grid[0:3], 0.2 * sub_alpha)
            self.grid.draw()
            if has_12_subs:
                self.grid_12.colors[State.NORMAL] = color
                self.grid_12.draw()
            else:
                self.grid_10.colors[State.NORMAL] = color
                self.grid_10.draw()
            self.x.draw()
            self.y.draw()


# ------------------------
# Select helper area
# ------------------------


class SelectArea:

    def __init__(self):

        self.p0 = Vector((0, 0))
        self.bounding_rect = [0, 0, 0, 0]

        color_bound = (1, 1, 1, 0.2)
        color_area = (1, 1, 1, 0.05)
        # 1 2
        # 0 3
        co = [
            (-0.5, -0.5, 0), (-0.5, 0.5, 0), (0.5, 0.5, 0), (0.5, -0.5, 0)
        ]
        bound = [(0, 1), (1, 2), (2, 3), (3, 0)]
        area = [(0, 1, 2), (2, 3, 0)]
        mat = Matrix()
        self._drawables = [
            Drawable(mat, co, bound, BatchType.LINES, ShaderType.UNIFORM_2D, color_bound),
            Drawable(mat, co, area, BatchType.TRIS, ShaderType.UNIFORM_2D, color_area)
        ]
        self.matrix_world = mat
        self.enabled = False

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def draw(self, context):
        """
        Draw the area widget
        :param context:
        :return:
        """
        if self.enabled and View.in_region(context):
            # logger.debug("%s.draw()" % self.__class__.__name__)
            for drawable in self._drawables:
                drawable.draw()

    def press(self, p0):
        self.p0[:] = View.screen_location(p0)
        self.bounding_rect = 0, 0, 0, 0
        for drawable in self._drawables:
            drawable.pixel = self.p0.copy()
            drawable.size = Vector((0, 0))

    def update(self, p1):
        pix = View.screen_location(p1)
        self._compute_bounding_rect(self.p0, pix)
        left, bottom, right, top = self.bounding_rect
        pixel = Geom3d.lerp(self.p0, pix, 0.5)
        size = Vector((right - left, top - bottom))
        for drawable in self._drawables:
            drawable.pixel[:] = pixel
            drawable.size[:] = size
        logger.info("pixel: %s  size: %s" % (pixel, size))

    def _compute_bounding_rect(self, pix0, pix1):
        """ origin (0,0) is bottom left
        :return: left, bottom, right, top
        """
        x, y = zip(*[pix0, pix1])
        self.bounding_rect = min(x), min(y), max(x), max(y)

    def _cross_area(self, coord: list) -> bool:
        """
        :param coord:
        :return: True if line cross the area
        """
        return Geom2d.line_cross_area(coord, self.bounding_rect)

    def _in_area(self, co: Vector) -> bool:
        """
        :param point: SnapItem
        :return: True if point is in the area
        """
        return Geom2d.point_in_area(co, self.bounding_rect)

    def in_area(self, helper) -> bool:
        if helper.batch_type & BatchType.LINES:
            coord = [View.screen_location(co) for co in helper.world_coords[0:2]]
            for co in coord:
                if self._in_area(co):
                    return True
            return False
            # return self._cross_area(co)
        elif helper.batch_type & BatchType.POINTS:
            co = View.screen_location(helper.world_coords[0])
            return self._in_area(co)
        return False


# ------------------------
# Mouse cursors
# ------------------------


class Cursor:

    SNAP = 1
    MOVE = 2
    ROTATE = 4
    SCALE = 8
    EDIT = 16
    TEXT = 32
    MEASURE = 64

    def __init__(self, context):
        self.matrix_world = Matrix()

        prefs = Prefs.get(context)
        size = int(prefs.cursor_size)
        theme = prefs.cursor_theme.lower()

        t = time.time()

        path = os.path.join(os.path.dirname(__file__), "cursors")
        self._images = {
            self.SNAP: Image(os.path.join(path, "%s.snap.dat" % theme), (size, size)),
            self.MOVE: Image(os.path.join(path, "%s.move.dat" % theme), (size, size)),
            self.ROTATE: Image(os.path.join(path, "%s.rotate.dat" % theme), (size, size)),
            self.SCALE: Image(os.path.join(path, "%s.scale.dat" % theme), (size, size)),
            self.EDIT: Image(os.path.join(path, "%s.edit.dat" % theme), (size, size)),
            self.TEXT: Image(os.path.join(path, "%s.text.dat" % theme), (size, size)),
            self.MEASURE: Image(os.path.join(path, "%s.measure.dat" % theme), (size, size))
        }

        logger.info("Load images %.4f" % (time.time() - t))

        self.state = self.MOVE
        self.enabled = True
        # Store location to pass to feedback
        self.pixel = Vector((0, 0))

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def update(self, context, event, state):
        self.state = state
        self.pixel = Events.mouse_pos(event)
        self._images[state].center = self.pixel

    def draw(self, context):
        if self.enabled and View.in_region(context):
            self._images[self.state].draw()


# ------------------------
# Transform feedback
# ------------------------


class ToolTip:
    """
    Define a line of feedback action, with optional icons for keys and state
    """
    __slots__ = ('_icons', '_keys', 'text', 'w', 'h')

    def __init__(self, context, keys: list, images: list, label: str, text: Text):
        """
        :param context:
        :param keys: icon key names
        :param images: icon images
        :param label:
        :param text:
        """
        self._icons = images
        # keys are icon namees
        self._keys = keys
        self.text = i18n.translate(label)
        self.w, self.h = text.size(context, self.text)
    
    @property
    def keys(self) -> int:
        return len(self._icons)
    
    def draw(self, context, pixel: tuple, left_margin: int, key_width: int, text: Text):
        x, y = pixel
        for i, key in enumerate(self._icons):
            key.bottom_left = x + i * key_width, y
            key.draw()
        text.draw(context, (x + left_margin, y), self.text)


class ToolTips:

    _tips = []

    def __init__(self, context, offset: Vector = Vector((60, 0)), size: int = 16):
        prefs = Prefs.get(context)
        color_bg = prefs.color_feedback_bg
        color_frame = prefs.color_feedback_frame
        color_header = prefs.color_tooltips_header
        color_keys = prefs.color_tooltips_keys
        self.color_text = prefs.color_feedback_text
        self.matrix_world = Matrix()
        # Size without margins
        self._offset = Vector(offset)
        self._keys = {}
        self._key_size = size
        # pos without margins
        self.pixel = Vector((0, 0))
        # Tooltip label : action
        self.header = ""
        self.action = ""
        # Feedback text
        self.text = ""
        self._header = Text(context, color=(1, 1, 1, 1))
        self._label = Text(context, color=prefs.color_feedback_text)
        # Frame
        self._frame = [
            Square(self.matrix_world, color_keys, BatchType.TRIS),    # Bg keys
            Square(self.matrix_world, color_bg, BatchType.TRIS),      # Bg labels
            Square(self.matrix_world, color_frame, BatchType.LINES),  # Frame
            Square(self.matrix_world, color_header, BatchType.TRIS),  # Bg header
            Square(self.matrix_world, color_frame, BatchType.LINES)   # Frame header
        ]
        # frame margin
        self._margin = 10
        # margin before labels: max keys width
        self._key_w = 0
        self._text_width = 0
        # space between keys and text should remain 2 * margin
        self._key_margin = 20
        # horizontal space between keys
        self._key_space = 4
        # vertical space between lines
        self._line_margin = 4
        # number of tips
        self._lines = -1
        self.enabled = False
        # Overall size
        self.w = 0
        self.h = 0
        self.height = [0, 0, 0, 0, 0]
        self.text_bottom = [0, 0, 0]
        # feedback size when alone
        self.fw = 0
        self._size = Vector((0, 0))
        self._show_tips = True

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False
    
    def _compute_size(self, context, label):
        prefs = Prefs.get(context)
        tips = len(self._tips)

        hw, hh = self._header.size(context, label)
        fw, fh = self._label.size(context, "0m")

        tw = max([tip.w for tip in self._tips])
        kw = max([
            tip.keys
            for tip in self._tips
        ]) * (self._key_size + self._key_space) + self._key_margin - self._key_space
        kh = self._key_size + self._line_margin

        # height frame / spaces (bottom to top) feedback / space / tips / space / header
        self.height[:] = [
            fh + self._margin,
            0.5 * self._margin,
            tips * kh - self._line_margin + 2 * self._margin,
            0.5 * self._margin,
            hh + 2 * self._margin
        ]

        # Overall size
        if prefs.show_tooltips:
            self.w = max(tw + kw, fw, hw) + 2 * self._margin
            self.h = sum(self.height)

        else:
            self.w = fw + 2 * self._margin
            self.h = self.height[0]

        # width of key frame
        self._key_w = kw
        # bottom left
        self.text_bottom = [
            0.5 * self._margin,
            sum(self.height[0:2]) + self._margin,
            sum(self.height[0:4]) + self._margin
        ]

    def _add(self, context, keys, label):
        # Cache keys
        path = os.path.join(os.path.dirname(__file__), "keys")

        _keys = []
        size = Vector((self._key_size, self._key_size))

        for key in keys:
            if key not in self._keys:
                self._keys[key] = Image(os.path.join(path, "%s.dat" % key), size)
            _keys.append(self._keys[key])

        tip = ToolTip(context, keys, _keys, label, self._label)
        self._tips.append(tip)

    def _replace_tips(self, context, tips):
        self.clear()
        for tip in tips:
            self._add(context, *tip)
        self._compute_size(context, "%s : %s" % (self.header, self.action))

    def replace(self, context, header: str, action: str = "", tips: list = None):
        """
        Replace action
        :param context:
        :param header: operation name
        :param action: action name
        :param tips: list of [key icon names], label
        :return:
        """
        self.header = i18n.translate(header)
        self.action = i18n.translate(action)
        self._replace_tips(context, tips)

    def replace_tips(self, context, action: str, tips: list):
        """
        Replace tips but keep header
        :param context:
        :param action:
        :param tips:
        :return:
        """
        self.action = i18n.translate(action)
        self._replace_tips(context, tips)

    def update(self, pixel: Vector):
        """
        :param pixel: bottom left location
        :return:
        """
        dx, dy = self._offset
        x, y = pixel[0: 2]
        w, h = self.w, self.h
        if w + x + dx > View.window[0]:
            x -= w + 2 * dx
        if h + y + dy > View.window[1]:
            y -= h + 2 * dy
        self.pixel[:] = x, y

    def draw(self, context):
        if not self.enabled or not View.in_region(context):
            return

        # logger.debug("%s.draw()" % self.__class__.__name__)
        prefs = Prefs.get(context)

        if self._show_tips != prefs.show_tooltips:
            self._show_tips = prefs.show_tooltips
            self._compute_size(context, "%s : %s" % (self.header, self.action))

        x, y = self.pixel + self._offset
        tx = x + self._margin
        fw, fh = self.w, self.height[0]

        if not prefs.show_tooltips:
            if self.text == "":
                return
            fw = self._label.size(context, self.text)[0] + 2 * self._margin
            self.w = fw
            self.h = fh

        # Feedback
        for frame in self._frame[1:3]:
            frame.size = fw, fh
            frame.bottom_left = x, y
            frame.draw()

        ty = y + self.text_bottom[0]
        self._label.draw(context, (tx, ty), self.text)

        if not prefs.show_tooltips:
            return

        fy = y + self.text_bottom[1] - self._margin
        fh = self.height[2]

        # bg keys
        self._frame[0].size = self._key_w, fh
        self._frame[0].bottom_left = x, fy
        # bg labels
        self._frame[1].size = fw - self._key_w, fh
        self._frame[1].bottom_left = x + self._key_w, fy
        # frame
        self._frame[2].size = fw, fh
        self._frame[2].bottom_left = x, fy

        for frame in self._frame[0:3]:
            frame.draw()

        # Tips
        ty = y + self.text_bottom[1]
        # space between keys
        spacing = self._key_size + self._key_space
        # left margin for tips
        margin_left = self._key_w
        for tip in reversed(self._tips):
            tip.draw(context, (tx, ty), margin_left, spacing, self._label)
            ty += self._key_size + self._line_margin

        # frame header
        fh = self.height[4]
        for i, frame in enumerate(self._frame[3:5]):
            frame.size = fw, fh
            frame.bottom_left = x, ty + self._margin
            frame.draw()

        ty = y + self.text_bottom[2]
        self._header.draw(context, (tx, ty), "%s : %s" % (self.header, self.action))

    def clear(self):
        self._lines = -1
        self._size[:] = (0, 0)
        self._tips.clear()


class Feedback:

    def __init__(self, context, color=None):

        if color is not None:
            color_bg = (*color[0:3], 0.03)
            color_frame = (*color[0:3], 0.5)
            color_text = color

        else:
            prefs = Prefs.get(context)
            color_bg = prefs.color_feedback_bg
            color_frame = prefs.color_feedback_frame
            color_text = prefs.color_feedback_text

        self.matrix_world = Matrix()

        self.frame = [
            Square(self.matrix_world, color_bg, BatchType.TRIS),
            Square(self.matrix_world, color_frame, BatchType.LINES)
        ]
        for line in self.frame:
            line.enabled = True

        self.text = ""
        self.label = Text(context, None, TextType.TEXT_2D | TextType.LEFT, color_text)
        self.enabled = False
        self.offset = Vector((10, 10))

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def draw(self, context, coord: Vector):
        """
        :param context:
        :param coord: Either a 2 dimension Vector or pixel location or 3d world coord
        :return:
        """
        if self.enabled and View.in_region(context):
            # logger.debug("%s.draw()" % self.__class__.__name__)
            x, y = self.label.size(context, self.text)
            # NOTE: pixel pos is bottom of text
            # so we must move up and right from margin
            margin = 10
            if len(coord) == 3:
                px, py = View.screen_location(coord)

            else:
                px, py = coord
            size = (margin + x, margin + y)
            frame_pos = (px + 0.5 * (margin + x), py + 0.5 * (margin + y))
            text_pos = (px + 0.5 * margin, py + 0.5 * margin)
            for line in self.frame:
                line.size = size
                line.pixel = frame_pos
                line.draw()
            self.label.draw(context, text_pos, self.text)


class Rotation:

    def __init__(self, context):
        self.matrix_world = Matrix()
        self.pie = [
            Pie(self.matrix_world, RED, BatchType.TRIS, None, 0.5, 1.0, ShaderType.UNIFORM_3D),
            Pie(self.matrix_world, RED, BatchType.LINES, None, 0.5, 1.0, ShaderType.UNIFORM_3D)
        ]
        self.lines = [
            Line(self.matrix_world.copy(), None, RED),
            Line(self.matrix_world.copy(), None, RED),
        ]
        self.circle = Circle(self.matrix_world, RED, BatchType.LINES, 0.55, ShaderType.UNIFORM_3D)
        self.circle.theme_axis_colors(context, 1.0)
        self.pie[0].theme_axis_colors(context, 0.2)
        self.pie[1].theme_axis_colors(context, 0.5)
        for line in self.lines:
            line.theme_axis_colors(context, 0.5)
        self.enabled = False

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def update(self, index: int = -1):
        """ Set widget matrix and angles from transform and update colors state
        :param context:
        :param index:
        """
        trs, transformable = Transform.get_active(index)

        about = Space.get(trs, transformable.o.matrix_world)

        # orient about system so Z fit with rotation axis
        self.matrix_world[:] = Constraint.rotation_plane(trs, about)
        start, delta = trs.get_angles(self.matrix_world)
        for pie in self.pie:
            pie.set_angle(start, delta)
        # Set colors according ConstraintType
        axis = ConstraintType.get_active_axis()
        if axis == ConstraintType.NONE:
            axis = ConstraintType.Z
        self.circle.state = axis
        for pie in self.pie:
            pie.state = axis
        for line in self.lines:
            line.state = axis
            line.enabled = trs.has_not(TransformType.KEYBOARD)
        p0 = self.matrix_world.translation
        p1 = Geom3d.neareast_point_plane(trs.snap_from, self.matrix_world)
        p2 = Geom3d.neareast_point_plane(trs.snap_to, self.matrix_world)
        self.lines[0].from_2_points(p0, p1)
        self.lines[1].from_2_points(p0, p2)

    def draw(self, context):
        if self.enabled and View.in_region(context):
            self.circle.draw()
            for pie in self.pie:
                pie.draw()
            for line in self.lines:
                line.draw()


class Move:

    def __init__(self, context):
        self.matrix_world = Matrix()
        self._display_matrix = Matrix()

        prefs = Prefs.get(context)

        opacity_bg = 0.01
        xy = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        yz = [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)]
        zx = [(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)]
        line = [(0, 1)]
        bound = [(0, 1), (1, 2), (2, 3)]
        surf = [(0, 1, 2), (2, 3, 0)]

        self.lines = [
            Drawable(self._display_matrix, xy[0:2], line, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, yz[0:2], line, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, zx[0:2], line, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, xy[1:4], bound, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, zx[1:4], bound, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, yz[1:4], bound, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, xy, surf, BatchType.TRIS, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, zx, surf, BatchType.TRIS, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, yz, surf, BatchType.TRIS, ShaderType.UNIFORM_3D, RED)
        ]
        theme = context.preferences.themes[0].user_interface
        self.labels = [
            #    Text(context, None, TextType.TEXT_3D | TextType.LEFT),
            Feedback(context, (*theme.axis_x, 1)),
            Feedback(context, (*theme.axis_y, 1)),
            Feedback(context, (*theme.axis_z, 1)),
            Feedback(context, (*prefs.color_feedback_text[0:3], 1))
        ]
        for line, state, opacity in zip(self.lines, [
            ConstraintType.X, ConstraintType.Y, ConstraintType.Z,
            ConstraintType.Z, ConstraintType.Y, ConstraintType.X,
            ConstraintType.Z, ConstraintType.Y, ConstraintType.X
        ], [1.0, 1.0, 1.0, 0.5, 0.5, 0.5, opacity_bg, opacity_bg, opacity_bg]):
            line.theme_axis_colors(context, opacity)
            line.state = state

        self.enabled = False

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def update(self, context, index: int = -1):
        """ Set widget matrix and angles from transform and update colors state
        :param context:
        :param index:
        """
        trs, transformable = Transform.get_active(index)

        # visible labels / lines index
        labels = {}
        lines = {0}

        if trs.has_constraint(ConstraintType.PLANE | ConstraintType.AXIS):

            self.lines[0].state = ConstraintType.X

            sx, sy, sz = transformable.feedback_move

            for label, s in zip(self.labels, [sx, sy, sz]):
                label.text = Units.to_string(context, s, "LENGTH")

            if trs.has_constraint(ConstraintType.PLANE):
                if trs.has_constraint(ConstraintType.X):
                    # plane yz
                    lines = {1, 2, 5, 8}
                    labels = {1, 2, 3}
                    sx = 1.0
                elif trs.has_constraint(ConstraintType.Y):
                    lines = {0, 2, 4, 7}
                    labels = {0, 2, 3}
                    sy = 1.0
                else:
                    lines = {0, 1, 3, 6}
                    labels = {0, 1, 3}
                    sz = 1.0

                self.labels[3].text = Units.to_string(context, abs(sx * sy * sz), "AREA")

            elif trs.has_constraint(ConstraintType.AXIS):
                if trs.has_constraint(ConstraintType.X):
                    lines = {0}
                    labels = {0}
                    sy, sz = 1.0, 1.0
                elif trs.has_constraint(ConstraintType.Y):
                    lines = {1}
                    labels = {1}
                    sx, sz = 1.0, 1.0
                else:
                    lines = {2}
                    labels = {2}
                    sx, sy = 1.0, 1.0

            about = trs.space.copy()
            about.translation = trs.snap_from
            self._display_matrix[:] = about @ Geom3d.scale_matrix(sx, sy, sz)

        else:
            self._display_matrix[:] = Geom3d.matrix_from_up_and_direction(
                trs.snap_from, trs.snap_to - trs.snap_from, Z_AXIS
            )
            self.lines[0].state = ConstraintType.NONE

        for i, line in enumerate(self.lines):
            line.enabled = i in lines

        for i, label in enumerate(self.labels):
            label.enabled = i in labels

    def draw(self, context):
        if self.enabled and View.in_region(context):
            for line in self.lines:
                line.draw()
            co = [self._display_matrix @ p for p in (X_AXIS, Y_AXIS, Z_AXIS, X_AXIS + Y_AXIS + Z_AXIS)]
            for i, label in enumerate(self.labels):
                label.draw(context, co[i])


class Scale:

    def __init__(self, context):
        self.matrix_world = Matrix()
        self._display_matrix = Matrix()
        prefs = Prefs.get(context)
        opacity_bg = 0.01
        xy = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        yz = [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)]
        zx = [(0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)]
        line = [(0, 1)]
        bound = [(0, 1), (1, 2), (2, 3)]
        surf = [(0, 1, 2), (2, 3, 0)]
        self.lines = [
            Drawable(self._display_matrix, xy[0:2], line, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, yz[0:2], line, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, zx[0:2], line, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, xy[1:4], bound, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, zx[1:4], bound, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, yz[1:4], bound, BatchType.LINES, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, xy, surf, BatchType.TRIS, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, zx, surf, BatchType.TRIS, ShaderType.UNIFORM_3D, RED),
            Drawable(self._display_matrix, yz, surf, BatchType.TRIS, ShaderType.UNIFORM_3D, RED)
        ]
        theme = context.preferences.themes[0].user_interface
        self.labels = [
            #    Text(context, None, TextType.TEXT_3D | TextType.LEFT),
            Feedback(context, (*theme.axis_x, 1)),
            Feedback(context, (*theme.axis_y, 1)),
            Feedback(context, (*theme.axis_z, 1))
        ]
        for line, state, opacity in zip(self.lines, [
            ConstraintType.X, ConstraintType.Y, ConstraintType.Z,
            ConstraintType.Z, ConstraintType.Y, ConstraintType.X,
            ConstraintType.Z, ConstraintType.Y, ConstraintType.X
        ], [1.0, 1.0, 1.0, 0.5, 0.5, 0.5, opacity_bg, opacity_bg, opacity_bg]):
            line.theme_axis_colors(context, opacity)
            line.state = state

        self.enabled = False

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def update(self, context, index: int = -1):
        """ Set widget matrix and angles from transform and update colors state
        :param context:
        :param index:
        """

        trs, transformable = Transform.get_active(index)

        # visible labels / lines index
        labels = {}
        lines = {0}

        if trs.has_constraint(ConstraintType.PLANE | ConstraintType.AXIS):
            self.labels[0].show()
            self.lines[0].state = ConstraintType.X

            about = trs.space.copy()
            sx, sy, sz = transformable.feedback_resize

            for label, s in zip(self.labels, [sx, sy, sz]):
                label.text = Units.to_string(context, s, "LENGTH")

            if trs.has_constraint(ConstraintType.PLANE):
                if trs.has_constraint(ConstraintType.X):
                    # plane yz
                    lines = {1, 2, 5, 8}
                    labels = {1, 2}
                    if sx < 0:
                        sx = -1.0
                    else:
                        sx = 1.0
                elif trs.has_constraint(ConstraintType.Y):
                    lines = {0, 2, 4, 7}
                    labels = {0, 2}
                    if sy < 0:
                        sy = -1.0
                    else:
                        sy = 1.0
                else:
                    lines = {0, 1, 3, 6}
                    labels = {0, 1}
                    if sz < 0:
                        sz = -1.0
                    else:
                        sz = 1.0

            elif trs.has_constraint(ConstraintType.AXIS):
                if trs.has_constraint(ConstraintType.X):
                    lines = {0}
                    labels = {0}
                    sy, sz = 1.0, 1.0
                elif trs.has_constraint(ConstraintType.Y):
                    lines = {1}
                    labels = {1}
                    sx, sz = 1.0, 1.0
                else:
                    lines = {2}
                    labels = {2}
                    sx, sy = 1.0, 1.0

            self._display_matrix[:] = about @ Geom3d.scale_matrix(sx, sy, sz)

        else:
            self._display_matrix[:] = Geom3d.matrix_from_up_and_direction(
                trs.snap_from, trs.snap_to - trs.snap_from, Z_AXIS
            )
            self.lines[0].state = ConstraintType.NONE

        for i, line in enumerate(self.lines):
            line.enabled = i in lines

        for i, label in enumerate(self.labels):
            label.enabled = i in labels

    def draw(self, context):
        if self.enabled and View.in_region(context):
            for line in self.lines:
                line.draw()
            co = [self._display_matrix @ (1.1 * p) for p in (X_AXIS, Y_AXIS, Z_AXIS, X_AXIS + Y_AXIS + Z_AXIS)]
            for i, label in enumerate(self.labels):
                label.draw(context, co[i])
