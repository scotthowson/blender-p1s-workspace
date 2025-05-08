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
from enum import IntFlag, auto
from .geom import View
logger = get_logger(__name__, 'ERROR')


class TypeEnum:

    NONE = 0
    _mode: int = NONE

    def __init__(self, mode: int = 0):
        self._mode = mode
        pass

    @classmethod
    def on_change(cls, changed: bool):
        """
        Callback to handle changes on subclass
        :param changed:
        :return:
        """
        pass

    @classmethod
    def set(cls, mode: int):
        """
        Set mode, replace all
        :param mode:
        :return:
        """
        old = cls._mode
        cls._mode = mode
        cls.on_change(old != cls._mode)
        return None

    @classmethod
    def get(cls):
        return cls._mode

    @classmethod
    def has_not(cls, mode: int) -> bool:
        """
        Return true when any given mode is not enabled
        :param mode:
        :return:
        """
        return (cls._mode & mode) == 0

    @classmethod
    def has(cls, mode: int) -> bool:
        """
        Return true when any given mode is enabled
        :param mode:
        :return:
        """
        return (cls._mode & mode) > 0

    @classmethod
    def all(cls, mode: int) -> bool:
        """
        Return true when all given mode(s) are enabled
        :param mode:
        :return:
        """
        return (cls._mode & mode) == mode

    @classmethod
    def equals(cls, mode: int) -> bool:
        """
        Return true when mode strictly equals with all enabled ones
        :param mode:
        :return:
        """
        return cls._mode == mode

    @classmethod
    def enable(cls, mode: int) -> None:
        old = cls._mode
        cls._mode = old | mode
        cls.on_change(old != cls._mode)

    @classmethod
    def disable(cls, mode: int) -> None:
        old = cls._mode
        cls._mode = old & ~mode
        cls.on_change(old != cls._mode)

    @classmethod
    def state(cls, mode: int, state: bool) -> None:
        """
        Enable or disable given flag according state value
        :param mode:
        :param state:
        :return:
        """
        if state:
            cls.enable(mode)
        else:
            cls.disable(mode)

    @classmethod
    def toggle(cls, mode: int) -> None:
        """
        Toggle state of mode
        :param mode:
        :return:
        """
        if cls.has(mode):
            cls.disable(mode)
        else:
            cls.enable(mode)

    @classmethod
    def clear(cls) -> None:
        old = cls._mode
        cls._mode = cls.NONE
        cls.on_change(old != cls._mode)

    @classmethod
    def from_enumproperty(cls, enum):
        # noinspection PyTypeChecker
        for typ in cls:
            if typ.name in enum:
                cls.enable(typ)

    @classmethod
    def as_string(cls, mode=None) -> str:
        """
        :param mode: Optional, a mode to test against, default to current state of class
        :return: string representation of enabled modes
        NOTE: cast to string probably is overshoot as typical usage rely on string format - casting twice
        """
        if mode is None:
            mode = cls._mode
        m = cls(mode)
        return "%s %i" % (str(m), int(mode))


class BatchType(IntFlag):
    """
        Types for detectable GPUBatch type
    """
    # allowed types
    NONE = auto()
    POINTS = auto()
    LINES = auto()
    TRIS = auto()


class ShaderType(IntFlag):
    NONE = 0
    UNIFORM_2D = auto()
    UNIFORM_3D = auto()


class TransformType(TypeEnum, IntFlag):
    MOVE = auto()
    ROTATE = auto()
    SCALE = auto()
    # Orient x axis while keeping z up ans y horizontal
    PINHOLE = auto()
    # Apply a transform matrix from matrix_step for step operations saving steps into matrix_step
    FINAL = auto()
    # align by 3 points, 1: move / 2: orient x axis / 3: rotate y about x
    BY_3_POINTS = auto()
    # Modes
    KEYBOARD = auto()
    ROUND = auto()
    SMALL_STEPS = auto()
    COPY = auto()
    LINKED_COPY = auto()
    # Spaces
    INDIVIDUAL_ORIGIN = auto()
    SCREEN = auto()
    # In keyboard mode, set scale by size
    ABSOLUTE = auto()
    UNIFORM_SCALE = auto()
    # Transform target, tools settings
    LOCATION_ONLY = auto()
    DATA_ORIGIN = auto()
    SKIP_CHILDREN = auto()
    #
    ALONG_SEGMENT = auto()
    ALIGN_TO_NORMAL = auto()
    # Transform only previews and store to matrix save
    # call apply_final() to set objects transformation
    APPLY_STEP = auto()
    # Shrink wrap
    PROJECTION = auto()


