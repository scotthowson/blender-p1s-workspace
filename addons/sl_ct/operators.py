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
from .snapi.logger import get_logger, DEBUG
from enum import IntFlag, auto
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
from bpy.types import (
    Operator
    )

import time
# noinspection PyUnresolvedReferences
from mathutils import Vector, Matrix
from .snapi.geom import (
    View,
    Geom2d,
    Geom3d,
    Z_AXIS,
# REMOVE begin
    ZERO,
    X_AXIS,
    Y_AXIS,
# REMOVE end
    GRID_STEPS,
    MATRIX_WORLD
)
from .snapi.types import (
    TypeEnum,
    TransformType,
    SpaceType,
    SnapItemType,
    ConstraintType,
    SnapType,
    BatchType
)
from .snapi.units import Units
from .snapi.selection import Selection
from .snapi.detector import Detector
from .snapi.drawable import (
    Circle,
    Cross,
    Line
)
from .snapi.constraint import Constraint
from .snapi.snapitem import (
    SnapItem,
    SnapContext
)
from .snapi.widgets import (
    Handles,
    SnapHelpers,
    Rotation,
    Move,
    Scale,
    Pivot,
    Tripod,
    Grid,
    SelectArea,
    Cursor,
    Feedback,
    ToolTips
)
from .snapi.keyboard import Keyboard
from .snapi.transform import (
    Transform,
    TransformableMesh,
    TransformableCurve,
    Space
)
from .snapi.preferences import (
    Prefs
)
from .keymap import Keymap
from .snapi.event import Events
from .snapi.i18n import i18n
from . import bl_info

logger = get_logger(__name__, 'ERROR')

# REMOVE begin
matrix_world = Matrix()
x_axis = Vector((1, 0, 0))
y_axis = Vector((0, 1, 0))
z_axis = Vector((0, 0, 1))
zero = Vector()
# REMOVE end

class ModalAction(TypeEnum, IntFlag):
    # Targets
    HELPER = auto()
    PIVOT = auto()
    GRID = auto()
    # Edit handle location, waiting for a click to confirm, always with a TRAMSFORM flag
    HANDLE = auto()
    # Transform step 1: waiting for click to set snap_from
    FREEMOVE = auto()
    # Transform step 2: waiting for a click to confirm / exit, transform while moving mouse
    TRANSFORM = auto()
    # Sub for HELPER AVERAGE
    # Selection area for snap helpers
    SELECT = auto()
    # Flag : call Transform.pop() once done, alongside with HELPER and HANDLE
    WIDGET = auto()
    # Move along segment or face normal will bypass keyboard on confirm as values are in snap_from and snap_to
    ALONG_SEGMENT = auto()
    # align widget by 3 points, combined with GRID | PIVOT targets
    BY_3_POINTS = auto()
    # Reserved for future use
    FLAG_1 = auto()
    FLAG_2 = auto()
    FLAG_3 = auto()
    FLAG_4 = auto()
    FLAG_5 = auto()


def get_snap_type(self):
    return SnapType.get()


def set_snap_type(self, mode):
    SnapType.set(mode)
    return None


