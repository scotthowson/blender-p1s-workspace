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

# noinspection PyUnresolvedReferences
import bmesh
from math import atan2, radians, degrees, sin, cos
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
from bpy.app import version
# noinspection PyUnresolvedReferences
from mathutils import Matrix, Vector
from .types import (
    SpaceType,
    TransformType,
    ConstraintType,
    BatchType
)
from .i18n import i18n
from .units import Units, ROTATION_ROUNDING
from .keyboard import Keyboard
from .geom import (
    View,
    Geom3d,
    MATRIX_WORLD,
    ZERO,
    X_AXIS,
    Y_AXIS,
    Z_AXIS,
    SQRT_2,
    VERY_SMALL
)
from .drawable import (
    Drawable,
    Line,
    Mesh,
    Curve,
    Cross
)
from .constraint import (
    Constraint
)
from .preferences import Prefs
from .context_override import context_override
from .bmesh_utils import BmeshUtils
logger = get_logger(__name__, 'ERROR')

CORRECT_UVS = True


class Space:
    """
    Transform space matrix
    """
    # Grid matrix for display and snap
    grid = Matrix()

    # Store user space across sessions
    _user = Matrix()

    # use for dumb transform operations
    matrix_world = Matrix()

    # Space toggle order Local World User
    order = {
        "WLU": [
            SpaceType.WORLD,
            SpaceType.LOCAL,
            SpaceType.USER
        ],
        "WUL": [
            SpaceType.WORLD,
            SpaceType.USER,
            SpaceType.LOCAL
        ],
        "LWU": [
            SpaceType.LOCAL,
            SpaceType.WORLD,
            SpaceType.USER
        ],
        "LUW": [
            SpaceType.LOCAL,
            SpaceType.USER,
            SpaceType.WORLD
        ],
        "UWL": [
            SpaceType.USER,
            SpaceType.WORLD,
            SpaceType.LOCAL
        ],
        "ULW": [
            SpaceType.USER,
            SpaceType.LOCAL,
            SpaceType.WORLD
        ]
    }

    @classmethod
    def get_user(cls) -> Matrix:
        return cls._user.copy()

    @classmethod
    def set_user(cls, space: Matrix):
        cls._user[:] = Geom3d.normalized(space)

    @classmethod
    def get(cls, trs=None, pivot: Matrix = None):
        """
        Return active transform space
        :param trs: TransformAction
        :param pivot: local object matrix world
        :return:
        """
        # Default to trs.space
        res = trs.space

        if trs.has(TransformType.INDIVIDUAL_ORIGIN):

            if pivot is not None:
                res = pivot.copy()

        elif trs.has(TransformType.SCREEN):
            z = View.vector()
            res = Geom3d.matrix_from_view(pivot.translation, z)

        return res


class TransformAction:
    """
    Store transform action in order to be able to undo
    """
    __slots__ = (
        'context',
        'transformtype',
        'snap_from', 'snap_to', 'snapitem',
        'step', 'steps',
        'constraint',
        '_space',
        'normal',
        'feedback',
        'active'
    )

    def __init__(self, context, transformtype: int, space: Matrix = MATRIX_WORLD):
        """
        :param context: blender context
        :param transformtype: TransformMode
        :param space: reference of "pivot" NORMALIZED matrix
        """
        self.context = context

        # TransformType
        self.transformtype = transformtype
        # ConstraintType
        self.constraint = 0

        # align to normal
        self.normal = Vector((0, 0, 1))

        self.snap_from = Vector()
        self.snap_to = Vector()

        # SnapItem to handle "clever" snap to intersection / perpendicular
        # depending on constraint type
        self.snapitem = None

        # "about" space : pivot
        self._space = space

        # Active state
        self.active = False

        # Copy
        self.step = 1
        self.steps = 0

        # for display
        self.feedback = "0"

    def __str__(self):
        return "TransformAction {} step:{} steps:{}".format(
            self.transformtype, self.step, self.steps
        )

    @property
    def space(self) -> Matrix:
        return self._space

    @space.setter
    def space(self, space: Matrix):
        """Set Normalized space Matrix "in place"
        :param space: Matrix.
        :return:
        """
        self._space[:] = Geom3d.normalized(space)

    def has_constraint(self, constraint: int) -> bool:
        return self.constraint & constraint > 0
        
    def has(self, transformtype: int) -> bool:
        return self.transformtype & transformtype > 0

    def has_not(self, transformtype: int) -> bool:
        return self.transformtype & transformtype == 0

    def enable(self, transformtype: int):
        self.transformtype = self.transformtype | transformtype

    def disable(self, transformtype: int):
        self.transformtype = self.transformtype & ~transformtype

    def state(self, transformtype: int, state: bool):
        if state:
            self.enable(transformtype)
        else:
            self.disable(transformtype)

    def get_angles(self, about: Matrix = MATRIX_WORLD):
        """
        :param about: Matrix, projection plane to evaluate rotation
        :return: signed angle radians in range [-pi | pi]
        """
        c = about.translation
        # project snap_from and snap_to to space
        snapitem, self.snapitem = self.snapitem, None
        p0 = Constraint.to_plane(self, self.snap_from, about)
        self.snapitem = snapitem
        p1 = Constraint.to_plane(self, self.snap_to, about)
        itm = Geom3d.matrix_inverted(about)
        x0, y0 = (itm @ p0)[0:2]
        start = atan2(y0, x0)
        delta = Geom3d.signed_angle(p0 - c, p1 - c, about.col[2].to_3d())
        return start, delta


