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
import bpy
from .. import __package__ as bl_idname


# Use triangulated faces as overlay for selection, when disabled draw face outlines only
USE_TRI_OVERLAY = False


class Prefs:
    """
    A class providing convenient access to preferences at runtime
    """

    @classmethod
    def get(cls, context=None):
        _context = context
        if context is None:
            _context = bpy.context
        prefs = _context.preferences.addons[bl_idname].preferences
        return prefs