class TextType(TypeEnum, IntFlag):
    TEXT_2D = auto()
    TEXT_3D = auto()
    CENTER = auto()
    LEFT = auto()
    RIGHT = auto()
    MIDDLE = auto()


class ConstraintType(TypeEnum, IntFlag):
    # Define rotation / scale 1d / move axis
    AXIS = auto()
    # Define move / scale 2d plane
    PLANE = auto()
    X = auto()
    Y = auto()
    Z = auto()
    PERPENDICULAR = auto()
    PARALLEL = auto()

    @classmethod
    def set_axis(cls, axis):
        """
        Set axis with PLANE or AXIS, default to AXIS when not set
        :param axis:  in ConstraintType.X|Y|Z with [PLANE | AXIS | None], default to AXIS
        :return:
        """
        cls.disable(
            cls.X |
            cls.Y |
            cls.Z |
            cls.AXIS |
            cls.PLANE
        )
        cls.enable(axis)
        if not cls.has(cls.AXIS | cls.PLANE):
            cls.enable(cls.AXIS)

    @classmethod
    def set_perpendicular(cls, state):
        cls.disable(cls.PARALLEL)
        if state:
            cls.enable(cls.PERPENDICULAR)
        else:
            cls.disable(cls.PERPENDICULAR)

    @classmethod
    def set_parallel(cls, state):
        cls.disable(cls.PERPENDICULAR)
        if state:
            cls.enable(cls.PARALLEL)
        else:
            cls.disable(cls.PARALLEL)

    @classmethod
    def get_active_axis(cls):
        if cls.has(cls.X):
            return cls.X
        elif cls.has(cls.Y):
            return cls.Y
        elif cls.has(cls.Z):
            return cls.Z
        return cls.NONE

    @classmethod
    def get_axis_name(cls) -> str:
        """
        Return Axis name for rotations, default to Z when not set
        :return: Axis as name for rotation matrix
        """
        if cls.has(cls.X):
            return "X"
        elif cls.has(cls.Y):
            return "Y"
        return "Z"


class SpaceType(TypeEnum, IntFlag):
    WORLD = auto()
    LOCAL = auto()
    SCREEN = auto()
    USER = auto()


class SnapTargetType(IntFlag):
    NONE = 0
    POINT = auto()
    LINE = auto()
    POLY = auto()
    # For future use
    CIRCLE = auto()
    ELLIPSIS = auto()


class SnapItemType(IntFlag):
    NONE = 0
    POINT = auto()
    LINE = auto()
    TRI = auto()
    CENTER = auto()

    @classmethod
    def key(cls, mode):
        """
        Allow to sort items by type
        :param mode:
        :return:
        """
        value = cls(mode)
        key = 0
        if value & cls.POINT:
            key = 0

        elif value & cls.LINE:
            key += 2

        elif value & cls.TRI:
            key += 4

        if not (value & cls.CENTER):
            key += 1

        logger.debug("%s %s" % (value, key))

        return key


class SnapType(TypeEnum, IntFlag):

    VERT = auto()
    EDGE = auto()
    FACE = auto()
    GRID = auto()
    EDGE_CENTER = auto()
    FACE_CENTER = auto()
    ORIGIN = auto()
    BOUNDS = auto()
    CURSOR = auto()
    ISOLATED = auto()
    VIRTUAL = auto()
    INSTANCES = auto()
    # Center of selection in edit mode
    CENTER = auto()

    @classmethod
    def on_change(cls, changed: bool):
        # Trigger redraw when snap mode change
        if changed:
            View.dirty = True


class State(IntFlag):
    # States for colors / normal hover active selected
    NONE = 0
    NORMAL = auto()
    HOVER = auto()
    ACTIVE = auto()
    SELECTED = auto()
