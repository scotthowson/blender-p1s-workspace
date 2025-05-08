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
from mathutils import Matrix, Vector
import time
from .engine import (
    DetectEngine
)
from .geom import (
    View,
    Geom3d,
    GRID_STEPS
)
from .types import (
    SnapItemType,
    SnapType
)
from .snapitem import (
    SnapItems
)
from .transform import (
    Space
)
logger = get_logger(__name__, 'ERROR')


class GridEngine(DetectEngine):
    """
    A Grid based detect engine
    """
    def __init__(self, context):
        DetectEngine.__init__(self, context)

    def exit(self):
        pass

    @property
    def enabled(self):
        return SnapType.has(SnapType.GRID)

    def detect(self, context, event):
        """
        :param context: blender's context
        :param event: blender's mouse event
        :return:
        """

        # Snap to grid
        # NOTE: rely on other Space than user as grid origin is not always pivot one
        #       scale match with unit settings
        #       so round will fit with units
        t = time.time()

        p0 = Geom3d.mouse_to_plane(p_co=Space.grid)

        if p0 is not None:
            grid_matrix, has_12_subs, sub_alpha = View.grid_scale(context, Space.grid, GRID_STEPS)

            subs = 10
            if has_12_subs:
                subs = 12

            space_grid = Space.grid @ grid_matrix
            space_invert = Geom3d.matrix_inverted(space_grid, "space_grid")

            # Round to small units
            co = space_grid @ Vector((round(axis * subs, 0) / subs for axis in space_invert @ p0))

            dist = View.distance_pixels_from_3d_sq(co)

            if dist < self._snap_radius_sq:

                SnapItems.add(
                    co,
                    [co],
                    dist,
                    SnapItemType.POINT,
                    0,
                    Space.grid.col[2].xyz,
                    View.distance_from_origin(co),
                    1
                )

        logger.info("GridDetectEngine found: %s %.4f sec" % (SnapItems.count(), time.time() - t))