class TransformAble:
    """
    Handle transform operation on objects
    Delta is absolute and always apply to initial state
    """

    def __init__(self, o):

        self.o = o
        self._display_type = None
        self.is_edit_mode = False
        # for steps operations matrix_step will be modified at each step
        self.matrix_step = o.matrix_world.copy()

        # keep source matrix_world for step operations
        self.matrix_save = o.matrix_world.copy()

        self.transform_matrix = Matrix()

        # NOTE:
        # When available, transform preview(s) matrix_world until confirm
        #  - no need to store any data / but require to create a preview
        #  - prevent issues with 0 scale
        #  - rely on blender's undo
        self.previews = None

        # Store children matrix world
        self.children = {}
        # Is active object
        self.active_object = True
        # store resize on multiple axis for widget
        self.feedback_resize = Vector()
        self.feedback_move = Vector()
        self.scale_flip_normal = False
        # Store a fake snap_to in space system
        self.snap_to = Vector()

    def display_as_wire(self):
        self.restore_display_type()
        if hasattr(self.o, "display_type"):
            self._display_type = self.o.display_type
            self.o.display_type = Transform.display_type

    def restore_display_type(self):
        if self._display_type is not None:
            self.o.display_type = self._display_type
            self._display_type = None

    def cancel(self):
        if self.previews is None:
            self.o.matrix_world[:] = self.matrix_save
            self.matrix_step[:] = self.matrix_save

    @staticmethod
    def _units_steps(context):
        us = context.scene.unit_settings
        # Use custom unit when set by user
        if us.length_unit == "FEET":
            step = 12
        else:
            step = 10
        return step / us.scale_length

    @staticmethod
    def signed_angle(trs: TransformAction, about: Matrix = MATRIX_WORLD) -> float:
        """
        :param trs: TransformAction
        :param about: Matrix, projection plane to evaluate rotation
        :return: signed angle radians in range [-pi | pi]
        """
        c = about.translation
        # project snap_from and snap_to to space
        snapitem, trs.snapitem = trs.snapitem, None
        p0 = Constraint.to_plane(trs, trs.snap_from, about)
        trs.snapitem = snapitem
        p1 = Constraint.to_plane(trs, trs.snap_to, about)
        return Geom3d.signed_angle(p0 - c, p1 - c, about.col[2].to_3d())

    def _rotation(self, trs: TransformAction) -> Matrix:
        """Evaluate rotation
        :param trs: TransformAction
        :return: Transform matrix
        """
        # orient about system so Z fit with rotation axis
        about = Constraint.rotation_plane(trs, trs.space)
        if trs.has(TransformType.KEYBOARD):
            # keyboard value may eval as degree
            a = Keyboard.value
            logger.debug("angle %.4f" % degrees(a))

        else:
            a = self.signed_angle(trs, about)
            if a != 0 and trs.has(TransformType.ROUND):

                # TODO: use prefs for steps size
                # prefs = Prefs.get(trs.context)

                if trs.has(TransformType.SMALL_STEPS):
                    step = 1.0
                else:
                    step = 5.0
                a = radians(step * round(degrees(a) / step, 0))

        steps = max(1, trs.steps)

        if trs.has(TransformType.COPY):
            trs.feedback = "%s( %s )  %s" % (
                i18n.translate("Array"),
                steps + 1,
                Units.to_string(trs.context, a, "ROTATION")
            )
        else:
            trs.feedback = Units.to_string(trs.context, a, "ROTATION")

        about = Space.get(trs, self.matrix_step)
        about = Constraint.rotation_plane(trs, about)

        # pre rotation
        return Geom3d.pre_transform(about, Matrix.Rotation((trs.step * a / steps), 4, "Z"))

    def _translation(self, trs: TransformAction) -> Matrix:
        """Evaluate translation
        :param trs: TransformAction
        :return: Transform matrix
        """
        # By default, trs.space is active object's matrix_world normalized
        about = trs.space
        #
        about.translation[:] = trs.snap_from
        # snap_to in trs.space
        delta = Geom3d.matrix_inverted(about) @ Constraint.apply(trs, trs.snap_to, about)
        delta_len = delta.length

        if trs.has(TransformType.KEYBOARD):

            # NOTE: for keyboard actions with axis constraints
            #        ensure that delta is not null
            if delta_len == 0 and trs.has_constraint(ConstraintType.AXIS):
                if trs.has_constraint(ConstraintType.X):
                    delta = X_AXIS
                elif trs.has_constraint(ConstraintType.Y):
                    delta = Y_AXIS
                else:
                    delta = Z_AXIS
                delta_len = 1.0

            dist = Keyboard.value

            logger.debug("dist %.4f %s" % (dist, delta.normalized()))

        else:
            dist = delta_len

        # Store feedback for widget
        self.feedback_move[:] = delta
        steps = max(1, trs.steps)

        if trs.has(TransformType.COPY):
            trs.feedback = "%s( %s )  %s" % (
                i18n.translate("Array"),
                trs.steps + 1,
                Units.to_string(trs.context, round(dist, 5), "LENGTH")
            )
        else:
            trs.feedback = Units.to_string(trs.context, round(dist, 5), "LENGTH")

        if delta_len == 0:
            # delta not normalizable .. so transform is null
            return Matrix()

        about = Space.get(trs, self.matrix_step)
        # pre-translate
        return Geom3d.normalized(
            Geom3d.pre_transform(about, Matrix.Translation((trs.step * dist / steps) * delta.normalized()))
        )

    def _scale(self, trs: TransformAction) -> Matrix:
        """Evaluate scale
        :param trs: TransformAction
        :return: Transform matrix
        """
        about = trs.space
        snap_to = Constraint.apply(trs, trs.snap_to, about)

        # temporary disable intersection computation
        snapitem = trs.snapitem
        if trs.has_constraint(ConstraintType.AXIS | ConstraintType.PLANE):
            trs.snapitem = None

        snap_from = Constraint.apply(trs, trs.snap_from, about)
        trs.snapitem = snapitem

        fac = 1.0
        s = 1.0

        if trs.has(TransformType.KEYBOARD):

            s = Keyboard.value
            _d = 1.0
            if trs.has(TransformType.ABSOLUTE):
                tx, ty, tz = s, s, s

                # Uniform scale
                if trs.has(TransformType.UNIFORM_SCALE):
                    logger.debug("TransformType.ABSOLUTE")
                    _d = (trs.space.translation - snap_from).length
                    fx, fy, fz = _d, _d, _d

                else:
                    im = Geom3d.matrix_inverted(about)
                    fx, fy, fz = im @ snap_from

                scale = []
                resize = []

                for _from, _to in zip([fx, fy, fz], [tx, ty, tz]):

                    if -VERY_SMALL < _to < VERY_SMALL or -VERY_SMALL < _from < VERY_SMALL:
                        scale.append(1.0)
                        resize.append(0)
                    else:
                        resize.append(_to)
                        s = _to / _from
                        scale.append(s if _from * _to > -VERY_SMALL else -s)
                        logger.debug("scale %.4f  _from: %.4f  _to: %.4f" % (scale[-1], _from, _to))

                self.feedback_resize[:] = resize

            # logger.debug("scale s: %.4f  _d: %.4f" % (s, _d))
            else:
                scale = [s, s, s]
                self.feedback_resize[:] = scale
        else:
            # Uniform scale
            if trs.has(TransformType.UNIFORM_SCALE):
                im = Geom3d.matrix_inverted(about)
                _fpt = im @ snap_from
                _tpt = im @ snap_to
                _from = _fpt.length
                _to = _tpt.length
                if -VERY_SMALL < _to < VERY_SMALL or -VERY_SMALL < _from < VERY_SMALL:
                    scale = [1.0, 1.0, 1.0]
                    self.feedback_resize[:] = 0, 0, 0
                else:
                    # if trs.has(TransformType.ROUND):
                    #     step = self._units_steps(trs.context)
                    #     if trs.has(TransformType.SMALL_STEPS):
                    #         step /= 1000
                    #     else:
                    #         step /= 100
                    #     _to = step * round(_to / step, 0)

                    s = _to / _from
                    scale = [s if _from * _to > -VERY_SMALL else -s for _to, _from in zip(_tpt, _fpt)]

                    if trs.has_constraint(ConstraintType.PLANE):
                        _to /= SQRT_2
                    self.feedback_resize[:] = [_to if axis > 0 else -_to for axis in _tpt]

                logger.debug("scale %.4f  _from: %.4f  _to: %.4f" % (s, _from, _to))

            else:
                # non uniform scale
                scale = []
                resize = []
                im = Geom3d.matrix_inverted(about)
                fx, fy, fz = im @ snap_from
                tx, ty, tz = im @ snap_to

                for _from, _to in zip([fx, fy, fz], [tx, ty, tz]):
                    if -VERY_SMALL < _to < VERY_SMALL or -VERY_SMALL < _from < VERY_SMALL:
                        scale.append(1.0)
                        resize.append(0)
                    else:

                        resize.append(_to)
                        scale.append(_to / _from)
                        logger.debug("scale %.4f  _from: %.4f  _to: %.4f" % (scale[-1], _from, _to))

                self.feedback_resize[:] = resize

        sx, sy, sz = fac, fac, fac

        if trs.has_constraint(ConstraintType.AXIS):
            if trs.has_constraint(ConstraintType.X):
                sx = scale[0]
            elif trs.has_constraint(ConstraintType.Y):
                sy = scale[1]
            elif trs.has_constraint(ConstraintType.Z):
                sz = scale[2]

        elif trs.has_constraint(ConstraintType.PLANE):
            if trs.has_constraint(ConstraintType.X):
                sy, sz = scale[1], scale[2]

            elif trs.has_constraint(ConstraintType.Y):
                sx, sz = scale[0], scale[2]

            elif trs.has_constraint(ConstraintType.Z):
                sx, sy = scale[0], scale[1]

        else:
            sx, sy, sz = scale

        if trs.has(TransformType.UNIFORM_SCALE):
            trs.feedback = "%s%%" % (round(100 * s, 1))

        else:
            trs.feedback = "x:%s%%  y:%s%%  z:%s%%" % (round(100 * sx, 1), round(100 * sy, 1), round(100 * sz, 1))

        self.scale_flip_normal = sx * sy * sz < 0

        # Finally we do apply about either str.space or local matrix world
        about = Space.get(trs, self.matrix_step)
        # pre-scale
        return Geom3d.pre_transform(about, Geom3d.scale_matrix(sx, sy, sz))

    def _pinhole(self, trs: TransformAction) -> Matrix:
        """Evaluate pinhole orientation of x axis, keeping z as vertical as possible, and y strictly horizontal
        :param trs: TransformAction
        :return: Transform Matrix
        """
        about = trs.space
        snap_to = Constraint.apply(trs, trs.snap_to, about)
        itm = Geom3d.matrix_inverted(about)
        if trs.has(TransformType.KEYBOARD):
            # keyboard value may eval as degree
            a = Keyboard.value
            logger.debug("angle %.4f" % degrees(a))
            direction = Vector((sin(a), cos(a), 0))
        else:
            direction = itm  @ snap_to

        about = Space.get(trs, self.matrix_step)
        return Geom3d.pre_transform(about, Geom3d.safe_matrix(ZERO, direction.normalized(), Z_AXIS))

    def _final(self, trs: TransformAction) -> Matrix:
        """ Apply final transform to step based operations using matrix_step in steps.
        :param trs:
        :return: delta Matrix
        """
        if self.is_edit_mode and hasattr(self.o, "data"):
            # Geom3d.debug(self.matrix_step, "_final() matrix_step")
            # In edit mode, rely on delta between matrix_save and matrix_step
            return Geom3d.normalized(self.matrix_step @ Geom3d.matrix_inverted(self.matrix_save))
        else:
            # apply use _delta @ matrix_step, matrix_step is the final transform, delta is a world matrix
            return MATRIX_WORLD

    def transform(self, target, trs: TransformAction):
        """
        Transform object
        :param target: either object or preview with matrix_world property
        :param trs: TransformAction
        :return:
        """
        if trs.has(TransformType.MOVE):
            self.move(target, trs)

        elif trs.has(TransformType.ROTATE):
            self.rotate(target, trs)

        elif trs.has(TransformType.SCALE):
            self.scale(target, trs)

        elif trs.has(TransformType.PINHOLE):
            self.pinhole(target, trs)

        elif trs.has(TransformType.FINAL):
            self.final(target, trs)

    def transform_data(self, target, trs: TransformAction, delta: Matrix):
        pass

    def store_children(self, target, trs: TransformAction):
        """
        Store children locations
        :param target:
        :param trs:
        :return:
        """
        # NOTE: for scale operations we do store any time as children will be scaled too

        if hasattr(target, 'children') and (
                trs.has(TransformType.SKIP_CHILDREN) or trs.has(TransformType.SCALE)
        ):
            self.children[target] = {c: c.matrix_world.copy() for c in target.children}
        else:
            self.children[target] = {}

    def restore_children(self, target):
        """
        Reset children locations
        :return:
        """
        for c, matrix_world in self.children[target].items():
            c.matrix_world[:] = matrix_world
        del self.children[target]

    def apply(self, target, trs: TransformAction, delta: Matrix, location_only: bool = False):
        """
        Apply the transform delta to target
        :param target:
        :param trs:
        :param delta:
        :param location_only:
        :return:
        """
        if target is None:
            return
        # keep a copy of children matrix_world
        self.store_children(target, trs)

        if location_only:
            target.matrix_world.translation[:] = delta @ self.matrix_step.translation
            _delta = delta
        else:

            if trs.has(TransformType.ALIGN_TO_NORMAL):
                _rot = Geom3d.matrix_as_rotation(
                    Geom3d.matrix_inverted(trs.space)
                )
                _loc = trs.space.copy()
                _loc.translation[:] = trs.snap_from
                _normal = _rot @ trs.normal
                # follow the slope
                if Geom3d.close_enough(_normal, Z_AXIS, VERY_SMALL):
                    _guide = _normal.cross(Y_AXIS)
                else:
                    _guide = _normal.cross(-Z_AXIS)
                _delta = delta @ Geom3d.pre_transform(
                    _loc,
                    Geom3d.safe_matrix(ZERO, _normal, _guide, "Z", "X")
                )

            else:
                _delta = delta

            if trs.has(TransformType.DATA_ORIGIN):

                if hasattr(target, "data"):
                    self.transform_data(target, trs, Geom3d.matrix_inverted(_delta))
                    target.matrix_world[:] = _delta @ self.matrix_step
            else:
                target.matrix_world[:] = _delta @ self.matrix_step

            self.fix_rotation(target)

        # Store transform matrix for external use
        # This is a world absolute transform
        self.transform_matrix[:] = _delta

        self.restore_children(target)

    @staticmethod
    def fix_rotation(target):

        # This is really dirty HACK as it actually does rotate object(s)
        # from small amount of max ~1e-5°, only to fix rounding issue in blender angle display
        # The most significant side effect is to limit angle step to: 1 / 10000°.
        #
        # Source of small rotations IS a precision issue :
        # tm = C.object.matrix_world
        # rm = Matrix.Rotation(radians(45), 4, "Z")
        # C.object.matrix_world = tm @ rm @  rm.inverted() @ tm.inverted()
        # C.object.euler_rotation.z : 1.8848643534852272e-08 -> 0.000001d

        if hasattr(target, "rotation_euler"):
            for i, axis in enumerate(target.rotation_euler):
                target.rotation_euler[i] = radians(round(degrees(axis), ROTATION_ROUNDING))

    def move(self, target, trs: TransformAction):
        raise NotImplementedError

    def pinhole(self, target, trs: TransformAction):
        raise NotImplementedError

    def rotate(self, target, trs: TransformAction):
        raise NotImplementedError

    def scale(self, target, trs: TransformAction):
        raise NotImplementedError

    def final(self, target, trs: TransformAction):
        raise NotImplementedError

    def __del__(self):
        if self.previews is not None:
            for drawable in reversed(self.previews):
                del drawable
            self.previews.clear()


