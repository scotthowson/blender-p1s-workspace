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
from .preferences import (
    Prefs,
    USE_TRI_OVERLAY
)
from .geom import (
    View,
    MATRIX_WORLD
)
from .types import (
    ShaderType,
    BatchType,
    SnapItemType,
    State
)
from .drawable import (
    Drawable
)
logger = get_logger(__name__, 'ERROR')


class Selected(Drawable):
    """
    Draw selected snap-able object
    """

    def __init__(self, co, indices=None, batch_type: int = BatchType.LINES):
        """
        :param co: world coord
        :param indices:
        :param batch_type:
        """
        color = Prefs.get().color_selected
        Drawable.__init__(self, MATRIX_WORLD, co, indices, batch_type, ShaderType.UNIFORM_3D, color)


class SelectedPoints(Selected):
    """
        Freeform points
    """

    def __init__(self, co, indices=None):
        Selected.__init__(self, co, indices, BatchType.POINTS)


class SelectedLines(Selected):
    """
        Freeform line
    """

    def __init__(self, co, indices=None):
        Selected.__init__(self, co, indices, BatchType.LINES)


class SelectedTris(Selected):
    """
        Freeform tris
    """

    def __init__(self, co, indices=None):
        Selected.__init__(self, co, indices, BatchType.TRIS)


class Selection:
    """
    Display
     - current selection of items to build snap helpers
     - active snap item
    """
    _selected = []
    _hover = None

    # Display enabled
    _enabled = False

    @classmethod
    def draw(cls, context):
        if cls._enabled and View.in_region(context):
            for selected in cls._selected:
                selected.draw()
            if cls._hover is not None:
                cls._hover.draw()

    @classmethod
    def show(cls):
        cls._enabled = True

    @classmethod
    def hide(cls):
        cls._enabled = False

    @classmethod
    def exit(cls):
        cls._selected.clear()
        cls.remove_hover()
        cls.hide()

    @classmethod
    def has_hover(cls):
        return cls._hover is not None

    @classmethod
    def remove_last(cls):
        if len(cls._selected) > 0:
            drawable = cls._selected.pop(-1)
            del drawable
            cls.remove_hover()

    @classmethod
    def create(cls, snapitem, state: int, color):
        """
        Create a SnapItem
        :param snapitem:
        :param state:
        :param color:
        :return:
        """
        target = None

        if snapitem.type & (SnapItemType.POINT | SnapItemType.CENTER):
            target = SelectedPoints([snapitem.coord])

        elif snapitem.type & SnapItemType.LINE:
            target = SelectedLines(snapitem.coords)

        elif snapitem.type & SnapItemType.TRI:
            if USE_TRI_OVERLAY:
                target = SelectedTris(snapitem.coords)
            else:
                coords = snapitem.coords
                size = len(coords)
                indices = [(i - 1, i) for i in range(1, size)] + [(size - 1, 0)]
                target = SelectedLines(coords, indices)
                logger.debug("Selected lines coords : %s  indices : %s" % (coords, indices))
        if target is not None:
            target.state = state
            target.colors = {state: color}

        return target

    @classmethod
    def add(cls, snapitem):
        color = Prefs.get().color_selected
        target = cls.create(snapitem, State.SELECTED, color)
        if target is not None:
            cls._selected.append(target)
            cls.remove_hover()
        return target

    @classmethod
    def add_hover(cls, snapitem):
        """
        Replace hover item by a new one
        :param snapitem:
        :return:
        """
        cls.remove_hover()
        color = Prefs.get().color_hover
        cls._hover = cls.create(snapitem, State.HOVER, color)

    @classmethod
    def remove_hover(cls):
        cls._hover = None
