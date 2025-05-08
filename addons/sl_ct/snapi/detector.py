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

import time
from .raster import (
    RasterDetectEngine,
    SnapHelpers
)
from .types import (
    ConstraintType,
    TransformType,
    SnapItemType
)
from .transform import Space, Transform
from .constraint import Constraint
from .drawable import Shader
from .raycast import RayCastDetectEngine
from .grid_engine import GridEngine
from .selection import Selection
from .preferences import Prefs
from .snapitem import (
    SnapItems,
    SnapContext
)
from .widgets import Handles
from .geom import (
    View,
    Geom3d
)
logger = get_logger(__name__, 'ERROR')


class Detector:
    """
        Abstract class for snap processors
    """
    def __init__(self, context, event):

        self.raster = RasterDetectEngine(context)
        self.raycast = RayCastDetectEngine(context)
        self.grid_engine = GridEngine(context)

        self._engines = [
            # raycast before raster as it depends on View.dirty state too
            self.raycast,
            self.raster,
            self.grid_engine
        ]
        self._active = False
        self.snapitem = None

        self.start(context, event)

    def start(self, context, event):
        logger.debug("Detector.start()")
        prefs = Prefs.get(context)
        Shader.line_width = prefs.line_width
        Shader.point_size = prefs.point_size

        Selection.show()
        SnapHelpers.show()
        View.dirty = True

        for engine in self._engines:
            engine.start(context, event)

    def reset(self, context):
        """
        Reset virtual snap items of objects
        Call this method after transform
        :param context:
        :return:
        """
        logger.info("Reset virtual snap items of objects")
        for engine in self._engines:
            engine.update(context)
        View.dirty = True

    def exit(self):
        logger.debug("Detector.exit()")

        for engine in self._engines:
            engine.exit()

        SnapItems.exit()

        Handles.exit()
        SnapContext.exit()
        SnapHelpers.hide()
        # keep for persistence across snap sessions
        # SnapHelpers.exit()

        Selection.exit()

    def draw(self, context):
        """
        Draw detectable points
        :param context:
        :return:
        """
        self.raster.draw(context)

    @property
    def pos(self):

        if self.found:
            return self.snapitem.coord

        #  Evaluate mouse position about relevant snap plane / axis depending on Transform operation type
        trs, transformable = Transform.get_active()

        if trs.active:

            about = Space.get(trs, transformable.o.matrix_world).copy()

            if trs.has(TransformType.MOVE):
                # about is active_object !
                about.translation = trs.snap_from

            if trs.has(TransformType.ROTATE) or trs.has_constraint(ConstraintType.PLANE):

                about = Constraint.rotation_plane(trs, about)
                return Geom3d.mouse_to_plane(about)

            elif trs.has_constraint(ConstraintType.AXIS):
                p0 = about.translation
                if trs.has_constraint(ConstraintType.X):
                    p1 = p0 + about.col[0].xyz
                elif trs.has_constraint(ConstraintType.Y):
                    p1 = p0 + about.col[1].xyz
                else:
                    p1 = p0 + about.col[2].xyz

                it = Geom3d.neareast_point_ray_line(View.origin, View.direction, p0, p1)

                if it is not None:
                    return it

            return Geom3d.mouse_to_plane(trs.space, -View.vector())

        # fallback to mouse to screen oriented plane about trs
        return Geom3d.mouse_to_plane(transformable.matrix_step, -View.vector())

    @property
    def found(self):
        return self.snapitem is not None

    def exclude(self, context, selection: list = None):
        for engine in self._engines:
            engine.exclude(context, selection)

    def detect(self, context, event):
        # Prevent call overflow as modal may fire faster than process time
        if self._active:
            logger.debug("Detector.detect() _active = True : skip")
            return

        self._active = True

        t = time.time()
        # do not even try to detect if pointer is out of 3d view
        if View.init(context, event):

            for engine in self._engines:
                if engine.enabled:
                    engine.detect(context, event)

            if SnapItems.found:

                # when snapping to normal use ray depth to sort items, as a back face may be closest than anything else
                if context.mode == "EDIT_MESH":
                    # and ConstraintType.has(ConstraintType.NORMAL):
                    def key(i):
                        return SnapItemType.key(i.type), i.ray_depth, i.dist, i.z
                else:
                    # prefer closest z items when pixel distance is the same
                    # sort by typ  point / line center / line / tri center / tri

                    def key(i):
                        return SnapItemType.key(i.type), i.dist, i.z

                # Closest snap item
                self.snapitem = SnapItems.find(key)

                logger.debug("Detector.detect() : found %.4f %s" % (time.time() - t, self.snapitem))

                Selection.add_hover(self.snapitem)
                Selection.show()

            else:
                logger.debug("Detector : not found %.4f" % (time.time() - t))
                self.snapitem = None
                Selection.remove_hover()

        self._active = False