class TransformableHandle(TransformAble):

    def __init__(self, o):
        """
        :param o: Handle
        """
        TransformAble.__init__(self, o)

    def move(self, target, trs: TransformAction):
        target.pos = self._translation(trs) @ self.matrix_step.translation
        target.update_target()

    def rotate(self, target, trs: TransformAction):
        pass
        # Fake rotation using projection on user space
        # space = Space.get(trs, target.space)
        # p0 = Geom3d.neareast_point_plane(trs.snap_from, space)
        # p1 = Geom3d.neareast_point_plane(trs.snap_to, space)
        # target.pos = self.matrix_step.translation + p1 - p0
        # target.update_target()

    def scale(self, target, trs: TransformAction):
        pass

    def pinhole(self, target, trs: TransformAction):
        pass

    def final(self, target, trs: TransformAction):
        pass


class TransformableObject(TransformAble):

    def __init__(self, context, o, previews: list = None, storage=None):
        """
        :param context:
        :param o: any object with matrix_world property
        :param previews: list of gl previews
        :param storage: A class with a add() method to store copy
        """
        self._storage = storage
        prefs = Prefs.get(context)
        color = prefs.color_preview
        TransformAble.__init__(self, o)

        self.active_object = o == context.active_object
        
        if previews is None:
            # exclude widgets and drawables
            if not hasattr(o, "enabled"):
                self.previews = [
                    Cross(o.matrix_world.copy(), color, 0.707 * prefs.handle_size, 2 * prefs.line_width)
                ]
        else:
            self.previews = previews

    @staticmethod
    def get_links(o, trs: TransformAction):
        """ 2/10è sec for 10k objects
        :param o:
        :param trs:
        :return: not selected linked objects
        """
        d = o.data
        name = o.name
        return [
            instance for instance in trs.context.scene.objects
            if d == instance.data and name != instance.name and not instance.select_get()
        ]

    @staticmethod
    def _clean_datablock(o, d):
        if d and d.users == 1:
            getattr(bpy.data, o.type.lower()).remove(d)

    def _sub_duplicate(self, target, trs: TransformAction):
        """ Duplicate blender object
        :param target:
        :param trs:
        :return:
        """

        # revert from wireframe display
        self.restore_display_type()

        new_o = target.copy()

        if hasattr(target, "data") and trs.has_not(TransformType.LINKED_COPY):
            # in move mode we may create instances
            new_o.data = target.data.copy()
            # self._clean_datablock(new_o, d)

        if hasattr(target, "users_collection"):
            # a blender object linked to scene
            for coll in target.users_collection:
                if new_o.name not in coll:
                    coll.objects.link(new_o)

        if self._storage is not None:
            self._storage.add(new_o)

        return new_o

    def _duplicate_hierarchy(self, target, trs: TransformAction):
        """ Recursively duplicate hierarchy
        :param target:
        :param trs:
        :return:
        """

        p = self._sub_duplicate(target, trs)

        if hasattr(target, "children") and trs.has_not(TransformType.SKIP_CHILDREN):
            for child in target.children:
                c = self._duplicate_hierarchy(child, trs)
                c.parent = p
                c.matrix_local[:] = child.matrix_local
                # keep parent inverse as objects are not supposed to move while duplicating
                c.matrix_parent_inverse[:] = child.matrix_parent_inverse

        return p
        # return None

    def _duplicate_object(self, target, trs: TransformAction):

        if target is None or not hasattr(target, "copy"):
            return None

        # Skip children of selected parent. (parent will copy whole hierarchy)
        if hasattr(target, "parent") and target.parent is not None and target.parent.select_get():
            return None

        p = self._duplicate_hierarchy(target, trs)
        # if target has parent, keep copy with same parent
        if p is not None and hasattr(target, "parent") and target.parent is not None:
            p.parent = target.parent
            p.matrix_local[:] = target.matrix_local
            # keep parent inverse as objects are not supposed to move while duplicating
            p.matrix_parent_inverse[:] = target.matrix_parent_inverse
        return p

    def move(self, target, trs: TransformAction):
        """ Move operation
        Move only location unless Align to normal is enabled
        TODO: enable this through set states instead !
        :param target:
        :param trs:
        :return:
        """
        # handle parent only
        if trs.has(TransformType.COPY) and target == self.o:
            for step in range(1, trs.steps + 1):
                trs.step = step
                dup = self._duplicate_object(target, trs)
                self.apply(dup, trs, self._translation(trs), trs.has_not(TransformType.ALIGN_TO_NORMAL))
        else:
            self.apply(target, trs, self._translation(trs), trs.has_not(TransformType.ALIGN_TO_NORMAL))

    def rotate(self, target, trs: TransformAction):
        # handle parent only
        location_only = trs.has(TransformType.LOCATION_ONLY)
        if trs.has(TransformType.COPY) and target == self.o:
            for step in range(1, trs.steps + 1):
                trs.step = step
                dup = self._duplicate_object(target, trs)
                self.apply(dup, trs, self._rotation(trs), location_only)
        else:
            rot = self._rotation(trs)
            self.apply(target, trs, rot, location_only)

    def scale(self, target, trs: TransformAction):
        self.apply(target, trs, self._scale(trs), trs.has(TransformType.LOCATION_ONLY))
        if hasattr(target, "children") and trs.has_not(TransformType.SKIP_CHILDREN):
            matrix_step = self.matrix_step.copy()
            for c in target.children:
                self.matrix_step[:] = c.matrix_world
                # TODO: handle different kind of objects !!
                if hasattr(c, "type") and c.type == target.type:
                    self.scale(c, trs)

            self.matrix_step[:] = matrix_step

    def pinhole(self, target, trs: TransformAction):
        self.apply(target, trs, self._pinhole(trs), trs.has(TransformType.LOCATION_ONLY))

    def final(self, target, trs: TransformAction):
        self.apply(target, trs, self._final(trs), trs.has(TransformType.LOCATION_ONLY))


