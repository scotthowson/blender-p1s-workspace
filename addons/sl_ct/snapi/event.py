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
from bpy.app import version
# noinspection PyUnresolvedReferences
from mathutils import Vector
import time
logger = get_logger(__name__, 'ERROR')


class SnapEvent:

    __slots__ = ('time', 'snapitem')

    def __init__(self, snapitem):
        self.time = time.time()
        self.snapitem = snapitem


class Events:

    # Delay (s)
    _delay = 0.5
    listen_short = True

    _short = None

    @classmethod
    def init(cls, short_delay=0.2):
        cls._delay = short_delay

    @classmethod
    def short_press(cls):
        cls._short = time.time()

    @classmethod
    def short_release(cls):
        """
        Detect short click, basically catch any event as main may pass through and we may wait for blender to release
        :return:
        """
        if cls._short is None:
            return False

        t = time.time() - cls._short
        cls._short = None
        return t < cls._delay

    @classmethod
    def signature(cls, event):
        """
        Return event signature as tuple
        :param event:
        :return:
        """
        return event.alt, event.ctrl, event.shift, event.type, event.value

    @classmethod
    def outside_region(cls, context, event, test_ui: bool = False) -> bool:
        """
        :param context:
        :param event:
        :param test_ui:
        :return: bool mouse event does not occurs inside region
        """
        # x, y from bottom left
        height = context.region.height
        width = context.region.width
        x = event.mouse_region_x
        y = event.mouse_region_y

        if context.preferences.system.use_region_overlap:
            # N panel
            if test_ui and context.space_data.show_region_ui:
                for region in context.area.regions:
                    if region.type == "UI":
                        w = width - region.width
                        h = height - region.height
                        if x > w and y > h:
                            return True

            if version[0] > 3:
                # in 4.x, area height include header (..)
                for region in context.area.regions:
                    if region.type == "HEADER":
                        height -= region.height
                        break

            if context.space_data.show_region_tool_header:
                # verify tool header height in pixels
                for region in context.area.regions:
                    if region.type == "TOOL_HEADER":
                        height -= region.height
                        break

        return not (
            height > y > 0 and width > x > 0
        )

    @classmethod
    def mouse_pos(cls, event) -> Vector:
        """
        :param event: blender event
        :return: Mouse location as 2d Vector(x, y)
        """
        return Vector((event.mouse_region_x, event.mouse_region_y))
