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
import os
# noinspection PyUnresolvedReferences
from bpy.app.icons import (
    new_triangles_from_file,
    release
)
# noinspection PyUnresolvedReferences
from bpy.utils.previews import (
    new,
    remove
)


# Base name of available icon files in ./icons/ folder, without extension assumed to be .png
icons_names = [
    "x_axis",
    "y_axis",
    "z_axis",
    "x_plane",
    "y_plane",
    "z_plane",
    "ZERO",
    "ONE",
    "TWO",
    "THREE",
    "FOUR",
    "FIVE",
    "SIX",
    "SEVEN",
    "EIGHT",
    "NINE",
    "BACK_SPACE",
    "UP_ARROW",
    "DOWN_ARROW",
    "LEFT_ARROW",
    "RIGHT_ARROW",
    "MOUSE_WHEEL"
]

# TODO: add missing F_[1:12] icons


class IconGeom(dict):
    """
    Icon based on geometry.dat files
    Not suited for regular icons as size doesnt match (...)
    """
    def __init__(self, icons: list = None):
        dict.__init__(self)
        if icons is not None:
            self.register(icons)

    def register(self, icons: list):
        if len(self) == 0:
            path = os.path.join(os.path.dirname(__file__), "icons")
            self.unregister()
            self.update({
                file: new_triangles_from_file(os.path.join(path, "%s.dat" % file))
                for file in icons
            })

    def unregister(self):
        for file, icon_id in self.items():
            release(icon_id)
        self.clear()


class Icon(dict):
    """
    Wrapper for blender's icon collection, provide more simple access to icon_id: icons["icon_name"]
    Manage auto-load at create time, and cleanup through .unregister() method
    """
    def __init__(self, icons: list = None):
        """
        Setup image based icons
        :param icons: list of base file name without extension, assumed to be .png
         Icons must be in ./icons/ sub folder relative to this file
        """
        dict.__init__(self)
        self._pcoll = None
        if icons is not None:
            self.register(icons)

    def register(self, icons: list):
        if len(self) == 0:
            if self._pcoll is None:
                self._pcoll = new()

            path = os.path.join(os.path.dirname(__file__), "icons")
            for file in icons:
                self._pcoll.load(file, os.path.join(path, "%s.png" % file), 'IMAGE')

            self.update({
                file: self._pcoll[file].icon_id
                for file in icons
            })

    def unregister(self):
        """
        Cleanup icons on unregister
        :return:
        """
        if len(self) > 0:
            remove(self._pcoll)
            self.clear()