class TransformableHelper(TransformableObject):
    """
    CAD Transform helper
    """

    def __init__(self, context, o, storage):
        prefs = Prefs.get(context)
        color = prefs.color_preview
        preview = None
        previews = None

        if o.batch_type == BatchType.POINTS:
            preview = Cross(o.matrix_world.copy(), color)

        elif o.batch_type == BatchType.LINES:
            preview = Line(o.matrix_world.copy(), None, color)

        elif o.batch_type == BatchType.TRIS:
            preview = Drawable(
                o.matrix_world.copy(), o.co, o.indices, o.batch_type, color=(*color[0:3], 0.05)
            )
            # preview.indices = o.indices

        if preview is None:
            logger.error("TransformableHelper.__init__() preview is none ..")
        else:
            previews = [
                preview
            ]

        TransformableObject.__init__(self, context, o, previews, storage)


class TransformableImage(TransformableObject):
    """
    Blender's image helper
    """

    def __init__(self, context, o):
        TransformableObject.__init__(self, context, o, [])
        self.previews = None

    def scale(self, target, trs: TransformAction):
        """Scale mesh object
        :param target:
        :param trs:
        :return:
        """
        delta = self._scale(trs)

        # NOTE:
        # #!?**!
        # For some reasons blender does not allow to scale matrix_world about not aligned arbitrary axis,
        # witch by the way does work as expected in openGl / bmesh, so i do transform data instead.
        # Maybe there is a performance reason to do so.

        if trs.has_not(TransformType.LOCATION_ONLY):
            # Special case : axis are not aligned with object's one, apply to mesh
            # provide support for both OBJECT and EDIT mode

            # Compute translation for pivot, relative to object's matrix_world
            translation_pivot = Geom3d.matrix_inverted(self.matrix_step) @ delta @ self.matrix_step.translation

            # transform location about pivot
            self.apply(target, trs, delta, False)
            self.store_children(target, trs)
            target.matrix_world.translation[:] = self.matrix_step @ translation_pivot
            self.restore_children(target)

        else:
            self.apply(target, trs, delta, True)