# noinspection PyPep8Naming
class SLCT_main:

    bl_idname = '%s.transform' % __package__
    bl_label = bl_info['name']
    translation_context = __package__

    bl_options = {"REGISTER", 'UNDO'}

    # snap from and to
    # NOTE: set "in place"
    snap_from = Vector()
    snap_to = Vector()
    snapitem = None
    # a flag to allow disabling of snap
    allow_disable_snap = True

    _detector = None
    _transform_type = TransformType.MOVE
    # times to skip event storm and debug times
    _last_run = 0
    _start_time = 0
    _event_duration = 0
    _skipped_events = 0
    _last_event = 0

    # 0.9.x behaviour, quick pivot setup
    _pivot_by_2_points = False
    _transform_after_pivot = False

    # draw handler
    _handle = None
    _timer = None

    # Widgets
    _cursor = None
    _debug = None
    _tooltip = None
    _last_tip = (None, None)
    # _feedback = None
    _rotation = None
    _move = None
    _scale = None
    _snap = None
    _average = None
    _context_preview_point = None
    _context_preview_line = None
    _selection_area = None
    _pivot = None
    _grid = None
    _tripod = None

    # behaviour
    _confirm_exit = False
    # confirm on release (use preferences)
    _release_confirm = False
    _snap_to_self = True
    _undo_signature = None

    # Store running action when editing grid / pivot
    _last_action = 0

    # SnapTypes always enabled and not exposed
    _default_snap_types = (
        SnapType.CURSOR |
        # SnapType.ISOLATED |
        SnapType.VIRTUAL
    )

    # Store for grid and axis display state
    _grid_visibility = []

    # Blender's grid properties
    _grid_props = {
            'show_floor',
            'show_ortho_grid',
            'show_axis_x',
            'show_axis_y',
            'show_axis_z',
    }

    def exit(self, context):

        context.window.cursor_set("DEFAULT")

        self.set_grid_visibility(context, False)

        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)

        bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        self._handle = None

        # Detector.exit() call SnapContext.exit() and SnapContext call Selection.exit()
        self._detector.exit()
        self._detector = None

        # Cleanup
        Transform.exit()
        ModalAction.set(0)

    def finished(self, context):
        self.exit(context)
        return {'FINISHED'}

    def _update_tooltip(self, context, event):
        trs = Transform.get_action()
        if trs is not None:
            self._tooltip.text = trs.feedback
        self.set_tooltip(context, event)

    def _store_stats(self):
        self._last_run = time.time()
        logger.info("Modal duration %.4f" % (self._last_run - self._start_time))

    def pass_through(self, context, event):
        self._update_tooltip(context, event)
        self._store_stats()
        return {'PASS_THROUGH'}

    def running_modal(self, context, event):
        self._update_tooltip(context, event)
        self._store_stats()
        return {'RUNNING_MODAL'}

    def cancelled(self, context):

        if Transform.done:
            # Store undo when a transform action was made on blender's object
            return self.finished(context)

        self.exit(context)
        return {'CANCELLED'}

    def _draw(self, context):

        # setup pers matrix and window size
        View.prepare_to_draw(context)

        # Preview of transformed objects
        Transform.draw(context)

        # at top so if anything goes wrong after at least cursor is drawn
        self._cursor.draw(context)

        # if DEBUG:
        #    self._preview_widget.draw()

        # draw in reverse order so last is top
        self._grid.draw(context)

        # tripod widget
        self._pivot.draw(context)

        # virtual snap points + snap buffer debug
        self._detector.draw(context)

        # draw tooltip under widgets
        self._tooltip.update(self._cursor.pixel)
        self._tooltip.draw(context)

        # Transform widgets
        self._rotation.draw(context)
        self._move.draw(context)
        self._scale.draw(context)

        self._debug.draw(context, Vector((50, 50)))

        SnapHelpers.draw(context)
        Selection.draw(context)
        Handles.draw(context)

        # Selection area for helpers
        self._selection_area.draw(context)

        # Preview and average
        self._context_preview_point.draw()
        self._context_preview_line.draw()

        self._average.draw()

        # snap circle
        self._snap.draw()
        
        if self._tripod.enabled:
            for o in context.selected_objects:
                if o != context.active_object:
                    self._tripod.matrix_world[:] = o.matrix_world
                    self._tripod.draw(context)

    def draw_handler(self, context):
        self._draw(context)

    def guess_axis(self, context, event):
        """
        Automatic Constraint from closest point
        :return:
        """
        trs = Transform.get_action()

        if trs.has_constraint(ConstraintType.AXIS | ConstraintType.PLANE):
            trs.constraint = ConstraintType.NONE

        else:
            s = [View.screen_location(trs.snap_from - (1000 * trs.space.col[i].xyz)) for i in range(3)]
            e = [View.screen_location(trs.snap_from + (1000 * trs.space.col[i].xyz)) for i in range(3)]
            axis = [ConstraintType.X, ConstraintType.Y, ConstraintType.Z]
            dist = 1e32
            constraint = ConstraintType.NONE
            for o, p, c in zip(s, e, axis):
                d = Geom2d.distance_point_line(View.pixel, o, p)
                if d < dist:
                    dist = d
                    constraint = c

            if event.shift:
                trs.constraint = ConstraintType.PLANE | constraint
            else:
                trs.constraint = ConstraintType.AXIS | constraint

        ConstraintType.set(trs.constraint)

        Transform.update(context, event, self.snap_to, self.get_snapitem())
        self.update_widgets(context, event)
    
    @staticmethod
    def toggle_constraint(axis: ConstraintType, typ: ConstraintType):

        if typ == ConstraintType.PLANE:
            other = ConstraintType.AXIS
        else:
            other = ConstraintType.PLANE

        if ConstraintType.has(axis) and not ConstraintType.has(other):
            ConstraintType.disable(
                ConstraintType.X |
                ConstraintType.Y |
                ConstraintType.Z |
                ConstraintType.AXIS |
                ConstraintType.PLANE
            )
        else:
            ConstraintType.set_axis(axis | typ)

        trs = Transform.get_action()
        trs.constraint = ConstraintType.get()

    def preview_context(self):

        # Eval as ContextResult
        result = SnapContext.eval(SnapContext.POINT)

        if result is None:
            result = SnapContext.eval(SnapContext.LINE)

        if result is None:
            result = SnapContext.eval(SnapContext.SPACE)

        self._context_preview_point.hide()
        self._context_preview_line.hide()

        if result is not None:
            size = len(result.coord)
            if size == 1:
                self._context_preview_point.pos = result.coord[0]
                self._context_preview_point.show()
            elif size == 2:
                self._context_preview_line.from_2_points(*result.coord)
                self._context_preview_line.show()
            elif size == 3:
                p0, p1 = result.space.translation, result.space @ Z_AXIS
                self._context_preview_line.from_2_points(p0, p1)
                self._context_preview_line.show()

        result = SnapContext.eval(SnapContext.AVERAGE)
        if result is not None:
            self._average.pos = result.coord[0]
            self._average.show()

    def context_from_hover(self):
        """
        Evaluate hover snapitem as context when nothing is selected
        :return:
        """
        if self._detector.found and SnapContext.is_empty():
            SnapContext.add(self._detector.snapitem)
            return True
        return False

    def eval_context(self):
        """
        Evaluate context, create helpers according
        :return:
        """
        self.hide_context_preview()
        # Eval as snap helpers
        if SnapContext.eval_as_helper(SnapContext.POINT):
            SnapContext.exit()
            logger.debug("SnapContext.eval_as_helper() found SnapContext.POINT")
            return True

        elif SnapContext.eval_as_helper(SnapContext.LINE):
            SnapContext.exit()
            logger.debug("SnapContext.eval_as_helper() found SnapContext.LINE")
            return True

        elif SnapContext.eval_as_helper(SnapContext.SPACE):
            SnapContext.exit()
            # Will be normal line + matrix
            logger.debug("SnapContext.eval_as_helper() found SnapContext.SPACE")
            return True

        elif SnapContext.eval_as_helper(SnapContext.LINE_INTERSECT):
            SnapContext.exit()
            # Will be normal line + matrix
            logger.debug("SnapContext.eval_as_helper() found SnapContext.SPACE")
            return True

        logger.debug("SnapContext.eval_as_helper() no SnapContext Found, eval hover items")
        if self.context_from_hover():
            # ModalAction.enable(ModalAction.SELECT)
            return self.eval_context()

        return False

    def toggle_space(self, context):
        """
        Set trs space according space toggle
        By default, when SpaceType is 0, order.first is set
        :param context:
        :return:
        """
        prefs = Prefs.get(context)
        
        trs = Transform.get_action()
        order = Space.order[prefs.space_order]
        
        if SpaceType.has(order[0]):
            SpaceType.set(order[1])

        elif SpaceType.has(order[1]):
            SpaceType.set(order[2])

        else:
            SpaceType.set(order[0])

        if SpaceType.has(SpaceType.LOCAL):
            # Local to base object !
            trs, transformable = Transform.get_active(0)
            trs.space = transformable.o.matrix_world

        elif SpaceType.has(SpaceType.USER):
            trs.space = Space.get_user()

        else:
            # default to world
            trs.space = MATRIX_WORLD

        if ModalAction.has(ModalAction.PIVOT):
            trs.space.translation[:] = self._pivot.matrix_world.translation

        if ModalAction.has(ModalAction.GRID):
            trs.space.translation[:] = self._grid.matrix_world.translation
            self._grid.matrix_world[:] = trs.space

        else:
            # Copy into tripod
            self._pivot.matrix_world[:] = trs.space

    def hide_context_preview(self):
        # Hide temp context
        self._average.hide()
        self._context_preview_point.hide()
        self._context_preview_line.hide()

    def get_snapitem(self):
        if self._detector.found:
            logger.debug("normal : %s" % self._detector.snapitem.normal)
            return self._detector.snapitem
        return None

    def keyboard_event_handler(self, context, event):
        """Handle keyboard events
        :param context:
        :param event:
        :return: Modal {}
        """

        if event.value != "PRESS":
            return self.running_modal(context, event)

        k = event.type
        prefs = Prefs.get(context)
        # -------------------------
        # Confirm / Cancel
        # -------------------------

        if k == "ESC":
            return self.confirm(context, event, False)

        elif k in {"RET", "NUMPAD_ENTER"}:
            return self.confirm(context, event, True)

        # -----------------------
        # Handle shortcuts
        # -----------------------

        signature = Events.signature(event)
        # NOTE: must "early" return Modal {}
        trs, transformable = Transform.get_active()

        # -----------------------
        # Space toggle
        # -----------------------

        if prefs.match("SWITCH_SPACE", signature):
            self.toggle_space(context)
            return self.running_modal(context, event)

        # ------------------------
        # AXIS | PLANE constraints
        # rotation & scale axis
        # ------------------------

        elif prefs.match("X", signature):
            self.toggle_constraint(ConstraintType.X, ConstraintType.AXIS)
            return self.running_modal(context, event)

        elif prefs.match("Y", signature):
            self.toggle_constraint(ConstraintType.Y, ConstraintType.AXIS)
            return self.running_modal(context, event)

        elif prefs.match("Z", signature):
            self.toggle_constraint(ConstraintType.Z, ConstraintType.AXIS)
            return self.running_modal(context, event)

        elif prefs.match("XY", signature):
            self.toggle_constraint(ConstraintType.Z, ConstraintType.PLANE)
            return self.running_modal(context, event)

        elif prefs.match("XZ", signature):
            self.toggle_constraint(ConstraintType.Y, ConstraintType.PLANE)
            return self.running_modal(context, event)

        elif prefs.match("YZ", signature):
            self.toggle_constraint(ConstraintType.X, ConstraintType.PLANE)
            return self.running_modal(context, event)

        elif prefs.match("PERPENDICULAR", signature):
            ConstraintType.disable(ConstraintType.PARALLEL)
            ConstraintType.toggle(ConstraintType.PERPENDICULAR)
            trs = Transform.get_action()
            trs.constraint = ConstraintType.get()
            return self.running_modal(context, event)

        elif prefs.match("PARALLEL", signature):
            ConstraintType.disable(ConstraintType.PERPENDICULAR)
            ConstraintType.toggle(ConstraintType.PARALLEL)
            trs = Transform.get_action()
            trs.constraint = ConstraintType.get()
            return self.running_modal(context, event)

        if trs.has_not(TransformType.KEYBOARD | TransformType.COPY):

            # Skip num pad navigation unless user start holding ALT
            if prefs.use_numpad_for_navigation and not event.alt and "NUMPAD_" in event.type:
                return self.pass_through(context, event)

            # ------------------------
            # Snap context handlers
            # ------------------------

            # Widgets direct transform

            if ModalAction.has(ModalAction.HELPER):

                widget = SnapHelpers.active

                # NOTE: Helpers handles are hidden so they are not clickable as we may snap to helper itself
                Handles.exit()

                # SnapHelpers.active may be None
                if widget is not None:

                    storage = SnapHelpers
                    space = Matrix.Translation(widget.pos)

                    if prefs.match("ROTATE", signature):
                        # Prevent calling twice
                        if not (ModalAction.has(ModalAction.WIDGET) and trs.has(TransformType.ROTATE)):

                            # Just in case user press twice or toggle between MOVE and ROTATE
                            if ModalAction.has(ModalAction.WIDGET):
                                Transform.pop()

                            Transform.push(context, [widget], TransformType.ROTATE, space, storage)
                            self._pivot.matrix_world[:] = space

                            ModalAction.enable(ModalAction.FREEMOVE | ModalAction.WIDGET)
                            return self.running_modal(context, event)

                    elif prefs.match("MOVE", signature):

                        # Prevent calling twice to allow snap to grid
                        if not (ModalAction.has(ModalAction.WIDGET) and trs.has(TransformType.MOVE)):

                            # Just in case user press twice or toggle between MOVE and ROTATE
                            if ModalAction.has(ModalAction.WIDGET):
                                Transform.pop()

                            Transform.push(context, [widget], TransformType.MOVE, space, storage)
                            self._pivot.matrix_world[:] = space

                            ModalAction.enable(ModalAction.FREEMOVE | ModalAction.WIDGET)
                            return self.running_modal(context, event)

                    elif prefs.match("SCALE", signature):

                        # Prevent calling twice
                        if not (ModalAction.has(ModalAction.WIDGET) and trs.has(TransformType.SCALE)):

                            # Just in case user press twice or toggle between MOVE and ROTATE
                            if ModalAction.has(ModalAction.WIDGET):
                                Transform.pop()

                            Transform.push(context, [widget], TransformType.SCALE, space, storage)
                            self._pivot.matrix_world[:] = space

                            ModalAction.enable(ModalAction.FREEMOVE | ModalAction.WIDGET)
                            return self.running_modal(context, event)

            # Snap context : Widgets move / remove snap items / helpers
            if prefs.match("PIVOT", signature):

                self._pivot_by_2_points = False
                self._transform_after_pivot = False

                # Setup Space widget
                if SnapContext.is_empty():
                    self.context_from_hover()

                result = SnapContext.eval(SnapContext.SPACE)
                if result is not None:
                    SnapContext.exit()

                    if ModalAction.has(ModalAction.PIVOT):

                        trs = Transform.pop()

                    # Store user space across session
                    SpaceType.set(SpaceType.USER)
                    Space.set_user(result.space)
                    trs.space = result.space

                    # Set constraint axis or plane for quick constraint
                    if self._detector.found and self._detector.snapitem is not None:

                        if self._detector.snapitem.type & SnapItemType.LINE:
                            trs.constraint = ConstraintType.AXIS | ConstraintType.Z

                        elif self._detector.snapitem.type & SnapItemType.TRI:
                            trs.constraint = ConstraintType.PLANE | ConstraintType.Z

                    ConstraintType.set(trs.constraint)

                    # As copy, confirm will alter space according
                    self._pivot.matrix_world[:] = trs.space
                    self.hide_context_preview()

                    if ModalAction.has(ModalAction.BY_3_POINTS):
                        ModalAction.set(ModalAction.FREEMOVE)

                return self.running_modal(context, event)

            elif prefs.match("HELPER", signature):

                # Setup helpers
                if SnapContext.is_empty():
                    self.context_from_hover()

                self.eval_context()
                self.hide_context_preview()
                return self.running_modal(context, event)

            if prefs.match("AVERAGE", signature):

                if SnapContext.eval_as_helper(SnapContext.AVERAGE):
                    SnapContext.exit()
                    self.hide_context_preview()

                return self.running_modal(context, event)

            if prefs.match("GRID", signature):

                SnapType.toggle(SnapType.GRID)

                if SnapType.has(SnapType.GRID):
                    self.set_grid_visibility(context, True)
                else:
                    self.set_grid_visibility(context, False)

                return self.running_modal(context, event)

            elif prefs.match("LOCAL_GRID", signature):
                SnapType.enable(SnapType.GRID)
                self.set_grid_visibility(context, True)
                about = Space.get(trs, transformable.matrix_step).copy()
                if trs.has(TransformType.MOVE):
                    about.translation = trs.snap_from
                # does set Space.grid
                self._grid.matrix_world[:] = Constraint.rotation_plane(trs, about)
                return self.running_modal(context, event)

            elif prefs.match("EDIT_GRID", signature):
                Transform.push(
                    context,
                    [self._grid],
                    TransformType.BY_3_POINTS | TransformType.MOVE,
                    self._grid.matrix_world.copy()
                )
                Transform.start(context, event, self._grid.pos)
                self.set_grid_visibility(context, True)
                SnapType.disable(SnapType.GRID)
                if self._last_action == ModalAction.NONE:
                    self._last_action = ModalAction.get()
                ModalAction.set(ModalAction.BY_3_POINTS | ModalAction.TRANSFORM | ModalAction.GRID)

                return self.running_modal(context, event)

            elif prefs.match("EDIT_PIVOT", signature):

                self._pivot_by_2_points = False
                self._transform_after_pivot = False

                if ModalAction.has_not(ModalAction.PIVOT):
                    Transform.push(
                        context,
                        [self._pivot],
                        TransformType.BY_3_POINTS | TransformType.MOVE,
                        self._pivot.matrix_world.copy()
                    )
                    Transform.start(context, event, self._pivot.pos)
                    self._pivot.show()
                    if self._last_action == ModalAction.NONE:
                        self._last_action = ModalAction.get()
                    ModalAction.set(ModalAction.BY_3_POINTS | ModalAction.TRANSFORM | ModalAction.PIVOT)

                return self.running_modal(context, event)

            elif prefs.match("AS_MESH", signature):
                o = SnapContext.as_mesh(context)
                if o is not None:
                    SnapContext.exit()
                return self.running_modal(context, event)

            elif prefs.match("RESET_TO_WORLD", signature):

                if ModalAction.has(ModalAction.GRID):
                    Space.grid[:] = MATRIX_WORLD
                    SnapType.enable(SnapType.GRID)
                    Transform.pop()
                    ModalAction.set(self._last_action)
                    self._last_action = ModalAction.NONE

                elif ModalAction.has(ModalAction.PIVOT):
                    self._pivot.matrix_world[:] = MATRIX_WORLD
                    Space.set_user(MATRIX_WORLD)
                    SpaceType.set(SpaceType.WORLD)
                    Transform.pop()
                    ModalAction.set(self._last_action)
                    self._last_action = ModalAction.NONE

                return self.running_modal(context, event)

            elif prefs.match("REMOVE_HELPER", signature):
                if SnapHelpers.active is not None:
                    self.hide_context_preview()
                    Handles.exit()
                    SnapHelpers.remove_active(context)

                else:
                    self.hide_context_preview()
                    SnapContext.remove_last()

                return self.running_modal(context, event)

            elif prefs.match("CLEAR_HELPERS", signature):

                if SnapHelpers.active is not None:
                    self.hide_context_preview()
                    Handles.exit()
                    SnapHelpers.clear()

                else:
                    self.hide_context_preview()
                    SnapContext.exit()

                return self.running_modal(context, event)

            # -----------------------
            # Snap Types
            # -----------------------
            
            elif prefs.match("X_RAY", signature):
                context.window_manager.slct.x_ray = not context.window_manager.slct.x_ray
                return self.running_modal(context, event)

            elif prefs.match("CLEAR_SNAP", signature):
                SnapType.clear()
                SnapType.enable(self._default_snap_types)
                return self.running_modal(context, event)

            elif prefs.match("VERT", signature):
                SnapType.toggle(SnapType.VERT)
                return self.running_modal(context, event)

            elif prefs.match("EDGE", signature):
                SnapType.toggle(SnapType.EDGE)
                return self.running_modal(context, event)

            elif prefs.match("EDGE_CENTER", signature):
                SnapType.toggle(SnapType.EDGE_CENTER)
                return self.running_modal(context, event)

            elif prefs.match("FACE", signature):
                SnapType.toggle(SnapType.FACE)
                return self.running_modal(context, event)

            elif prefs.match("FACE_CENTER", signature):
                SnapType.toggle(SnapType.FACE_CENTER)
                return self.running_modal(context, event)

            elif prefs.match("GRID", signature):
                SnapType.toggle(SnapType.GRID)
                if SnapType.has(SnapType.GRID):
                    self.set_grid_visibility(context, True)
                else:
                    self.set_grid_visibility(context, False)
                return self.running_modal(context, event)

            elif prefs.match("ORIGIN", signature):
                SnapType.toggle(SnapType.ORIGIN)
                return self.running_modal(context, event)

            elif prefs.match("BOUNDS", signature):
                SnapType.toggle(SnapType.BOUNDS)
                return self.running_modal(context, event)

            elif signature in self._undo_signature:
                # Prevent blender's undo while running, as undo is not supported
                return self.running_modal(context, event)

            logger.debug("No shortcut handler found")

        # -----------------------
        # Handle keyboard entry
        # -----------------------

        # Only start keyboard action if entry is numeric
        if trs.has_not(TransformType.KEYBOARD | TransformType.COPY) and not Keyboard.is_numeric(event):
            # let non handled events bubble to allow eg: N / T shortcuts in 3d view
            # TODO: extensive test as it may lead to TAB / nasty things to pass through .. so beware with this
            return self.pass_through(context, event)

        # ------------------------------
        # Hover and Quick actions
        # ------------------------------

        if trs.has_not(TransformType.KEYBOARD | TransformType.COPY):

            # -----------------------------
            # Quick R|S + X|Y|Z + number
            # -----------------------------

            if (
                self._transform_type & (TransformType.ROTATE | TransformType.SCALE) > 0 and
                ModalAction.has(ModalAction.BY_3_POINTS)
            ):
                ModalAction.disable(ModalAction.BY_3_POINTS | ModalAction.PIVOT)
                ModalAction.enable(ModalAction.TRANSFORM)

                # Use constraint set in pivot action
                constraint = trs.constraint
                trs = Transform.pop()
                ConstraintType.set(constraint)
                trs.constraint = constraint
            # -----------------------------
            # Hover edge / line / face normal
            # -----------------------------

            if trs.active:
                # -------------------------------------------------
                # Action exists (start with mouse - keyboard eval)
                # -------------------------------------------------

                if self._detector.found and (
                        self._detector.snapitem.type & SnapItemType.LINE  # (SnapItemType.LINE | SnapItemType.TRI)
                ):
                    # if self._detector.snapitem.type & SnapItemType.LINE:
                    p0, p1 = self._detector.snapitem.coords[0:2]
                    # else:
                    #     p0 = self._detector.snapitem.coord
                    #     p1 = p0 + self._detector.snapitem.normal

                    # assume user will snap somewhere along a segment
                    if True or trs.has(TransformType.MOVE):
                        trs.enable(TransformType.ALONG_SEGMENT)
                        # Move along hover segment
                        # Rely on preview_point transform as absolute snap_to store for transformed object
                        logger.debug(
                            "MOVE along segment from: %s to: %s direction: %s" %
                            (self.snap_from, self.snap_to, p1 - self.snap_to)
                        )
                        # Move to segment, at snap_to location
                        self._context_preview_point.pos = p0
                        self._context_preview_point.show()
                        mat = Matrix()
                        Transform.push(context, [self._context_preview_point], TransformType.MOVE, mat)
                        # self._pivot.matrix_world[:] = mat
                        Transform.start(context, event, p0, self.get_snapitem())
                        trs = Transform.get_action()
                        self.snap_to[:] = p1
                        ModalAction.enable(ModalAction.ALONG_SEGMENT)

                    else:
                        # by definition : Transform.has(TransformType.ROTATE | TransformType.SCALE)
                        # set end over a segment
                        # self.snap_from[:] = p0
                        self.snap_to[:] = p1

            else:
                # -------------------------------------------------
                # Action does not exists (not started with mouse),
                # -------------------------------------------------

                ModalAction.disable(ModalAction.FREEMOVE)
                ModalAction.enable(ModalAction.TRANSFORM)

                # ------------------------------
                # hover segment / face normal as constraint
                # -----------------------------
                if self._detector.found and (
                    self._detector.snapitem.type & SnapItemType.LINE  # (SnapItemType.TRI | SnapItemType.LINE )
                ):

                    # if self._detector.snapitem.type & SnapItemType.LINE:
                    p0, p1 = self._detector.snapitem.coords[0:2]
                    # else:
                    #     p0 = self._detector.snapitem.coord
                    #     p1 = p0 + self._detector.snapitem.normal

                    if trs.has(TransformType.MOVE):

                        # Orient along hover segment, this will not bypass constraints
                        # use projection of this value onto constraint axis when set
                        self.snap_from[:] = p0
                        self.snap_to[:] = p1
                        logger.debug(
                            "MOVE in directon of segment from: %s to: %s direction: %s" %
                            (self.snap_from, self.snap_to, self.snap_to - self.snap_from)
                        )

                    else:

                        trs.space = Geom3d.matrix_from_normal(p0, p1 - p0)
                        # by definition : Transform.has(TransformType.ROTATE | TransformType.SCALE)
                        # Set constraint Z axis about segment

                        # SpaceType.set(SpaceType.USER)
                        trs.constraint = ConstraintType.Z | ConstraintType.AXIS
                        # Update ui
                        ConstraintType.set(trs.constraint)

                # Start the action
                # Transform.create(context, space)
                Transform.start(context, event, self.snap_from, self.get_snapitem())

                # Object's transform, display preview
                if ModalAction.has(ModalAction.HELPER):
                    Transform.show(-1)

                elif ModalAction.has_not(ModalAction.WIDGET):
                    Transform.show()

        Keyboard.press(context, event, trs)

        if trs.has(TransformType.COPY):

            if ModalAction.has(ModalAction.ALONG_SEGMENT):
                _trs = Transform.get_action(-2)
            else:
                _trs = trs

            _trs.steps = max(1, Keyboard.copy - 1)

        else:

            trs.enable(TransformType.KEYBOARD)

        # Apply keyboard entry
        Transform.update(context, event, self.snap_to, self.get_snapitem())
        # Move preview ALONG_SEGMENT
        if ModalAction.has(ModalAction.ALONG_SEGMENT):
            # Absolute preview transform
            Transform.update(context, event, self._context_preview_point.pos, self.get_snapitem(), -2)

        # Widget will not redraw here ..
        self.update_widgets(context, event)

        return self.running_modal(context, event)

    def keyboard_event(self, context, event):
        """Handle keyboard events
        :param context:
        :param event:
        :return: Modal {}
        """
        return self.keyboard_event_handler(context, event)

    def confirm_handler(self, context, event, confirm: bool = True):
        """
        :param context:
        :param event:
        :param confirm: True to confirm (default)  False to cancel
        :return: Modal {}
        """
        cancel = not confirm

        prefs = Prefs.get(context)

        # Hide temp context
        self.hide_context_preview()

        trs = Transform.get_action()

        has_keyboard = trs.has(TransformType.KEYBOARD)
        has_helper = ModalAction.has(ModalAction.PIVOT | ModalAction.GRID)

        # has_widget = ModalAction.has(ModalAction.WIDGET)
        # has_freemove = ModalAction.has(ModalAction.FREEMOVE)
        keyboard_cancel = has_keyboard and cancel

        if keyboard_cancel:
            Keyboard.cancel()

        if ModalAction.has(ModalAction.ALONG_SEGMENT):
            ModalAction.disable(ModalAction.ALONG_SEGMENT)

            if confirm:
                # Move preview point over segment
                Transform.confirm(self.snap_to, self.get_snapitem())

                # Set absolute snap to for object's transform
                self.snap_to[:] = self._context_preview_point.pos

            trs = Transform.pop()

            # reset ui states from action
            ConstraintType.set(trs.constraint)
            self._pivot.matrix_world[:] = trs.space

        if ModalAction.has(ModalAction.TRANSFORM):

            if confirm:

                # Reset previews when transform occurs in edit mode
                if not self._confirm_exit:
                    context.window.cursor_set("WAIT")

                # reset preview only if we do not exit on confirm
                Transform.confirm(self.snap_to, self.get_snapitem(), -1, not self._confirm_exit)

                if not self._confirm_exit:

                    # Re-init bounds, origins, pivots, cursor, median and center
                    if ModalAction.has_not(ModalAction.WIDGET):
                        self._detector.reset(context)

                    context.window.cursor_set("NONE")

            else:
                # call cancel for special transform cases actually transforming objects instead of previews
                Transform.cancel()

            if not prefs.keep_constraint_on_exit:
                # Reset ui for constraint
                ConstraintType.set(ConstraintType.NONE)

            if keyboard_cancel:
                # Cancel keyboard must not cancel transform operation
                pass

            else:
                # Hide previews
                Transform.hide()

                trs.disable(TransformType.ALONG_SEGMENT)

                # Cancel keyboard must not cancel transform operation
                ModalAction.disable(ModalAction.TRANSFORM)

                # [HELPER] | HANDLE | TRANSFORM using mouse or G | R | S
                if ModalAction.has(ModalAction.WIDGET):

                    ModalAction.disable(ModalAction.WIDGET)

                    # Remove temp transform on confirm / cancel
                    trs = Transform.pop()
                    ConstraintType.set(trs.constraint)

                    # reset ACTIVE state
                    logger.debug("Release handle %s" % ModalAction.as_string())
                    Handles.release()

                    # Remove ACTIVE state and Refresh helpers / handles location
                    if ModalAction.has(ModalAction.HELPER):
                        SnapHelpers.confirm(context)
                        View.dirty = True

                    if ModalAction.has(ModalAction.HANDLE):
                        ModalAction.disable(ModalAction.HANDLE)
                        if cancel:
                            Handles.exit()

                    if confirm:
                        pass
                    else:
                        ModalAction.set(ModalAction.FREEMOVE)

                else:
                    # Object's transform, go into FREEMOVE
                    ModalAction.enable(ModalAction.FREEMOVE)

                # Hide widgets
                if not prefs.show_tooltips:
                    self._tooltip.hide()
                self._rotation.hide()
                self._move.hide()
                self._scale.hide()

                # Clear exclude
                self._detector.exclude(context)
                self._snap_to_self = False

                self.snap_from[:] = self.snap_to

        if has_keyboard and confirm:
            Keyboard.confirm()

        if ModalAction.has(ModalAction.SELECT):
            if cancel:
                ModalAction.disable(ModalAction.SELECT)
                ModalAction.enable(ModalAction.HELPER)
                self._selection_area.hide()

        elif ModalAction.has(ModalAction.HELPER):

            if cancel:
                # we do not want to exit
                has_helper = True
                # reset helpers state
                SnapHelpers.release()
                # clear handles
                Handles.exit()
                # reset context, clear Selection
                SnapContext.exit()
                ModalAction.set(ModalAction.FREEMOVE)

        trs, transformable = Transform.get_active()

        if ModalAction.has(ModalAction.BY_3_POINTS):

            trs.constraint = ConstraintType.NONE

            confirm_and_exit = False

            # on cancel: FREEMOVE
            if confirm:
                # On confirm + exit, keep FREEMOVE
                if event.shift:
                    # Confirm and exit (ROTATE action will not rely on this)
                    confirm_and_exit = True

                else:
                    # Confirm and start next action, set TRANSFORM to chain
                    ModalAction.disable(ModalAction.FREEMOVE)
                    ModalAction.enable(ModalAction.TRANSFORM)
                    Transform.show()

                if trs.has(TransformType.MOVE):
                    trs.disable(TransformType.MOVE)
                    # pivot by 2 points + start rotation using 2nd point as snap from
                    if not event.shift:
                        # start x axis orientation
                        trs.enable(TransformType.PINHOLE)
                        trs.space = transformable.matrix_step
                        self.snap_from[:] = trs.space.translation + trs.space.col[0].xyz
                        Transform.start(context, event, self.snap_from, self.get_snapitem())

                elif trs.has(TransformType.PINHOLE):
                    trs.disable(TransformType.PINHOLE)

                    # pivot by 2 points + start rotation using 2nd point as snap from
                    if self._pivot_by_2_points:
                        self._pivot_by_2_points = False
                        confirm_and_exit = True

                    elif not event.shift:
                        # start y rotation about x axis
                        trs.enable(TransformType.ROTATE)
                        trs.constraint = ConstraintType.PLANE | ConstraintType.X
                        trs.space = transformable.matrix_step
                        self.snap_from[:] = trs.space.translation + trs.space.col[1].xyz
                        Transform.start(context, event, self.snap_from, self.get_snapitem())

                elif trs.has(TransformType.ROTATE):
                    trs.disable(TransformType.ROTATE)
                    # Confirm and exit
                    confirm_and_exit = True

                if confirm_and_exit:

                    trs = Transform.pop()
                    ConstraintType.set(trs.constraint)
                    Transform.hide()

                    if ModalAction.has(ModalAction.GRID):
                        SnapType.enable(SnapType.GRID)

                    elif ModalAction.has(ModalAction.PIVOT):
                        Space.set_user(self._pivot.matrix_world)
                        SpaceType.set(SpaceType.USER)

                    ModalAction.disable(ModalAction.BY_3_POINTS | ModalAction.GRID | ModalAction.PIVOT)

                    if self._transform_after_pivot:
                        # Start transform using last point as snap_from
                        self._transform_after_pivot = False
                        Transform.start(context, event, self.snap_from, self.get_snapitem())
                        Transform.show()

                    else:
                        ModalAction.disable(ModalAction.TRANSFORM)
                        ModalAction.enable(ModalAction.FREEMOVE)

                    # this is the main transform operation
                    trs.space = Space.get_user()

            else:
                # Cancel and exit
                trs = Transform.pop()
                ConstraintType.set(trs.constraint)
                ModalAction.disable(ModalAction.BY_3_POINTS | ModalAction.GRID | ModalAction.PIVOT)
                Transform.hide()

            # Revert back to last ModalAction if any after grid / pivot edit
            if (confirm_and_exit or cancel) and self._last_action != ModalAction.NONE:
                ModalAction.set(self._last_action)
                self._last_action = ModalAction.NONE
                if ModalAction.has(ModalAction.TRANSFORM):
                    Transform.show()

            ConstraintType.set(trs.constraint)

        if has_keyboard:
            trs.disable(TransformType.KEYBOARD)

        if trs.has(TransformType.COPY):
            trs.disable(TransformType.COPY)
            trs.steps = 0
            Keyboard.exit()

        # Exit on cancel / or if confirm_exit
        return (cancel and not (has_keyboard or has_helper)) or (confirm and Transform.done and self._confirm_exit)

    def confirm(self, context, event, confirm: bool = True):
        """
        :param context:
        :param event:
        :param confirm: True to confirm (default)  False to cancel
        :return: Modal {}
        """
        if self.confirm_handler(context, event, confirm):

            if confirm:
                return self.finished(context)
            else:
                return self.cancelled(context)

        return self.running_modal(context, event)

    @staticmethod
    def sanitize_scale(context, o):
        """ Clean zero scale axis of objects
        When any matrix_world axis scale is 0, objects will not be snap able
        :param context:
        :param o:
        :return:
        """
        m = o.matrix_world
        s = Matrix()
        sanitize = False

        for i in range(3):
            if m.col[i].xyz.length == 0:
                m.col[i][i] = 1.0
                s.col[i][i] = 0.0
                sanitize = True

        if sanitize:
            # apply the scale matrix on changed axis
            if o.type == "MESH":
                transformable = TransformableMesh(context, o, False)
                transformable.transform_data(o, None, s)
            elif o.type == "CURVE":
                transformable = TransformableCurve(context, o)
                transformable.transform_data(o, None, s)

    def exclude_from_snap(self, context):
        # Exclude object from snap
        snap_to_self = context.window_manager.slct.snap_to_self
        if snap_to_self != self._snap_to_self:
            self._snap_to_self = snap_to_self
            if snap_to_self:
                # clear exclude
                self._detector.exclude(context)
            else:
                # exclude selected objects
                self._detector.exclude(context, context.selected_objects)

    def update_widgets(self, context, event):

        if ModalAction.has(ModalAction.TRANSFORM):

            along_segment = ModalAction.has(ModalAction.ALONG_SEGMENT)

            index = -1
            if along_segment:
                index = -2

            trs = Transform.get_action(index)

            # Update feedback and toggle widgets visibility
            if trs.has(TransformType.BY_3_POINTS):
                self._move.hide()
                self._scale.hide()
                self._rotation.hide()

            elif trs.has(TransformType.ROTATE):
                self._rotation.update(index)
                self._rotation.show()
                self._move.hide()
                self._scale.hide()

            elif trs.has(TransformType.MOVE):
                self._move.update(context, index)
                self._move.show()
                self._scale.hide()
                self._rotation.hide()

            elif trs.has(TransformType.SCALE):
                self._scale.update(context, index)
                self._scale.show()
                self._move.hide()
                self._rotation.hide()

            else:
                self._move.hide()
                self._scale.hide()
                self._rotation.hide()

    def mouse_move_handler(self, context, event):

        if self.allow_disable_snap and event.ctrl:
            View.init(context, event)
            self._snap.hide()
            self._detector.snapitem = None

        else:
            self._detector.detect(context, event)
            if self._detector.found:
                self._snap.pos = self._detector.pos
                self._snap.show()
            else:
                self._snap.hide()

        self.snapitem = self._detector.snapitem
        # when snapping to a face in rotation mode, compute snap_to
        self.snap_to[:] = self._detector.pos

        # Find snap items under mouse
        if ModalAction.has(ModalAction.SELECT):
            self._selection_area.update(self._detector.pos)
            return

        if ModalAction.has(ModalAction.TRANSFORM):

            trs = Transform.get_action()

            Transform.update(context, event, self.snap_to, self.get_snapitem())

            self._tripod.enabled = trs.has(TransformType.INDIVIDUAL_ORIGIN)

            self.exclude_from_snap(context)

            self.update_widgets(context, event)

            # HELPER | TRANSFORM | HANDLE, update snap helpers matrix
            # Transform helper using handle
            if ModalAction.has(ModalAction.HELPER):
                # Refresh helper matrix and update handle location
                SnapHelpers.edit()

        else:
            Handles.detect_hover(context)
            SnapHelpers.detect_hover(context)

    def mouse_move(self, context, event):
        """Main mouse move handler, allow override in custom operators
        :param context:
        :param event:
        :return:
        """
        self.mouse_move_handler(context, event)

    def tooltips(self, context, state: str) -> list:
        """Provide "transform" action tooltip
        NOTE: make is possible to handle multiple transform action steps based on transform type
        :param context:
        :param state: key of state in tip dict
        :return: list of tips [([key, ?], tip), ?] for [state]
        """
        raise NotImplementedError

    def get_tips(self, context, action: str, state: str) -> list:
        """ Tips dict {[([key, ?], tip), ?]}[action][state]
        :param context:
        :param action: key of action in tip dict
        :param state: key of state in tip dict
        :return: list of tips [([key, ?], tip), ?] for [action][state]
        """
        if action == "transform":

            return self.tooltips(context, state)

        prefs = Prefs.get(context)
        return {
            "default": {
                "default": [
                    (["MOUSE_RMB", "EVENT_RETURN"], "Confirm"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Cancel / Exit")
                ]
            },

            "Select": {
                "Select": [
                    # Select area
                    (["MOUSE_RMB", "EVENT_SHIFT"], "Select more")
                ],
                "Select / edit": [
                    # select context
                    (["MOUSE_RMB", "EVENT_SHIFT"], "Select / edit"),
                    (prefs.tip("HELPER")),
                    (prefs.tip("AVERAGE")),
                    (prefs.tip("REMOVE_HELPER")),
                    (prefs.tip("CLEAR_HELPERS"))
                ]
            },
            "edit": {
                "Helper": [
                    (["MOUSE_RMB"], "Edit"),
                    (["MOUSE_RMB", "EVENT_SHIFT"], "Select / edit"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Exit edit mode"),
                    (prefs.tip("REMOVE_HELPER")),
                    (prefs.tip("CLEAR_HELPERS")),
                    (prefs.tip("AS_MESH")),
                    (["EVENT_G"], "Move"),
                    (["EVENT_R"], "Rotate")
                ],
                "Handle": [
                    (["MOUSE_RMB"], "Set destination"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Exit")
                ]
            },

            "Keyboard": {
                "Enter a value": [
                    (["ZERO"], "Enter value"),
                    (["EVENT_M", "EVENT_I", "EVENT_N"], "Set unit"),
                    (["BACK_SPACE"], "Delete last"),
                    (["EVENT_RETURN"], "Confirm"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                ]
            },
            "widgets": {
                "Pick start point": [
                    (["MOUSE_LMB"], "Confirm"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Exit"),
                    (prefs.tip("RESET_TO_WORLD")),
                    (prefs.tip("SWITCH_SPACE"))
                ],
                "move": [
                    (["MOUSE_LMB"], "Confirm and orient x axis"),
                    (["MOUSE_LMB", "EVENT_SHIFT"], "Confirm and exit"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                    (prefs.tip("RESET_TO_WORLD")),
                    (prefs.tip("SWITCH_SPACE"))
                ],
                "Orient x axis": [
                    (["MOUSE_LMB"], "Confirm and orient y axis"),
                    (["MOUSE_LMB", "EVENT_SHIFT"], "Confirm and exit"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                    (prefs.tip("RESET_TO_WORLD")),
                    (prefs.tip("SWITCH_SPACE")),
                    (["ZERO"], "Enter value"),
                    (prefs.tip("LOCAL_GRID")),
                    (["EVENT_SHIFT", "EVENT_X", "EVENT_Y", "EVENT_Z"], "Constraint to plane")
                ],
                "Orient y axis": [
                    (["MOUSE_LMB"], "Confirm and exit"),
                    (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                    (prefs.tip("RESET_TO_WORLD")),
                    (prefs.tip("SWITCH_SPACE")),
                    (["ZERO"], "Enter value"),
                    (prefs.tip("LOCAL_GRID")),
                ]
            },
        }[action][state]

    @staticmethod
    def get_tooltip_action(event, trs) -> str:
        """Default action name given modal action
        :param event:
        :param trs: TransformAction
        :return: Action name
        """
        _action = "transform"

        if trs.has(TransformType.KEYBOARD):
            _action = "Keyboard"

        elif ModalAction.has(ModalAction.BY_3_POINTS):
            # ModalAction.GRID | ModalAction.PIVOT
            _action = "widgets"

        elif ModalAction.has(ModalAction.HELPER):
            # Edit helper / handle
            _action = "edit"

        elif ModalAction.has(ModalAction.SELECT):
            # Select area
            _action = "Select"

        elif ModalAction.has(ModalAction.FREEMOVE):
            if event.shift:
                _action = "Select"

        return _action

    def get_tooltip_header(self, event, default: str) -> str:
        """Override default with own header
        :param event:
        :param default:
        :return: header
        """
        _header = default

        if ModalAction.has(ModalAction.BY_3_POINTS):
            # Pivot unless we are in GRID
            if ModalAction.has(ModalAction.GRID):
                _header = "Grid by 3 points"
            else:
                if self._pivot_by_2_points:
                    _header = "Pivot by 2 points"
                else:
                    _header = "Pivot by 3 points"

        elif ModalAction.has(ModalAction.SELECT):
            _header = "Select helpers"

        elif ModalAction.has(ModalAction.HELPER):

            if ModalAction.has(ModalAction.WIDGET):
                trs = Transform.get_action()
                if trs.has(TransformType.MOVE):
                    _header = "Move helper"
                elif trs.has(TransformType.ROTATE):
                    _header = "Rotate helper"
                elif trs.has(TransformType.SCALE):
                    _header = "Scale helper"
            else:
                _header = "Edit helper"

        else:

            if ModalAction.has(ModalAction.FREEMOVE):
                if event.shift:
                    # Select context
                    _header = "Select context"

            if ModalAction.has(ModalAction.ALONG_SEGMENT):
                _header = "Along segment"

        return _header

    @staticmethod
    def get_tooltip_state(event, trs, action) -> str:
        """
        :param event:
        :param trs:
        :param action:
        :return: state
        """
        state = "Pick start point"

        if action == "Keyboard":
            state = "Enter a value"

        elif action == "widgets":

            if trs.has(TransformType.MOVE):
                state = "move"
            elif trs.has(TransformType.PINHOLE):
                state = "Orient x axis"
            elif trs.has(TransformType.ROTATE):
                state = "Orient y axis"

        elif action == "Select":
            if ModalAction.has(ModalAction.SELECT):
                # Select AREA
                state = "Select"
            else:
                # Context
                state = "Select / edit"

        elif action == "edit":
            # Edit helpers
            if ModalAction.has(ModalAction.HANDLE):
                state = "Handle"
            else:
                state = "Helper"

        else:

            if ModalAction.has(ModalAction.FREEMOVE):
                # Select context items
                if event.shift:
                    state = "Select / edit"

            elif ModalAction.has(ModalAction.TRANSFORM):
                state = "Pick destination"

        return state

    def set_tooltip(self, context, event, header: str = "Transform"):
        """
        :param context:
        :param event:
        :param header:
        :return:
        """
        trs = Transform.get_action()

        action = self.get_tooltip_action(event, trs)
        state = self.get_tooltip_state(event, trs, action)
        header = self.get_tooltip_header(event, header)

        # Show "Measure mode"
        if len(context.selected_objects) == 0:
            header = "%s - %s" % (i18n.translate("Measure"), header)

        if self._last_tip == (header, action, state):
            return

        self._last_tip = (header, action, state)

        tips = self.get_tips(context, action, state)

        self._tooltip.replace(context, header, state, tips)
        self._tooltip.show()

    def mouse_press_handler(self, context, event):
        """
        :param context:
        :param event:
        :return: False to keep modal running, True to confirm
        """
        # TODO: (?) check order to allow EDIT mode switch while in transform operation
        # prefs = Prefs.get(context)

        # if ModalAction.has(ModalAction.TRANSFORM):
        #     if self._release_confirm:
        #         return self.running_modal(context, event)
        #     else:
        #         return self.confirm(context, event)

        # Out of event.shift
        handle = Handles.press(context)
        if handle is not None:

            logger.debug("Handle.press(), set snap_from")

            # Select a handle
            # snap from is active handle location
            self.snap_from[:] = handle.pos

            # Handle may only provide a "snap_from"
            if handle.action == TransformType.NONE:
                # Wait for a keyboard press to push a transformation
                # In snap from only mode, handle does nothing
                # We are now in TRANSFORM mode
                handle.release()
                if ModalAction.has(ModalAction.FREEMOVE):
                    Transform.start(context, event, self.snap_from)
                    ModalAction.disable(ModalAction.FREEMOVE)
                    ModalAction.enable(ModalAction.TRANSFORM)

            else:
                Transform.push(context, [handle], handle.action, handle.matrix_world)
                Transform.start(context, event, self.snap_from)
                ModalAction.disable(ModalAction.FREEMOVE)
                ModalAction.enable(ModalAction.TRANSFORM | ModalAction.HANDLE | ModalAction.WIDGET)

            # Must not snap to self, so disable until confirm
            if ModalAction.has(ModalAction.GRID):
                SnapType.disable(SnapType.GRID)

            return self.running_modal(context, event)

        trs, transformable = Transform.get_active()

        # Select snap items / helpers
        if event.shift and trs.has_not(TransformType.BY_3_POINTS):

            if SnapHelpers.press(context):
                logger.info("SnapHelper press")

                # SnapHelper may be "hover" but still not found by detector on edge cases ..
                if self._detector.found:

                    SnapContext.add(self._detector.snapitem)
                    self.preview_context()

                    # Select another snap helper on the fly, show handles
                    ModalAction.enable(ModalAction.HELPER)

            # Select snap items by hand
            elif self._detector.found:
                Handles.exit()
                SnapHelpers.release()
                # Add snap items to SnapContext
                SnapContext.add(self._detector.snapitem)
                self.preview_context()
                ModalAction.disable(ModalAction.HELPER)

            # select many snap helpers
            else:
                Handles.exit()
                SnapHelpers.release()
                self._selection_area.press(self._detector.pos)
                self._selection_area.show()
                ModalAction.disable(ModalAction.HELPER)
                ModalAction.enable(ModalAction.SELECT)

            return self.running_modal(context, event)

        if ModalAction.has(ModalAction.FREEMOVE):

            self.snap_from[:] = self._detector.pos

            if trs.has(TransformType.BY_3_POINTS):
                # FREEMOVE press
                if trs.has_not(TransformType.MOVE | TransformType.ROTATE | TransformType.PINHOLE):
                    # we are at start point, choose from
                    matrix_world = transformable.o.matrix_world
                    if ModalAction.has(ModalAction.BY_3_POINTS):
                        # Set snap_from to current widget location
                        self.snap_from[:] = matrix_world.translation
                    else:
                        # Move pivot to snap_from, update trs and transformable according
                        matrix_world.translation[:] = self.snap_from
                        transformable.matrix_step[:] = matrix_world

                    trs.space = matrix_world
                    trs.enable(TransformType.MOVE)

            logger.debug("switch to ModalAction.TRANSFORM")

            # Hide selection and context items
            SnapContext.exit()

            ModalAction.disable(ModalAction.FREEMOVE)
            ModalAction.enable(ModalAction.TRANSFORM)

            trs.constraint = ConstraintType.get()

            Transform.start(context, event, self.snap_from, self.get_snapitem())

            self._tripod.enabled = trs.has(TransformType.INDIVIDUAL_ORIGIN)
            
            # ModalAction.TRANSFORM | ModalAction.HANDLE | ModalAction.WIDGET
            
            if ModalAction.has(ModalAction.HELPER):
                # Editing helper so show helper
                Transform.show(-1)

            elif ModalAction.has_not(ModalAction.WIDGET):
                # not Editing helper (G | R) / handle
                Transform.show()

            return self.running_modal(context, event)

        if self._release_confirm:
            return self.running_modal(context, event)
        else:
            return self.confirm(context, event)

    def mouse_press(self, context, event):
        """
        :param context:
        :param event:
        :return: Modal {}
        """
        return self.mouse_press_handler(context, event)

    def store_grid_visibility(self, context):
        self._grid_visibility = [
            getattr(context.space_data.overlay, prop) for prop in self._grid_props
        ]

    def set_grid_visibility(self, context, state):
        """
        :param context:
        :param state: When True, display grid and hide blender's grid
        :return:
        """
        if state:
            self._grid.show()
            for prop in self._grid_props:
                setattr(context.space_data.overlay, prop, False)
        else:
            self._grid.hide()
            for prop, value in zip(self._grid_props, self._grid_visibility):
                setattr(context.space_data.overlay, prop, value)

    def set_mouse_cursor(self, context, event):

        if Events.outside_region(context, event, test_ui=True):
            self._cursor.hide()
            context.window.cursor_set("DEFAULT")
            return

        self._cursor.show()
        context.window.cursor_set("NONE")

        if len(context.selected_objects) == 0:
            state = Cursor.MEASURE

        else:
            trs = Transform.get_action()

            state = Cursor.SNAP

            if trs.has(TransformType.KEYBOARD):
                state = Cursor.TEXT

            elif ModalAction.has(ModalAction.TRANSFORM):

                if trs.has(TransformType.SCALE):
                    state = Cursor.SCALE

                elif trs.has(TransformType.ROTATE | TransformType.PINHOLE):
                    state = Cursor.ROTATE

                elif trs.has(TransformType.MOVE):
                    state = Cursor.MOVE

            elif event.shift or ModalAction.has(ModalAction.SELECT | ModalAction.HELPER):
                state = Cursor.EDIT

        self._cursor.update(context, event, state)

    def modal(self, context, event):

        # """
        # States
        # FREEMOVE  -> wait for snap_from and click to switch to transform
        # TRANSFORM -> wait for snap_to to confirm
        # BY_3_POINTS | [GRID | PIVOT] : Edit by 3 points active
        # SELECT : Select Area is active
        # shift + click ->
        #     select snap items, KEY to eval as [ AVERAGE | HELPER ]
        #     switch to EDIT on click over widgets
        # EDIT helper
        #     by mouse
        #     HANDLE | TRANSFORM      -> Move using handle
        #     by shortcuts : G | R
        #     FREEMOVE                -> Move, Wait for click on snap_from
        #     TRANSFORM               -> Move / Rotation, Wait for user click to confirm
        #       + WIDGET              -> means we must Transform.pop() once done
        # * KEYBOARD
        # """

        # ------------------------
        # Basic context check
        # ------------------------
        # REMOVE begin
        assert(MATRIX_WORLD == matrix_world)
        assert(ZERO == zero)
        assert(X_AXIS == x_axis)
        assert(Y_AXIS == y_axis)
        assert(Z_AXIS == z_axis)
        # REMOVE end

        if context.area is None:
            logger.debug("context.area is none")
            return self.finished(context)
            
        if context.region_data is None:
            logger.debug("context.region_data is none")
            return self.finished(context)

        if event.type == "TIMER":
            return self.pass_through(context, event)

        self.set_mouse_cursor(context, event)
        context.area.tag_redraw()

        t = time.time()
        self._start_time = t
        _event_duration = t - self._last_run

        logger.debug("Modal t - _last_run %.4f" % _event_duration)

        # ------------------------
        # Skip modal conditions
        # ------------------------

        # Events are "stacked" on blender's side and cast once modal ends.
        # So once modal done we may have many events to consume.
        # The window to consume events may be short on huge scenes.
        # Consuming event take up to ~4ms each
        # we are able to consume ~12 events

        # Detect "event" storm, basically stacked events casting pretty fast.

        if not (
                event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} or
                Keyboard.has(event)
        ):
            if _event_duration < self._event_duration:
                self._event_duration = 3 * _event_duration
                self._last_run = t
                logger.debug("Modal skip event to prevent overflow  %s %s" % (event.type, event.value))
                self._skipped_events += 1
                return self.pass_through(context, event)

        logger.debug("Modal skipped_events %s %.4f evt duration: %.4f" % (
            self._skipped_events,
            t - self._last_run,
            self._event_duration
        ))

        self._skipped_events = 0
        # Allow viewport navigation in industry compatible keymap mode
        # Prevent snap to values while dragging ..
        if (
                context.preferences.keymap.active_keyconfig == 'Industry_Compatible' and
                event.alt and 
                event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE'}
        ):
            logger.debug("Modal skip : Industry Compatible screen navigation")
            View.dirty = True
            return self.pass_through(context, event)

        logger.debug("%s   -- %s -- %s --  %s - %s  alt: %s  shift: %s  ctrl: %s" % (
            ModalAction.as_string(),
            Transform.get_action().transformtype,
            SpaceType.as_string(),
            event.type,
            event.value,
            event.alt,
            event.shift,
            event.ctrl
        ))

        # ------------------------
        # Mouse & keyboard events
        # ------------------------

        # Automatic Constraint with middle mouse, 2 steps
        if event.type == "MIDDLEMOUSE" and event.value == "PRESS":
            trs = Transform.get_action()
            if trs.active:
                Events.short_press()
                return self.pass_through(context, event)

        elif Events.short_release():
            # NOTE: when pass_through, RELEASE event may be hidden by blender
            # so we wait for any subsequent event (crap, but half work)
            trs = Transform.get_action()
            if trs.active:
                self.guess_axis(context, event)
                return self.running_modal(context, event)

        x, y, z = [Units.to_string(context, p) for p in self._detector.pos[0:3]]

        if DEBUG:
            trs = Transform.get_action()
            # self._preview_widget.pos = self._detector.pos
            self._debug.text = "x:%s y:%s  z:%s  %s -- %s -- %s" % (
                x, y, z,
                ModalAction.as_string(),
                SpaceType.as_string(),
                TransformType.as_string(trs.transformtype)
            )
        else:
            if SnapType.has(SnapType.GRID):
                grid = Geom3d.matrix_inverted(Space.grid)
                xg, yg, zg = [Units.to_string(context, p) for p in grid @ self._detector.pos]
                self._debug.text = "world: x:%s  y:%s  z:%s   grid: x:%s  y:%s  z:%s" % (x, y, z, xg, yg, zg)
            else:
                self._debug.text = "world: x:%s  y:%s  z:%s " % (x, y, z)
        self._debug.show()

        if Keyboard.has(event):
            return self.keyboard_event(context, event)

            # Pass mouse events to status bar
        elif Events.outside_region(context, event, test_ui=True):
            logger.debug("Modal skip : outside_region")
            return self.pass_through(context, event)

        # Cancel
        elif event.type in {'ESC', 'RIGHTMOUSE'}:

            if event.value == "PRESS":
                # passing False will cancel
                return self.confirm(context, event, False)

            return self.running_modal(context, event)

        elif event.type in {'LEFTMOUSE'}:

            if event.value == "PRESS":
                return self.mouse_press(context, event)

            elif event.value == "RELEASE":

                if ModalAction.has(ModalAction.SELECT):
                    ModalAction.disable(ModalAction.SELECT)
                    ModalAction.enable(ModalAction.HELPER)
                    self._selection_area.update(self._detector.pos)
                    self._selection_area.hide()
                    
                    # empty selection unless user press shift
                    if not event.shift and not event.alt:
                        SnapContext.exit()
                    
                    to_remove = []
                    
                    for helper in SnapHelpers.helpers():

                        if self._selection_area.in_area(helper):
                            
                            logger.info("found %s" % helper)
                            snapitem_type = None
                            coords = helper.world_coords
    
                            if helper.batch_type == BatchType.POINTS:
                                snapitem_type = SnapItemType.POINT
    
                            elif helper.batch_type == BatchType.LINES:
                                snapitem_type = SnapItemType.LINE
    
                            elif helper.batch_type == BatchType.TRIS:
                                snapitem_type = SnapItemType.TRI
    
                            if snapitem_type is not None:
                                snapitem = SnapItem(coords[0], coords, 0, snapitem_type, 0, helper.normal, 0, 0)
                                # ALT to remove items
                                if event.alt:
                                    index = SnapContext.index(snapitem)
                                    if index > -1:
                                        to_remove.append(index)
                                        
                                elif SnapContext.has_not(snapitem):
                                    SnapContext.add(snapitem)
                    
                    SnapContext.remove_by_index(to_remove)

                if self._release_confirm:
                    return self.confirm(context, event)

            return self.running_modal(context, event)

        elif event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:

            # when keyboard is active disallow mouse input
            # XXX allow edit mode so eg select a snap item ?
            trs = Transform.get_action()

            if trs.has_not(TransformType.KEYBOARD):
                self.mouse_move(context, event)

        elif (event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.ctrl) or \
                event.type in {'UP_ARROW', 'DOWN_ARROW'} and event.value == "PRESS":
            offset = -1
            if "UP" in event.type:
                offset = 1

            trs = Transform.get_action()
            if trs.active:
                # keep copy state to main trs in ALONG_SEGMENT mode for display in workspace tool
                _trs = trs
                if trs.has(ModalAction.has(ModalAction.ALONG_SEGMENT)):
                    trs = Transform.get_action(-2)

                # always reset step
                if (
                    ModalAction.has_not(ModalAction.WIDGET) or (
                        ModalAction.has(ModalAction.TRANSFORM) and
                        ModalAction.has(ModalAction.HELPER)
                    )
                ):
                    trs.steps = max(0, trs.steps + offset)
                    trs.state(TransformType.COPY, trs.steps > 0)
                    _trs.state(TransformType.COPY, trs.steps > 0)

                    if trs.has(TransformType.COPY):
                        # TODO: store current entered
                        Keyboard.entered = ""

                    Transform.update(context, event, self.snap_to, self.get_snapitem())

                else:
                    trs.steps = 0
                    trs.disable(TransformType.COPY)
                    _trs.disable(TransformType.COPY)

            return self.running_modal(context, event)

        return self.pass_through(context, event)

    @staticmethod
    def _clean_datablock(o, d):
        if d and d.users == 1:
            getattr(bpy.data, o.type.lower()).remove(d)

    @staticmethod
    def _make_unique_obdata(o):
        """Make object unique as we can't apply object's transform on shared data
        :param o:
        :return:
        """
        if o.data is not None and o.data.users > 1:
            o.data = o.data.copy()
            try:
                o.data.update_flag()
            except Exception:
                pass

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    def init_prefs_handler(self, context):
        prefs = Prefs.get(context)

        Transform.display_type = prefs.display_type

        self._release_confirm = prefs.release_confirm
        self._confirm_exit = prefs.confirm_exit
        # get undo event signature from active key config
        self._undo_signature = Keymap.signature(context, "ed.undo", "", "EMPTY")

        if prefs.absolute_scale:
            self._transform_type |= TransformType.ABSOLUTE

        if prefs.sanitize_scale:
            for o in context.visible_objects:
                if o.type in {"MESH", "CURVE"}:
                    self.sanitize_scale(context, o)

    def init_prefs(self, context):
        self.init_prefs_handler(context)

    def setup_widgets_handler(self, context):

        prefs = Prefs.get(context)
        # ---------------------
        # setup gl widgets
        # ---------------------

        self._cursor = Cursor(context)

        self._debug = Feedback(context)

        # Transform feedback text
        # self._feedback = Feedback(context)

        # Transform feedback
        self._rotation = Rotation(context)
        self._move = Move(context)
        self._scale = Scale(context)

        self._tooltip = ToolTips(context, (100, 0), 20)

        # set pos as reference so it magically update
        self._snap = Circle(Matrix(), prefs.color_snap, BatchType.LINES, 2 * prefs.snap_radius)
        self._snap.pos = self.snap_to

        # temporary display of context evaluations
        self._average = Cross(
            Matrix(), prefs.color_average, 0.707 * prefs.handle_size, 2 * prefs.line_width
        )

        self._context_preview_point = Cross(
            Matrix(), prefs.color_preview_context, 0.707 * prefs.handle_size, 2 * prefs.line_width
        )
        self._context_preview_line = Line(Matrix(), None, prefs.color_preview_context)
        self.hide_context_preview()

        self._selection_area = SelectArea()

        # Set as copy
        trs = Transform.get_action()
        self._pivot.matrix_world[:] = trs.space

        self._tripod = Tripod(context)

        # Grid matrix_world is a reference to Space.grid
        self._grid = Grid(context, Space.grid, GRID_STEPS)

        # Store blender's grid settings
        self.store_grid_visibility(context)

        if SnapType.has(SnapType.GRID):
            self.set_grid_visibility(context, True)

        # display detector.pos
        # self._preview_widget = Circle(Matrix(), (1, 0, 0, 1))
        # self._preview_widget.hide()

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_handler, (context,), 'WINDOW', 'POST_PIXEL'
        )

    def setup_widgets(self, context):
        self.setup_widgets_handler(context)

    def init_handler(self, context, event):
        prefs = Prefs.get(context)
        self.init_prefs(context)

        self._detector = Detector(context, event)
        self._pivot = Pivot(context, Space.get_user())

        SpaceType.set(SpaceType.NONE)

        # Init with local space (as copy as we do not want to move objects when editing the space)
        if context.active_object is not None:
            matrix_world = context.active_object.matrix_world

        elif context.selected_objects:
            matrix_world = context.selected_objects[0].matrix_world

        else:
            matrix_world = Space.matrix_world

        # Create a normalized copy as space is stored as reference at init time
        space = Geom3d.normalized(matrix_world)
        Transform.push(context, context.selected_objects, self._transform_type, space)

        # start reversed
        self._snap_to_self = not context.window_manager.slct.snap_to_self
        self.exclude_from_snap(context)

        self.setup_widgets(context)

        # When no space is set, use order.first
        if SpaceType.equals(SpaceType.NONE):
            self.toggle_space(context)
        
        if not prefs.keep_snap_on_start or SnapType.equals(SnapType.NONE):
            SnapType.from_enumproperty(prefs.snap_elements)

        # Set and orient pivot in BY_3_POINTS | ROTATE | SCALE modes
        if self._transform_type & (TransformType.ROTATE | TransformType.SCALE | TransformType.PINHOLE) > 0:
            ModalAction.set(ModalAction.BY_3_POINTS | ModalAction.TRANSFORM | ModalAction.PIVOT)
            space = self._pivot.matrix_world.copy()
            Transform.push(context, [self._pivot], TransformType.BY_3_POINTS | TransformType.MOVE, space)
            Transform.start(context, event, space.translation)

        # Always keep not exposed snap types
        SnapType.enable(self._default_snap_types)

        Events.init()

        logger.debug("%s" % SnapType.as_string())

    def init(self, context, event):
        self.init_handler(context, event)

    def invoke(self, context, event):

        if ModalAction.has(0xffff):
            # Only one instance running at time
            return {'FINISHED'}

        if context.area.type == 'VIEW_3D':

            logger.info("SLCT_main.invoke()")

            ModalAction.set(ModalAction.FREEMOVE)
            context.window.cursor_set("WAIT")

            self._skipped_events = 0
            self._last_event = time.time()
            self._event_duration = 0.008
            View.init(context, event)
            self.init(context, event)

            wm = context.window_manager
            wm.modal_handler_add(self)

            return {'RUNNING_MODAL'}

        else:
            # noinspection PyUnresolvedReferences
            self.report({'WARNING'}, "CAD Transform require 3d view")
            return {'CANCELLED'}


# noinspection PyPep8Naming
class SLCT_OT_move(SLCT_main, Operator):
    bl_idname = '%s.move' % __package__
    bl_label = '%s Move' % bl_info['name']
    default_shortcut = "G"

    _transform_type = TransformType.MOVE

    def tooltips(self, context, state) -> list:
        prefs = Prefs.get(context)
        return {
            "Pick start point": [
                (["MOUSE_LMB"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Exit"),
                (prefs.tip("EDIT_GRID")),
                (prefs.tip("EDIT_PIVOT")),
                (["EVENT_SHIFT", "MOUSE_LMB"], "Select / edit")
            ],
            "Pick destination": [
                (["MOUSE_LMB", "EVENT_RETURN"], "Confirm"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["ZERO"], "Enter distance"),
                (["EVENT_CTRL", "MOUSE_WHEEL", "UP_ARROW", "DOWN_ARROW"], "Copy"),
                (prefs.tip("LOCAL_GRID")),
                (["MOUSE_MMB_DRAG"], "Automatic Constraint"),
                (["EVENT_SHIFT", "MOUSE_MMB_DRAG"], "Automatic Constraint Plane")
            ]
        }[state]


# noinspection PyPep8Naming
class SLCT_OT_rotate(SLCT_main, Operator):
    bl_idname = '%s.rotate' % __package__
    bl_label = '%s Rotate' % bl_info['name']
    default_shortcut = "R"

    _transform_type = TransformType.ROTATE

    def init_prefs(self, context):
        prefs = Prefs.get(context)
        self._pivot_by_2_points = prefs.use_fast_rotation
        self._transform_after_pivot = prefs.use_fast_rotation
        self.init_prefs_handler(context)

    def tooltips(self, context, state) -> list:
        # prefs = Prefs.get(context)
        return {
            "Pick start point": [
                (["MOUSE_LMB"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Exit"),
                (["EVENT_X", "EVENT_Y", "EVENT_Z"], "Choose axis"),
                (["ZERO"], "Enter angle"),
                (["EVENT_SHIFT", "MOUSE_LMB"], "Select / edit")
            ],
            "Pick destination": [
                (["MOUSE_LMB", "EVENT_RETURN"], "Confirm"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["EVENT_SHIFT"], "Round (hold)"),
                (["EVENT_ALT", "EVENT_SHIFT"], "Round small (hold)"),
                (["EVENT_CTRL", "MOUSE_WHEEL", "UP_ARROW", "DOWN_ARROW"], "Copy"),
                (["ZERO"], "Enter angle"),
                (["EVENT_X", "EVENT_Y", "EVENT_Z"], "Choose axis"),
                (["MOUSE_MMB_DRAG"], "Automatic Constraint"),
                (["EVENT_SHIFT", "MOUSE_MMB_DRAG"], "Automatic Constraint Plane")
            ]
        }[state]


# noinspection PyPep8Naming
class SLCT_OT_scale(SLCT_main, Operator):
    bl_idname = '%s.scale' % __package__
    bl_label = '%s Scale' % bl_info['name']
    default_shortcut = "S"

    _transform_type = TransformType.SCALE

    def init_prefs(self, context):
        prefs = Prefs.get(context)
        self._pivot_by_2_points = prefs.use_fast_scale
        self._transform_after_pivot = prefs.use_fast_scale
        self.init_prefs_handler(context)

    def tooltips(self, context, state) -> list:
        prefs = Prefs.get(context)
        return {
            "Pick start point": [
                (["MOUSE_LMB"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Exit"),
                (prefs.tip("EDIT_GRID")),
                (["EVENT_SHIFT", "MOUSE_LMB"], "Select / edit")
            ],
            "Pick destination": [
                (["MOUSE_LMB", "EVENT_RETURN"], "Confirm"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["EVENT_ALT"], "Uniform scale"),
                (["ZERO"], "Enter factor / distance"),
                (prefs.tip("LOCAL_GRID")),
                (["MOUSE_MMB_DRAG"], "Automatic Constraint"),
                (["EVENT_SHIFT", "MOUSE_MMB_DRAG"], "Automatic Constraint Plane")
            ]
        }[state]





# noinspection PyPep8Naming
class SLCT_OT_pinhole(SLCT_main, Operator):
    bl_idname = '%s.pinhole' % __package__
    bl_label = '%s Pinhole' % bl_info['name']
    default_shortcut = "P"

    _transform_type = TransformType.PINHOLE

    def init_prefs(self, context):
        prefs = Prefs.get(context)
        self._pivot_by_2_points = True
        self._transform_after_pivot = True
        self.init_prefs_handler(context)

    def tooltips(self, context, state) -> list:
        # prefs = Prefs.get(context)
        return {
            "Pick start point": [
                (["MOUSE_LMB"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Exit"),
                (["EVENT_X", "EVENT_Y", "EVENT_Z"], "Choose axis"),
                (["EVENT_SHIFT", "MOUSE_LMB"], "Select / edit")
            ],
            "Pick destination": [
                (["MOUSE_LMB", "EVENT_RETURN"], "Confirm"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["EVENT_SHIFT"], "Round (hold)"),
                (["EVENT_ALT", "EVENT_SHIFT"], "Round small (hold)"),
                (["EVENT_CTRL", "MOUSE_WHEEL", "UP_ARROW", "DOWN_ARROW"], "Copy"),
                (["EVENT_X", "EVENT_Y", "EVENT_Z"], "Choose axis"),
                (["MOUSE_MMB_DRAG"], "Automatic Constraint"),
                (["EVENT_SHIFT", "MOUSE_MMB_DRAG"], "Automatic Constraint Plane")
            ]
        }[state]


# noinspection PyPep8Naming
class SLCT_OT_align(SLCT_main, Operator):
    bl_idname = '%s.align' % __package__
    bl_label = '%s Align' % bl_info['name']
    default_shortcut = "L"

    _transform_type = TransformType.BY_3_POINTS | TransformType.APPLY_STEP

    def init(self, context, event):
        self.init_handler(context, event)
        # Transform pivot with selection and retrieve as active_object
        sel = [self._pivot]
        sel.extend(context.selected_objects)
        Transform.push(context, sel, self._transform_type, Space.get_user())
        Transform.make_first_object_active()
        Transform.pop(0)

        # Start by "Pivot by 3 points"
        ModalAction.set(ModalAction.BY_3_POINTS | ModalAction.TRANSFORM | ModalAction.PIVOT)
        space = self._pivot.matrix_world.copy()
        Transform.push(context, [self._pivot], TransformType.BY_3_POINTS | TransformType.MOVE, space)
        Transform.start(context, event, space.translation.copy())

    def confirm(self, context, event, confirm: bool = True):

        has_by_3_points = ModalAction.has(ModalAction.BY_3_POINTS)
        can_exit = self.confirm_handler(context, event, confirm)
        # cancel = not confirm

        trs, transformable = Transform.get_active()

        # Geom3d.debug(trs.space, "confirm: trs.space")
        # Geom3d.debug(self._pivot.matrix_world, "confirm: _pivot.matrix_world")

        if trs.has(TransformType.BY_3_POINTS) and not has_by_3_points:

            trs.constraint = ConstraintType.NONE

            # on cancel: FREEMOVE
            if confirm:
                if event.shift:
                    # Confirm and exit
                    Transform.apply_final()
                    trs.space = transformable.matrix_step
                    # Geom3d.debug(trs.space, "confirm and quit: trs.space")

                    Transform.hide()
                else:
                    # Confirm and start next action, set TRANSFORM to chain
                    ModalAction.disable(ModalAction.FREEMOVE)
                    ModalAction.enable(ModalAction.TRANSFORM)
                    Transform.show()

            else:
                # Cancel and exit
                Transform.hide()

            if confirm:
                if trs.has(TransformType.MOVE):
                    trs.disable(TransformType.MOVE)
                    if not event.shift:
                        # start x axis orientation
                        trs.enable(TransformType.PINHOLE)
                        trs.space = transformable.matrix_step
                        snap_from = trs.space.translation + trs.space.col[0].xyz
                        Transform.start(context, event, snap_from, self.get_snapitem())

                elif trs.has(TransformType.PINHOLE):
                    trs.disable(TransformType.PINHOLE)
                    if not event.shift:
                        # start y rotation about x axis
                        trs.enable(TransformType.ROTATE)
                        trs.constraint = ConstraintType.PLANE | ConstraintType.X
                        trs.space = transformable.matrix_step
                        snap_from = trs.space.translation + trs.space.col[1].xyz
                        Transform.start(context, event, snap_from, self.get_snapitem())

                elif trs.has(TransformType.ROTATE):
                    trs.disable(TransformType.ROTATE)
                    # Confirm and exit
                    Transform.apply_final()
                    trs.space = transformable.matrix_step
                    ModalAction.disable(ModalAction.TRANSFORM)
                    ModalAction.enable(ModalAction.FREEMOVE)
                    Transform.hide()

                Space.set_user(transformable.matrix_step)

            ConstraintType.set(trs.constraint)

        # Exit on cancel / or if confirm_exit
        if can_exit or (confirm and Transform.done and self._confirm_exit):
            if confirm:
                return self.finished(context)
            else:
                return self.cancelled(context)

        return self.running_modal(context, event)

    def tooltips(self, context, state) -> list:

        prefs = Prefs.get(context)
        trs = Transform.get_action()

        _state = "Pick start point"

        if trs.has(TransformType.MOVE):
            _state = "move"
        elif trs.has(TransformType.PINHOLE):
            _state = "Orient x axis"
        elif trs.has(TransformType.ROTATE):
            _state = "Orient y axis"

        return {
            "Pick start point": [
                (["MOUSE_LMB"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Exit")
            ],
            "move": [
                (["MOUSE_LMB"], "Confirm and orient x axis"),
                (["MOUSE_LMB", "EVENT_SHIFT"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel")
            ],
            "Orient x axis": [
                (["MOUSE_LMB"], "Confirm and orient y axis"),
                (["MOUSE_LMB", "EVENT_SHIFT"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["ZERO"], "Enter value"),
                (prefs.tip("LOCAL_GRID")),
                (["EVENT_SHIFT", "EVENT_X", "EVENT_Y", "EVENT_Z"], "Constraint to plane")
            ],
            "Orient y axis": [
                (["MOUSE_LMB"], "Confirm"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["ZERO"], "Enter value"),
                (prefs.tip("LOCAL_GRID")),
            ]
        }[_state]

    def set_tooltip(self, context, event, header: str = None):
        trs = Transform.get_action()

        action = self.get_tooltip_action(event, trs)
        state = self.get_tooltip_state(event, trs, action)

        _header = "Align object"

        header = self.get_tooltip_header(event, _header)

        if self._last_tip == (header, action, state):
            return

        prefs = Prefs.get(context)
        if prefs.show_tooltips:
            self._tooltip.show()

        tips = self.get_tips(context, action, state)

        self._last_tip = (header, action, state)

        self._tooltip.replace(context, header, state, tips)


# noinspection PyPep8Naming
class SLCT_OT_adjust(SLCT_main, Operator):
    bl_idname = '%s.adjust' % __package__
    bl_label = '%s Adjust' % bl_info['name']
    default_shortcut = "D"

    _transform_type = TransformType.BY_3_POINTS | TransformType.APPLY_STEP

    _ref = Vector((1.0, 1.0, 1.0))

    def init(self, context, event):
        self.init_handler(context, event)
        # Transform pivot with selection and retrieve as active_object
        sel = [self._pivot]
        sel.extend(context.selected_objects)
        Transform.push(context, sel, self._transform_type, Space.get_user())
        Transform.make_first_object_active()
        Transform.pop(0)

        # Start by "Pivot by 3 points"
        ModalAction.set(ModalAction.BY_3_POINTS | ModalAction.TRANSFORM | ModalAction.PIVOT)
        space = self._pivot.matrix_world.copy()
        Transform.push(context, [self._pivot], TransformType.BY_3_POINTS | TransformType.MOVE, space)
        Transform.start(context, event, space.translation.copy())

    def mouse_move(self, context, event):
        self.mouse_move_handler(context, event)
        trs, transformable = Transform.get_active()

        if trs.has(TransformType.SCALE):
            self._scale.update(context)
            self._scale.show()
            self._move.hide()
            self._rotation.hide()

        if ModalAction.has(ModalAction.BY_3_POINTS):
            # retrieve ref x y from picked points while setting up pivot
            if trs.transformtype & TransformType.PINHOLE:
                self._ref.x = (Geom3d.matrix_inverted(trs.space) @ trs.snap_to).x
            elif trs.transformtype & TransformType.ROTATE:
                self._ref.y = (Geom3d.matrix_inverted(trs.space) @ trs.snap_to).y

    def confirm(self, context, event, confirm: bool = True):

        has_by_3_points = ModalAction.has(ModalAction.BY_3_POINTS)
        can_exit = self.confirm_handler(context, event, confirm)

        trs, transformable = Transform.get_active()

        if trs.has(TransformType.BY_3_POINTS) and not has_by_3_points:

            trs.constraint = ConstraintType.NONE

            # on cancel: FREEMOVE
            if confirm:
                if event.shift:
                    # Confirm and exit
                    Transform.apply_final()
                    trs.space = transformable.matrix_step
                    Transform.hide()
                else:
                    # Confirm and start next action, set TRANSFORM to chain
                    ModalAction.disable(ModalAction.FREEMOVE)
                    ModalAction.enable(ModalAction.TRANSFORM)
                    Transform.show()
            else:
                # Cancel and exit
                Transform.hide()

            if confirm:
                if trs.has(TransformType.MOVE):
                    trs.disable(TransformType.MOVE)

                    if not event.shift:
                        # start x axis orientation
                        trs.enable(TransformType.PINHOLE)
                        trs.space = transformable.matrix_step
                        snap_from = trs.space.translation + trs.space.col[0].xyz
                        Transform.start(context, event, snap_from, self.get_snapitem())

                elif trs.has(TransformType.PINHOLE):
                    trs.disable(TransformType.PINHOLE)
                    if not event.shift:
                        # start y rotation about x axis
                        trs.enable(TransformType.ROTATE)
                        trs.constraint = ConstraintType.PLANE | ConstraintType.X
                        trs.space = transformable.matrix_step
                        snap_from = trs.space.translation + trs.space.col[1].xyz
                        Transform.start(context, event, snap_from, self.get_snapitem())

                elif trs.has(TransformType.ROTATE):
                    trs.disable(TransformType.ROTATE)
                    if not event.shift:
                        trs.enable(TransformType.SCALE)
                        trs.constraint = ConstraintType.PLANE | ConstraintType.Z
                        trs.space = transformable.matrix_step
                        snap_from = (
                            trs.space.translation +
                            self._ref.x * trs.space.col[0].xyz +
                            self._ref.y * trs.space.col[1].xyz
                        )
                        Transform.start(context, event, snap_from, self.get_snapitem())

                elif trs.has(TransformType.SCALE):
                    trs.disable(TransformType.SCALE)
                    # Confirm and exit
                    Transform.apply_final()
                    trs.space = transformable.matrix_step
                    ModalAction.disable(ModalAction.TRANSFORM)
                    ModalAction.enable(ModalAction.FREEMOVE)
                    Transform.hide()

                Space.set_user(transformable.matrix_step)

            ConstraintType.set(trs.constraint)

        # Exit on cancel / or if confirm_exit
        if can_exit or (confirm and Transform.done and self._confirm_exit):
            if confirm:
                return self.finished(context)
            else:
                return self.cancelled(context)

        return self.running_modal(context, event)

    def tooltips(self, context, state) -> list:

        prefs = Prefs.get(context)
        trs = Transform.get_action()

        _state = "Pick start point"

        if trs.has(TransformType.MOVE):
            _state = "move"
        elif trs.has(TransformType.PINHOLE):
            _state = "Orient x axis"
        elif trs.has(TransformType.ROTATE):
            _state = "Orient y axis"
        elif trs.has(TransformType.SCALE):
            _state = "Scale"

        return {
            "Pick start point": [
                (["MOUSE_LMB"], "Confirm and start"),
                (["MOUSE_RMB", "EVENT_ESC"], "Exit")
            ],
            "move": [
                (["MOUSE_LMB"], "Confirm and orient x axis"),
                (["MOUSE_LMB", "EVENT_SHIFT"], "Confirm and exit"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel")
            ],
            "Orient x axis": [
                (["MOUSE_LMB"], "Confirm and orient y axis"),
                (["MOUSE_LMB", "EVENT_SHIFT"], "Confirm and exit"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["ZERO"], "Enter value"),
                (prefs.tip("LOCAL_GRID")),
                (["EVENT_SHIFT", "EVENT_X", "EVENT_Y", "EVENT_Z"], "Constraint to plane")
            ],
            "Orient y axis": [
                (["MOUSE_LMB"], "Confirm and adjust scale"),
                (["MOUSE_LMB", "EVENT_SHIFT"], "Confirm and exit"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["ZERO"], "Enter value"),
                (prefs.tip("LOCAL_GRID")),
            ],
            "Scale": [
                (["MOUSE_LMB"], "Confirm"),
                (["MOUSE_RMB", "EVENT_ESC"], "Cancel"),
                (["ZERO"], "Enter value"),
                (prefs.tip("LOCAL_GRID")),
                (["EVENT_X", "EVENT_Y", "EVENT_Z"], "Constraint to axis"),
                (["EVENT_SHIFT", "EVENT_X", "EVENT_Y", "EVENT_Z"], "Constraint to plane")
            ]
        }[_state]

    def set_tooltip(self, context, event, header: str = None):
        trs = Transform.get_action()

        action = self.get_tooltip_action(event, trs)
        state = self.get_tooltip_state(event, trs, action)

        _header = "Align object"

        header = self.get_tooltip_header(event, _header)

        if self._last_tip == (header, action, state):
            return

        prefs = Prefs.get(context)
        if prefs.show_tooltips:
            self._tooltip.show()

        tips = self.get_tips(context, action, state)

        self._last_tip = (header, action, state)

        self._tooltip.replace(context, header, state, tips)




operators = (
    SLCT_OT_move,
    SLCT_OT_rotate,
    SLCT_OT_scale,
    
    SLCT_OT_pinhole,
    SLCT_OT_align,
    SLCT_OT_adjust
    
    )
