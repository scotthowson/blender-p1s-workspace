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
from .logger import get_logger
from .preferences import Prefs
from .geom import (
    View
)
logger = get_logger(__name__, 'ERROR')


class DetectEngine:
    """
        Fill snap context with detected data
    """
    def __init__(self, context):
        prefs = Prefs.get(context)
        self._snap_radius = int(prefs.snap_radius)
        # max search radius in pixels (squared)
        self._snap_radius_sq = prefs.snap_radius ** 2

        # visible objects boundary
        self._exclude = set()
        self._visible_objects = set()

    def start(self, context, event):
        # Init from prefs
        pass

    def update(self, context):
        pass

    def exit(self):
        raise NotImplementedError

    @staticmethod
    def _normalized_screen_location(o, space: Matrix, v: Vector, res: list) -> bool:
        """Compute 2d Coord in perspective space normalized in range [-1 | 1], where < -1 and > 1 are not on screen
        :param o: object with bounding_box attribute
        :param space: perspective matrix @ matrix world
        :param v: a 4d vector
        :param res: array of 8 2d Vectors
        :return: bool all bounding box corners are behind view point
        """
        behind = True
        for i, b in enumerate(o.bound_box):
            v[0:3] = b
            pco = space @ v
            pco.xy /= pco.w

            if pco.z > 0:
                logger.debug("x: %s y: %s z: %s" % (pco.x, pco.y, pco.z))
                res[i][:] = pco.xy
                behind = False
            else:
                # point is behind camera
                logger.debug("behind x: %s y: %s z: %s" % (-pco.x, -pco.y, pco.z))
                res[i][:] = -pco.xy

        return behind

    def exclude(self, context, selection: list = None):
        pass

    def _any_visible_box(self, o, matrix_world: Matrix, v: Vector, res: list, box: list) -> bool:
        """Compute pixel bounding rect for object (extend box array)
        :param o: object with bounding_box attribute
        :param v: a 4d vector
        :param res: array of 8 2d Vectors
        :param box: array [xmin, xmax, ymin, ymax] bounding box in pixel, must be empty at call time
        :return: True if object is on screen
        """
        space = View.perspective_matrix @ matrix_world
        behind = self._normalized_screen_location(o, space, v, res)
        if behind:
            logger.debug("%s : all behind" % o.name)
            return False
        i = 0
        for axis in zip(*res):
            mini = min(axis)
            maxi = max(axis)
            if mini > 1.0:
                logger.debug("%s : mini (%.4f) > 1.0" % (o.name, mini))
                return False
            if maxi < -1.0:
                logger.debug("%s : maxi (%.4f) < -1.0" % (o.name, maxi))
                return False
            box.extend([(mini + 1.0) * View.half_window[i], (maxi + 1.0) * View.half_window[i]])
            i += 1
        return True

    @property
    def enabled(self):
        return False

    def detect(self, context, event):
        """
        Add closest entity found in snap context
        :param context:
        :param event:
        :return: None
        """
        raise NotImplementedError