class TransformDataHandler(TransformableObject):
    """
    Blender's object with data properties
    In order to be able to mix objects type in selection hierarchy
    """

    def __init__(self, context, o, previews, is_instance):
        TransformableObject.__init__(self, context, o, previews)
        self.is_instance = is_instance

    @staticmethod
    def transform_mesh(target, trs: TransformAction, delta: Matrix, flip_normal: bool = False, projection=None):
        """
        Rely on bmesh to apply non axis aligned scale right to object vertices
        NOTE: prevent precision issue with object matrix_world pivot manipulations
              support both OBJECT and EDIT modes
        :param trs: TransformAction
        :param target:
        :param delta:
        :param flip_normal:
        :param projection:
        :return:
        """
        if target.mode == "EDIT":
            bm = bmesh.from_edit_mesh(target.data)

        else:
            bm = bmesh.new(use_operators=True)
            bm.from_mesh(target.data)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        if target.mode == "EDIT":
            verts = [v for v in bm.verts if v.select]
        else:
            verts = bm.verts[:]

        do_correct_uvs = trs is not None and trs.context.scene.tool_settings.use_transform_correct_face_attributes
        src = bm

        if do_correct_uvs:
            src = bm.copy()

        # iterate over deltas for each vertex for project mode
        if projection is not None:
            #
            space = target.matrix_world
            snap_from = trs.snap_from.copy()
            for vert in verts:
                trs.snap_from[:] = space @ vert.co
                _delta = projection(trs)
                bmesh.ops.transform(
                    bm,
                    matrix=_delta,
                    space=space,
                    verts=[vert],
                    use_shapekey=False
                )
            trs.snap_from[:] = snap_from

        else:
            bmesh.ops.transform(
                bm,
                matrix=delta,
                space=target.matrix_world,
                verts=verts,
                use_shapekey=False
            )

        if do_correct_uvs:
            BmeshUtils.correct_face_attributes(src, bm)
            src.free()

        if flip_normal:
            # when one scale axis is negative, we must flip normals
            if target.mode == "EDIT":
                for face in bm.faces:
                    if face.select:
                        face.normal_flip()
            else:
                for face in bm.faces:
                    face.normal_flip()

        if trs is not None and trs.context.scene.tool_settings.use_mesh_automerge:
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=trs.context.scene.tool_settings.double_threshold)

        if target.mode == "EDIT":
            bmesh.update_edit_mesh(target.data, loop_triangles=True, destructive=False)
        else:
            bm.to_mesh(target.data)
            bm.free()

    @staticmethod
    def project_curve(matrix_world, inverted, delta, trs, co, projection):
        if projection is None:
            return delta @ co
        trs.snap_from[:] = matrix_world @ co
        return inverted @ projection(trs) @ matrix_world @ co

    def transform_curve(self, target, trs: TransformAction, delta: Matrix, flip_normal: bool = False, projection=None):
        """ Transform vertices of curve
        :param trs: TransformAction
        :param target:
        :param delta:
        :param flip_normal:
        :param projection:
        :return:
        """
        inverted = Geom3d.matrix_inverted(target.matrix_world)
        snap_from = trs.snap_from.copy()
        matrix_world = target.matrix_world
        tm = inverted @ delta @ matrix_world
        object_mode = target.mode == "OBJECT"
        for spline in target.data.splines:
            if spline.type in {'POLY', 'NURBS'}:
                for p in spline.points:
                    if p.select or object_mode:
                        p.co = self.project_curve(matrix_world, inverted, tm, trs, p.co, projection)
            elif spline.type == "BEZIER":
                for p in spline.bezier_points:
                    if p.select_control_point or object_mode:
                        p.co = self.project_curve(matrix_world, inverted, tm, trs, p.co, projection)
                    if p.select_left_handle or object_mode:
                        p.handle_left = self.project_curve(matrix_world, inverted, tm, trs, p.handle_left, projection)
                    if p.select_right_handle or object_mode:
                        p.handle_right = self.project_curve(matrix_world, inverted, tm, trs, p.handle_right, projection)
        trs.snap_from[:] = snap_from

    def transform_data(self, target, trs: TransformAction, delta: Matrix, flip_normal: bool = False, projection=None):
        if self.is_instance or not (hasattr(target, "type") and hasattr(target, "data")):
            return
        if target.type == "MESH":
            self.transform_mesh(target, trs, delta, flip_normal, projection)
        elif target.type == "CURVE":
            self.transform_curve(target, trs, delta, flip_normal, projection)

    def _transform(self, target, trs: TransformAction, delta: Matrix, projection=None):
        """ Handle EDIT and OBJECT mode transformations
        :param target:
        :param trs:
        :param delta:
        :return:
        """
        if self.is_edit_mode and hasattr(target, "data"):
            self.transform_data(target, trs, delta, self.scale_flip_normal, projection)
        else:
            self.apply(target, trs, delta, trs.has(TransformType.LOCATION_ONLY))

    def _duplicate(self, o, trs):
        """
        :param o:
        :param trs:
        :return:
        """
        if self.is_edit_mode and hasattr(o, "type") and o.type == "MESH":
            # Create a copy of selected items into separated object
            bm = bmesh.from_edit_mesh(o.data)
            new_bm = BmeshUtils.ops_duplicate(bm)
            bm.free()
            me = bpy.data.meshes.new(o.name)
            new_bm.to_mesh(me)
            new_bm.free()
            new_o = bpy.data.objects.new(o.name, me)
            new_o.matrix_world[:] = o.matrix_world
            return new_o
        else:
            return self._duplicate_object(o, trs)

    def move(self, target, trs: TransformAction):
        if trs.has(TransformType.COPY) and hasattr(target, "data"):
            dups = []
            for step in range(1, trs.steps + 1):
                trs.step = step
                dup = self._duplicate(target, trs)
                if dup is not None:
                    self._transform(dup, trs, self._translation(trs))
                    dups.append(dup)

            if self.is_edit_mode and target.type == "MESH" and len(dups) > 1:
                dups.append(target)
                with context_override(trs.context, target, dups, mode="OBJECT") as ctx:
                    if version[0] > 3:
                        with trs.context.temp_override(**ctx):
                            bpy.ops.object.join()
                    else:
                        bpy.ops.object.join(ctx)

        else:
            if trs.has(TransformType.PROJECTION):
                self._transform(target, trs, self._translation(trs), self._translation)
            else:
                self._transform(target, trs, self._translation(trs))

    def rotate(self, target, trs: TransformAction):
        if trs.has(TransformType.COPY) and hasattr(target, "data"):
            dups = []
            for step in range(1, trs.steps + 1):
                trs.step = step
                dup = self._duplicate(target, trs)
                if dup is not None:
                    self._transform(dup, trs, self._rotation(trs))
                    dups.append(dup)

            if target.type == "MESH" and self.is_edit_mode and len(dups) > 1:
                dups.append(target)
                # Override context to switch to OBJECT mode temporary
                with context_override(trs.context, target, dups, mode="OBJECT") as ctx:
                    if version[0] > 3:
                        with trs.context.temp_override(**ctx):
                            bpy.ops.object.join()
                    else:
                        bpy.ops.object.join(ctx)

        else:

            self._transform(target, trs, self._rotation(trs))

    def scale(self, target, trs: TransformAction):
        """Scale mesh object
        :param target:
        :param trs:
        :return:
        """
        delta = self._scale(trs)

        # NOTE:
        # #!?**!
        # For some reasons blender does not allow to scale matrix_world about not aligned arbitrary axis,
        # witch by the way does work as expected in openGl / bmesh, so i do transform data instead.
        # Maybe there is a performance reason to do so.

        if hasattr(target, "data") and trs.has_not(TransformType.LOCATION_ONLY):
            # Special case : axis are not aligned with object's one, apply to mesh
            # provide support for both OBJECT and EDIT mode
            if self.is_edit_mode:
                self.transform_data(target, trs, delta, self.scale_flip_normal)

            else:
                # Compute translation for pivot, relative to object's matrix_world
                translation_pivot = Geom3d.matrix_inverted(self.matrix_step) @ delta @ self.matrix_step.translation
                # Compute translation for data to compensate pivot translation
                translation_data = Geom3d.pre_transform(self.matrix_step, Matrix.Translation(-translation_pivot))

                # transform data about target matrix
                self.transform_data(target, trs, translation_data @ delta, self.scale_flip_normal)

                # transform location about pivot
                self.store_children(target, trs)
                target.matrix_world.translation[:] = self.matrix_step @ translation_pivot
                self.fix_rotation(target)
                self.restore_children(target)

                # apply delta to not selected as linked data has been transformed too
                for link in self.get_links(target, trs):
                    self.store_children(link, trs)
                    link.matrix_world.translation[:] = link.matrix_world @ translation_pivot
                    self.fix_rotation(link)
                    self.restore_children(link)

        else:
            # rely on regular object's matrix transform for preview
            self._transform(target, trs, delta)

        if hasattr(target, "children") and trs.has_not(TransformType.SKIP_CHILDREN):
            matrix_step = self.matrix_step.copy()
            for c in target.children:
                self.matrix_step[:] = c.matrix_world.copy()
                if hasattr(c, "type") and c.type == target.type:
                    self.scale(c, trs)
            self.matrix_step[:] = matrix_step

    def pinhole(self, target, trs: TransformAction):
        self._transform(target, trs, self._pinhole(trs))

    def final(self, target, trs: TransformAction):
        self._transform(target, trs, self._final(trs))


class TransformableMesh(TransformDataHandler):

    def __init__(self, context, o, is_instance: bool = False):

        prefs = Prefs.get(context)
        color = prefs.color_preview

        is_edit_mode = o.mode == "EDIT"

        if is_edit_mode:
            previews = [
                Mesh(context, o, color, BatchType.POINTS),
                Mesh(context, o, color, BatchType.LINES),
                Mesh(context, o, (*color[0:3], 0.1 * color[3]), BatchType.TRIS)
            ]
        else:
            previews = [
                Mesh(context, o, color, BatchType.LINES),
                Mesh(context, o, (*color[0:3], 0.1 * color[3]), BatchType.TRIS)
            ]
        TransformDataHandler.__init__(self, context, o, previews, is_instance)
        self.is_edit_mode = is_edit_mode

    def reset_preview(self, trs: TransformAction):

        # TODO: limit by number of vertex as it is damn slow : ~1 sec / 250k vertex

        if self.is_edit_mode or trs.has(TransformType.SCALE):
            prefs = Prefs.get(trs.context)
            color = prefs.color_preview

            for i in range(len(self.previews) - 1, 0, -1):
                del self.previews[i]

            self.previews.clear()

            if self.is_edit_mode:
                self.previews.append(Mesh(trs.context, self.o, color, BatchType.POINTS))

            self.previews.extend([
                Mesh(trs.context, self.o, color, BatchType.LINES),
                Mesh(trs.context, self.o, (*color[0:3], 0.1 * color[3]), BatchType.TRIS)
            ])

        else:
            for preview in self.previews:
                preview.matrix_world[:] = self.matrix_step


class TransformableCurve(TransformDataHandler):

    def __init__(self, context, o, is_instance: bool = None, previews: list = None):
        prefs = Prefs.get(context)
        color = prefs.color_preview
        if previews is None:
            previews = [
                Curve(context, o, color)
            ]
        TransformDataHandler.__init__(self, context, o, previews, is_instance)
        self.is_edit_mode = o.mode == "EDIT"

    def reset_preview(self, trs: TransformAction):

        if self.is_edit_mode or trs.has(TransformType.SCALE):
            prefs = Prefs.get(trs.context)
            color = prefs.color_preview

            del self.previews[0]

            self.previews = [
                Curve(trs.context, self.o, color)
            ]
        else:
            for preview in self.previews:
                preview.matrix_world[:] = self.matrix_step


class TransformableGreasePencil(TransformableObject):
    """
    TODO: implementation
    """
    def __init__(self, context, o):
        self.is_edit_mode = o.mode == "EDIT_GPENCIL"
        previews = None
        TransformableObject.__init__(self, context, o, previews)

    def _transform(self, target, trs: TransformAction, delta: Matrix):
        if self.is_edit_mode:
            # TODO: implementation
            # tm = target.matrix_world.inverted() @ delta
            pass
        else:
            # handle parent only and pivot
            location_only = trs.has(TransformType.LOCATION_ONLY)
            self.apply(target, trs, delta, location_only)

    def move(self, target, trs: TransformAction):
        delta = self._translation(trs)
        self._transform(target, trs, delta)

    def rotate(self, target, trs: TransformAction):
        delta = self._rotation(trs)
        self._transform(target, trs, delta)

    def scale(self, target, trs: TransformAction):
        delta = self._scale(trs)
        self._transform(target, trs, delta)


class Transformation:
    """
    Handle multiple transform operation undo stack
    Must create instances as we may use more than one at any time
    to use  "handles / widgets manipulations" while moving objects
    """
    def __init__(
        self, context, selection: list, mode: int = TransformType.NONE, space: Matrix = MATRIX_WORLD, storage=None
    ):
        """
        Create Transformable from selection
        :param selection: any object with a matrix_world property
        :param mode: TransformType
        :param storage: A class to store copy with .add() method
        :return:
        """
        self.mode = mode
        # current action for cancel
        self._action = TransformAction(context, mode, space)
        # store action for undo
        self._actions = []
        # target objects
        self._transformables = []

        if len(selection) == 0:
            # allow to rely on widgets to measure
            transformable = TransformableObject(context, Space)
            self._transformables.append(transformable)

        # identify instances
        is_instance = set()

        # add non selected object's instances to selection
        for o in selection:

            transformable = None
            if hasattr(o, "type"):

                if o.type == "MESH":
                    transformable = TransformableMesh(context, o, o.data in is_instance)
                    is_instance.add(o.data)

                elif o.type == "CURVE":
                    transformable = TransformableCurve(context, o, o.data in is_instance)
                    is_instance.add(o.data)

                elif o.type == "GPENCIL":
                    transformable = TransformableGreasePencil(context, o)

                elif o.type == "EMPTY" and hasattr(o, "empty_display_type") and o.empty_display_type == 'IMAGE':
                    # Reference Image
                    transformable = TransformableImage(context, o)

                else:
                    # Any other blender's object
                    transformable = TransformableObject(context, o)

            elif hasattr(o, 'action'):
                # Handles
                transformable = TransformableHandle(o)

            elif hasattr(o, 'offscreen_batch'):
                # Snap helpers
                transformable = TransformableHelper(context, o, storage)

            elif hasattr(o, 'matrix_world'):
                # Anything else without type attribute
                transformable = TransformableObject(context, o)

            if transformable is not None:

                self._transformables.append(transformable)

    def create(self, context, space, transformtype):
        self._action = TransformAction(context, transformtype, space)

    def cancel(self):
        for transformable in self._transformables:
            transformable.cancel()

    def get_active(self):
        """
        :return: active TransformAction, TransformAble of active object or last one
        """
        for transformable in self._transformables:
            if transformable.active_object:
                return self._action, transformable
        return self._action, self._transformables[-1]

    def get_transformables(self):
        return self._transformables

    def get_action(self):
        """
        :return: active TransformAction or None
        """
        return self._action

    def draw(self):
        trs = self._action
        for transformable in self._transformables:
            if transformable.previews is not None:
                if trs.has(TransformType.COPY):
                    for step in range(1, trs.steps + 1):
                        trs.step = step
                        for drawable in transformable.previews:
                            transformable.transform(drawable, trs)
                            drawable.draw()
                else:
                    for drawable in transformable.previews:
                        # re-use same previews on instances
                        if trs.has(TransformType.SCALE):
                            transformable.transform(drawable, trs)
                        drawable.draw()

    def update(self, trs):
        for transformable in self._transformables:
            if transformable.previews is not None:
                if trs.has_not(TransformType.COPY) and trs.has_not(TransformType.SCALE):
                    for drawable in transformable.previews:
                        transformable.transform(drawable, trs)

            else:
                transformable.transform(transformable.o, trs)

    def apply_final(self) -> bool:
        """ Apply matrix_step to objects on APPLY_STEP operations
        :return: True when transform occurs on blender object (object with "type" property)
        """
        res = False
        trs = self._action
        trs = TransformAction(trs.context, TransformType.FINAL, MATRIX_WORLD)
        for transformable in self._transformables:
            res = res or hasattr(transformable.o, "type")
            transformable.transform(transformable.o, trs)
        return res

    def confirm(self, trs, reset_preview: bool = False) -> bool:
        """
        :param trs: TransformAction
        :param reset_preview: Update preview when transform occurs in edit mode
        :return: True when transform occurs on blender object (object with "type" property)
        """
        res = False
        if trs.has(TransformType.APPLY_STEP):
            # store transform to matrix-save
            self.update(trs)
            for transformable in self._transformables:
                if transformable.previews is not None:
                    transformable.matrix_step[:] = transformable.previews[0].matrix_world

                else:
                    transformable.matrix_step[:] = transformable.o.matrix_world

                if reset_preview and hasattr(transformable, "reset_preview"):
                    transformable.reset_preview(trs)

        else:

            for transformable in self._transformables:
                res = res or hasattr(transformable.o, "type")
                transformable.transform(transformable.o, trs)
                transformable.matrix_step[:] = transformable.o.matrix_world
                if reset_preview and hasattr(transformable, "reset_preview"):
                    transformable.reset_preview(trs)

        # store action for undo
        self._actions.append(trs)
        # create a new transform action
        self.create(trs.context, trs.space, trs.transformtype)
        return res

    def exit(self):
        """
        Cleanup stored data
        :return:
        """
        self._transformables.clear()
        self._actions.clear()
        self._action = None


class Transform:

    _stack = []

    # Display on screen
    _draw_index = 0
    enabled = False

    # An object has been transformed
    done = False

    # Store transform matrix
    matrix = Matrix()
    # Store absolute world location
    pos = Vector()
    # Temporary display type
    display_type = 'WIRE'

    @classmethod
    def get_active(cls, index: int = -1) -> tuple:
        """
        :return: active (trs: TransformAction, transformable : TransformAble)
        """
        if not cls.has_action():
            logger.debug("get_active() not found")
            return None, None
        return cls._stack[index].get_active()

    @classmethod
    def get_action(cls, index: int = -1):
        """
        :return: active TransformAction or none
        """
        if not cls.has_action():
            logger.debug("get_action() not found")
            return None
        return cls._stack[index].get_action()

    @classmethod
    def has_action(cls):
        return len(cls._stack) > 0

    @classmethod
    def get_transformables(cls):
        return cls._stack[-1].get_transformables()

    @classmethod
    def get_mode(cls):
        """
        :return: TransformType of active action
        """
        return cls._stack[-1].mode

    @classmethod
    def draw(cls, context):
        if cls.enabled and View.in_region(context):
            cls._stack[cls._draw_index].draw()

    @classmethod
    def show(cls, index: int = 0):
        """
        :param index: index of item of stack to draw, 0 is main transform -1 is push action
        :return:
        """
        cls._draw_index = index
        cls.enabled = True

    @classmethod
    def hide(cls):
        cls._draw_index = 0
        cls.enabled = False

    @classmethod
    def push(cls, context, selection: list, mode: int = TransformType.NONE, space: Matrix = MATRIX_WORLD, storage=None):
        """
        Add a transformation for selection
        :param context:
        :param selection:
        :param mode:TransformType
        :param space: Space pivot
        :param storage: optional, a class to store copy with .add() method
        :return:
        """
        logger.info("Transform.push()")

        cls._stack.append(
            Transformation(context, selection, mode, space, storage)
        )

    @classmethod
    def cancel(cls):
        cls._stack[-1].cancel()

    @classmethod
    def make_first_object_active(cls):
        """
        Make first transformable of list active one
        :return:
        """
        cls.get_transformables()[0].active_object = True

    @classmethod
    def pop(cls, index: int = -1):
        """
        Remove last transformation from the stack
        :return:
        """
        logger.info("Transform.pop()")
        cls._stack.pop(index)
        return cls.get_action()

    # @classmethod
    # def undo(cls):
    #     trs = cls.get_action()
    #     trs.active = False
    #     cls._stack[-1].undo()

    # @classmethod
    # def cancel(cls, index: int = -1):
    #     trs = cls.get_action(index)
    #     trs.active = True
    #     # cls._stack[-1].cancel(trs)

    @classmethod
    def store_transform(cls, trs: TransformAction, transformable, use_object: bool = False):

        if not use_object and transformable.previews:
            target = transformable.previews[0]
        else:
            target = transformable.o
        # Store absolute world location
        cls.pos[:] = target.matrix_world.translation
        # Store absolute world transform matrix
        cls.matrix[:] = transformable.transform_matrix

    @classmethod
    def start(cls, context, event, snap_from: Vector, snapitem=None):
        """
        :param context:
        :param event:
        :param snap_from:
        :param snapitem:
        :return:
        """
        trs, transformable = cls.get_active()
        trs.snap_from[:] = snap_from
        trs.snap_to[:] = snap_from
        cls.set_normal(trs, snapitem)
        # Ensure preview is synchro when restarting action
        cls._stack[-1].update(trs)

        for t in cls.get_transformables():
            t.display_as_wire()

        # Absolute scale is to set only at startup, will still be available using a unit on keyboard
        trs.state(TransformType.ABSOLUTE, context.window_manager.slct.absolute_scale)
        cls.set_states(context, event, trs)
        trs.active = True
        cls.store_transform(trs, transformable)

    @classmethod
    def update_display_type(cls, display_type):
        cls.display_type = display_type
        trs, transformable = cls.get_active()
        if trs.active:
            for t in cls.get_transformables():
                t.display_as_wire()
        return None

    @classmethod
    def set_states(cls, context, event, trs: TransformAction):
        """ Update states from context and event
        :param context:
        :param event:
        :param trs:
        :return:
        # TODO: SOC abstraction !! take out of Transform as it depends on tools settings
        """
        ts = context.scene.tool_settings
        slct = context.window_manager.slct
        has_move = trs.has(TransformType.MOVE)
        has_scale = trs.has(TransformType.SCALE)
        has_rotate = trs.has(TransformType.ROTATE)

        trs.state(TransformType.SKIP_CHILDREN, ts.use_transform_skip_children)
        trs.state(TransformType.DATA_ORIGIN, ts.use_transform_data_origin)
        trs.state(TransformType.INDIVIDUAL_ORIGIN, slct.individual_origins)
        trs.state(TransformType.ALIGN_TO_NORMAL, has_move and slct.align_to_normal)
        # NOTE: Move default to location only unless align to normal is enabled
        trs.state(TransformType.LOCATION_ONLY, ts.use_transform_pivot_point_align)
        trs.state(TransformType.PROJECTION, slct.projection)
        trs.state(TransformType.LINKED_COPY, slct.linked_copy)
        trs.state(TransformType.UNIFORM_SCALE, has_scale and event.alt and not event.shift)
        trs.state(TransformType.ROUND, has_rotate and event.alt)
        trs.state(TransformType.SMALL_STEPS, has_rotate and event.alt and event.ctrl)

    @classmethod
    def set_normal(cls, trs, snapitem):
        if snapitem is None:
            trs.normal[:] = Z_AXIS
        else:
            trs.normal[:] = snapitem.normal
        trs.snapitem = snapitem

    @classmethod
    def update(cls, context, event, snap_to: Vector, snapitem=None, index: int = -1):
        """
        Apply a TransformAction
        :param context:
        :param event:
        :param snap_to:
        :param snapitem: SnapItem
        :param index: index of transform in stack
        :return:
        """
        logger.debug("Transform.update()")
        trs, transformable = cls.get_active(index)
        trs.snap_to[:] = snap_to
        cls.set_normal(trs, snapitem)
        trs.step = 1
        cls.set_states(context, event, trs)

        # update previews
        cls._stack[index].update(trs)
        cls.store_transform(trs, transformable)

    @classmethod
    def apply_final(cls, index: int = -1):
        if cls._stack[index].apply_final():
            cls.done = True

    @classmethod
    def confirm(cls, snap_to: Vector, snapitem=None, index: int = -1, reset_preview: bool = False):
        """
        Confirm a transformation
        :param snap_to:
        :param snapitem: ShapItem
        :param index: index of transform action in the stack default -1
        :param reset_preview: reset preview when changes occurs in edit mode
        :return:
        """
        logger.debug("Confirm")
        trs, transformable = cls.get_active(index)
        trs.snap_to[:] = snap_to
        cls.set_normal(trs, snapitem)
        trs.step = 1

        if cls._stack[index].confirm(trs, reset_preview):
            cls.done = True

        for t in cls.get_transformables():
            t.restore_display_type()

        trs.active = False
        cls.store_transform(trs, transformable, True)

    @classmethod
    def exit(cls):
        """
        Cleanup stored data
        :return:
        """
        for t in cls.get_transformables():
            t.restore_display_type()

        for trs in cls._stack:
            trs.exit()

        cls._stack.clear()
        cls.enabled = False
        cls.done = False
