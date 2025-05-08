# Copyright (C) 2025 Belaid Ziane

# ***** BEGIN GPL LICENSE BLOCK ****
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ***** END GPL LICENSE BLOCK *****

bl_info = {
    "name": "Measure and Scale",
    "author": "Bill3D(Belaid Ziane)",
    "version": (1, 1, 2), 
    "blender": (4, 2, 0),
    "location": "View3D > UI > Npanel > Item > Measure and Scale",
    "description": "Interactively measure between two vertices, scale the object uniformly to a target dimension.",
    "category": "Object",
}
import bpy
import bmesh
import gpu
import blf
from mathutils import Vector, Matrix
from bpy.types import Operator, Panel, PropertyGroup, Scene
from bpy.props import (
    FloatProperty, StringProperty, PointerProperty, EnumProperty,
    FloatVectorProperty, BoolProperty
)
import bpy_extras.view3d_utils
from gpu_extras.batch import batch_for_shader

# Constants
MAX_SNAP_DISTANCE_SCREEN = 25.0
MAX_3D_SNAP_VALIDATION_DIST_SQ = 0.5**2 # Max squared distance in world space for vertex validation
SNAP_POINT_SIZE = 10.0

# Unit Conversion Constants
METERS_TO_CM = 100.0
METERS_TO_MM = 1000.0
METERS_TO_FEET = 3.28084
METERS_TO_INCHES = 39.3701
FEET_TO_INCHES = 12.0

# Property Group for Settings
class ScaleInteractiveSettings(PropertyGroup):
    metric_unit: EnumProperty(
        name="Metric Unit",
        items=[
            ('M', "m", "Meters"),
            ('CM', "cm", "Centimeters"),
            ('MM', "mm", "Millimeters"),
        ],
        default='M',
        description="Select the metric unit for display"
    )
    system_unit: EnumProperty(
        name="System",
        items=[
            ('METRIC', "Metric", "Use Metric units (m, cm, mm)"),
            ('IMPERIAL_FT', "ft", "Use Imperial units (Feet)"),
            ('IMPERIAL_IN', "in", "Use Imperial units (Inches)"),
        ],
        default='METRIC',
        description="Select the unit system for display"
    )
    decimal_precision: EnumProperty(
        name="Precision",
        items=[
            ('0', "0", "No decimal places (e.g., 5)"),
            ('1', "0.0", "One decimal place (e.g., 5.3)"),
            ('2', "0.00", "Two decimal places (e.g., 5.32)"),
            ('3', "0.000", "Three decimal places (e.g., 5.321)"),
            ('4', "0.0000", "Four decimal places (e.g., 5.3214)"),
        ],
        default='2',
        description="Set the number of decimal places to display"
    )

# Unit Conversion Functions
def get_unit_suffix(settings):
    """Returns the appropriate unit suffix string based on settings."""
    if settings.system_unit == 'METRIC':
        return settings.metric_unit.lower()
    elif settings.system_unit == 'IMPERIAL_FT':
        return 'ft'
    elif settings.system_unit == 'IMPERIAL_IN':
        return 'in'
    return ''

def convert_to_display_unit(value_meters, settings):
    """Converts a value from meters to the selected display unit."""
    if settings.system_unit == 'METRIC':
        if settings.metric_unit == 'CM':
            return value_meters * METERS_TO_CM
        elif settings.metric_unit == 'MM':
            return value_meters * METERS_TO_MM
        else: # 'M'
            return value_meters
    elif settings.system_unit == 'IMPERIAL_FT':
        return value_meters * METERS_TO_FEET
    elif settings.system_unit == 'IMPERIAL_IN':
        return value_meters * METERS_TO_INCHES
    return value_meters

def convert_from_display_unit(value_display, settings):
    """Converts a value from the selected display unit back to meters."""
    if settings.system_unit == 'METRIC':
        if settings.metric_unit == 'CM':
            return value_display / METERS_TO_CM
        elif settings.metric_unit == 'MM':
            return value_display / METERS_TO_MM
        else: # 'M'
            return value_display
    elif settings.system_unit == 'IMPERIAL_FT':
        return value_display / METERS_TO_FEET
    elif settings.system_unit == 'IMPERIAL_IN':
        return value_display / METERS_TO_INCHES
    return value_display

# Helper Functions
def ray_cast(context, position):
    """Raycast from screen position into 3D space"""
    region = context.region
    region3D = context.space_data.region_3d
    if not region or not region3D:
        return False, None, None, -1, None, None, None
    view_point = bpy_extras.view3d_utils.region_2d_to_origin_3d(region, region3D, position)
    view_vector = bpy_extras.view3d_utils.region_2d_to_vector_3d(region, region3D, position)
    depsgraph = context.evaluated_depsgraph_get()
    result, location, normal, index, object_hit, matrix = \
        context.scene.ray_cast(depsgraph, view_point, view_vector)
    return result, location, normal, index, object_hit, matrix, view_point

def find_nearest_vertex_world(context, event, obj):
    """Find nearest visible vertex on the base mesh using improved snapping logic"""
    mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))
    region = context.region
    rv3d = context.space_data.region_3d
    if not region or not rv3d:
        return None

    ray_result, ray_hit_loc, _, _, hit_obj, _, _ = ray_cast(context, mouse_pos)

    min_dist_sq_screen = MAX_SNAP_DISTANCE_SCREEN**2
    nearest_vert_co = None

    mesh = obj.data
    if not mesh or not mesh.vertices:
        return None

    world_matrix = obj.matrix_world
    verts = mesh.vertices

    for v in verts:
        world_co = world_matrix @ v.co

        if ray_result and hit_obj == obj:
            if (world_co - ray_hit_loc).length_squared > MAX_3D_SNAP_VALIDATION_DIST_SQ:
                continue

        try:
            screen_co = bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, world_co)
        except (TypeError, ReferenceError):
            screen_co = None

        if screen_co:
            dist_sq = (screen_co - mouse_pos).length_squared
            if dist_sq < min_dist_sq_screen:
                min_dist_sq_screen = dist_sq
                nearest_vert_co = world_co

    return nearest_vert_co

# Drawing Callback
def draw_callback_px(op, context):
    if not context.area or not op:
        return

    settings = context.scene.scale_interactive_settings
    font_id = 0
    blf.size(font_id, 14)
    precision = int(settings.decimal_precision) # Get precision

    start_co = op.start_vertex_co if op.has_start_vertex else None
    end_co = op.end_vertex_co if op.has_end_vertex else None
    hover_co = op._hover_vertex_co
    mouse_pos = op._current_mouse_pos

    screen_start_co, screen_end_co, screen_hover_co = None, None, None
    rv3d = context.space_data.region_3d if context.space_data else None
    if not rv3d: return

    # Project 3D points to 2D screen space
    if start_co:
        try: screen_start_co = bpy_extras.view3d_utils.location_3d_to_region_2d(context.region, rv3d, start_co)
        except (TypeError, ReferenceError, AttributeError): pass
    if end_co:
        try: screen_end_co = bpy_extras.view3d_utils.location_3d_to_region_2d(context.region, rv3d, end_co)
        except (TypeError, ReferenceError, AttributeError): pass
    if hover_co and not end_co:
        try: screen_hover_co = bpy_extras.view3d_utils.location_3d_to_region_2d(context.region, rv3d, hover_co)
        except (TypeError, ReferenceError, AttributeError): pass

    # Draw Visuals using GPU module
    shader = op._shader
    if not shader: return
    shader.bind()

    # Draw Hover Point (Orange)
    if screen_hover_co:
        shader.uniform_float("color", (1.0, 0.5, 0.0, 1.0))
        gpu.state.point_size_set(SNAP_POINT_SIZE)
        batch = batch_for_shader(shader, 'POINTS', {"pos": [screen_hover_co]})
        batch.draw(shader)

    # Draw Start Point (Green)
    if screen_start_co:
        shader.uniform_float("color", (0.0, 1.0, 0.0, 1.0))
        gpu.state.point_size_set(SNAP_POINT_SIZE + 2)
        batch = batch_for_shader(shader, 'POINTS', {"pos": [screen_start_co]})
        batch.draw(shader)

    # Draw End Point (Red)
    if screen_end_co:
        shader.uniform_float("color", (1.0, 0.0, 0.0, 1.0))
        gpu.state.point_size_set(SNAP_POINT_SIZE + 2)
        batch = batch_for_shader(shader, 'POINTS', {"pos": [screen_end_co]})
        batch.draw(shader)

    gpu.state.point_size_set(1)

    # Draw Lines and Text
    line_drawn = False
    if screen_start_co:
        # Draw Final Measurement Line (Blue)
        if screen_end_co:
            shader.uniform_float("color", (0.53, 0.81, 0.92, 1.0))
            gpu.state.line_width_set(3.0)
            gpu.state.blend_set('ALPHA')
            batch = batch_for_shader(shader, 'LINES', {"pos": [screen_start_co, screen_end_co]})
            batch.draw(shader)
            line_drawn = True

            # Display Measured Distance Text
            measured_distance = op.measured_distance
            if measured_distance > 0.0001:
                text_pos = (Vector(screen_start_co) + Vector(screen_end_co)) / 2.0
                display_distance = convert_to_display_unit(measured_distance, settings)
                unit_suffix = get_unit_suffix(settings)
                # Check if the rounded value differs from the actual value
                rounded_display = round(display_distance, precision)
                high_precision = round(display_distance, precision + 2)
                prefix = "~" if abs(rounded_display - high_precision) > 0.0001 else ""
                blf.position(font_id, text_pos.x + 10, text_pos.y + 10, 0)
                blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
                blf.draw(font_id, f"{prefix}{rounded_display:.{precision}f} {unit_suffix}")

        # Draw Dynamic Line to Mouse/Hover (Gray)
        elif mouse_pos:
            target_screen_pos = mouse_pos
            dynamic_distance = 0.0
            if screen_hover_co:
                target_screen_pos = screen_hover_co
                if hover_co and start_co:
                    dynamic_distance = (hover_co - start_co).length

            shader.uniform_float("color", (0.8, 0.8, 0.8, 0.9))
            gpu.state.line_width_set(2.0)
            gpu.state.blend_set('ALPHA')
            batch = batch_for_shader(shader, 'LINES', {"pos": [screen_start_co, target_screen_pos]})
            batch.draw(shader)
            line_drawn = True

            # Display Dynamic Distance Text (if hovering)
            if dynamic_distance > 0.0001:
                text_pos = (Vector(screen_start_co) + Vector(target_screen_pos)) / 2.0
                display_dynamic_distance = convert_to_display_unit(dynamic_distance, settings)
                unit_suffix = get_unit_suffix(settings)
                # Check if the rounded value differs from the actual value
                rounded_display = round(display_dynamic_distance, precision)
                high_precision = round(display_dynamic_distance, precision + 2)
                prefix = "~" if abs(rounded_display - high_precision) > 0.0001 else ""
                blf.position(font_id, text_pos.x + 10, text_pos.y + 10, 0)
                blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
                blf.draw(font_id, f"{prefix}{rounded_display:.{precision}f} {unit_suffix}")

    # Reset GPU State
    if line_drawn:
        gpu.state.blend_set('NONE')
        gpu.state.line_width_set(1.0)

    # Draw Status Text
    blf.position(font_id, 20, 30, 0)
    blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
    blf.draw(font_id, op.status_message)

# Main Operator
class OBJECT_OT_ScaleToDimensionInteractive(Operator):
    bl_idname = "object.scale_to_dimension_interactive"
    bl_label = "Measure and Scale Interactive"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator Properties
    start_vertex_co: FloatVectorProperty(name="Start Vertex", size=3, subtype='XYZ', unit='LENGTH')
    end_vertex_co: FloatVectorProperty(name="End Vertex", size=3, subtype='XYZ', unit='LENGTH')
    measured_distance: FloatProperty(name="Measured Distance", default=0.0, unit='LENGTH')
    object_name: StringProperty(name="Object Name")
    original_mode: StringProperty(name="Original Mode")
    status_message: StringProperty(name="Status Message", default="Click first vertex (ESC to cancel)")
    has_start_vertex: BoolProperty(default=False)
    has_end_vertex: BoolProperty(default=False)

    # Internal instance variables
    _draw_handle = None
    _shader = None
    _current_mouse_pos = None
    _hover_vertex_co = None
    _original_wireframe_state = None
    _wireframe_changed_by_op = False

    # Class variable for dialog completion signal
    _dialog_completed_successfully = False

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Active space must be a 3D View")
            return {'CANCELLED'}

        if OBJECT_OT_ScaleToDimensionInteractive._draw_handle is not None:
             self.report({'WARNING'}, "Interactive scale operation might already be in progress.")
             self._cleanup(context)
             return {'CANCELLED'}

        active_obj = context.active_object
        if not active_obj:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}
        if active_obj.type != 'MESH':
            self.report({'WARNING'}, "Active object must be a Mesh")
            return {'CANCELLED'}

        # Initialize Operator State
        self.object_name = active_obj.name
        self.original_mode = context.mode
        self.measured_distance = 0.0
        self.has_start_vertex = False
        self.has_end_vertex = False
        self.start_vertex_co = (0, 0, 0)
        self.end_vertex_co = (0, 0, 0)
        self.status_message = "Click first vertex (ESC to cancel)"
        self._current_mouse_pos = None
        self._hover_vertex_co = None
        self._wireframe_changed_by_op = False
        OBJECT_OT_ScaleToDimensionInteractive._dialog_completed_successfully = False

        # Manage Wireframe Overlay
        space_data = context.space_data
        self._original_wireframe_state = None
        if space_data and hasattr(space_data, 'overlay'):
            try:
                self._original_wireframe_state = space_data.overlay.show_wireframes
                if not self._original_wireframe_state:
                    space_data.overlay.show_wireframes = True
                    self._wireframe_changed_by_op = True
            except AttributeError:
                 print(f"{self.bl_idname}: Warning: Could not access space_data.overlay.")
            except Exception as e:
                 print(f"{self.bl_idname}: Error accessing wireframe state: {e}")
        else:
            print(f"{self.bl_idname}: Warning: context.space_data not available.")

        # Setup Drawing
        self._shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        args = (self, context)
        try:
            OBJECT_OT_ScaleToDimensionInteractive._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
            self._draw_handle = OBJECT_OT_ScaleToDimensionInteractive._draw_handle
        except Exception as e:
            self.report({'ERROR'}, f"Failed to add draw handler: {e}")
            self._cleanup(context)
            return {'CANCELLED'}

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        # Check for completion signal from dialog
        if OBJECT_OT_ScaleToDimensionInteractive._dialog_completed_successfully:
            OBJECT_OT_ScaleToDimensionInteractive._dialog_completed_successfully = False
            return self.finish(context)

        if not OBJECT_OT_ScaleToDimensionInteractive._draw_handle:
             return {'FINISHED'} # Already cleaned up

        if not context.area:
            return self._cancel_and_cleanup(context)

        context.area.tag_redraw()

        obj = context.scene.objects.get(self.object_name)
        if not obj:
            self.report({'WARNING'}, "Original object lost!")
            return self._cancel_and_cleanup(context)
        if obj.type != 'MESH':
            self.report({'WARNING'}, "Object is no longer a mesh.")
            return self._cancel_and_cleanup(context)

        # Event Handling
        if event.type == 'MOUSEMOVE':
            if not self.has_end_vertex:
                self._current_mouse_pos = (event.mouse_region_x, event.mouse_region_y)
                self._hover_vertex_co = find_nearest_vertex_world(context, event, obj)
            else:
                self._current_mouse_pos = None
                self._hover_vertex_co = None

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not self.has_end_vertex:
                click_co = find_nearest_vertex_world(context, event, obj)
                if click_co:
                    if not self.has_start_vertex:
                        self.start_vertex_co = click_co
                        self.has_start_vertex = True
                        self.status_message = "Click second vertex (ESC to cancel)"
                        self._hover_vertex_co = None
                    else:
                        if (click_co - Vector(self.start_vertex_co)).length < 0.0001:
                            self.report({'INFO'}, "Second point too close to the first.")
                            return {'RUNNING_MODAL'}

                        self.end_vertex_co = click_co
                        self.has_end_vertex = True
                        self.measured_distance = (Vector(self.end_vertex_co) - Vector(self.start_vertex_co)).length
                        self.status_message = "Dialog Open - Enter Target Dimension"
                        self._current_mouse_pos = None
                        self._hover_vertex_co = None

                        context.area.tag_redraw()

                        # Invoke Dialog
                        bpy.ops.object.scale_confirm_dialog('INVOKE_DEFAULT',
                            measured_distance=self.measured_distance,
                            object_name=self.object_name,
                            original_mode=self.original_mode)
                        return {'PASS_THROUGH'}
                else:
                    self.report({'INFO'}, "No vertex found near cursor.")
                    return {'RUNNING_MODAL'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.report({'INFO'}, "Interactive scaling cancelled.")
            return self._cancel_and_cleanup(context)

        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} or \
             (event.type == 'MOUSEMOVE' and event.alt and not event.ctrl and not event.shift) or \
             event.type in {'ROTATE', 'MOVE', 'ZOOM'} or \
             (event.type == 'TIMER'):
             return {'PASS_THROUGH'} # Pass Through Navigation

        return {'RUNNING_MODAL'}

    def _restore_wireframe(self, context):
        """Helper to restore wireframe if it was changed by this operator."""
        if self._wireframe_changed_by_op and self._original_wireframe_state is False:
            if context and context.space_data and hasattr(context.space_data, 'overlay'):
                try:
                    if context.space_data.overlay.show_wireframes is True:
                         context.space_data.overlay.show_wireframes = False
                         print(f"{self.bl_idname}: Restored wireframe overlay to OFF.")
                except Exception as e:
                    print(f"{self.bl_idname}: Info: Error restoring wireframe state during cleanup: {e}")
            else:
                 print(f"{self.bl_idname}: Info: Could not restore wireframe - context/space_data unavailable.")
        self._wireframe_changed_by_op = False
        self._original_wireframe_state = None

    def _cleanup(self, context):
        """Remove draw handler and restore wireframe."""
        handle = OBJECT_OT_ScaleToDimensionInteractive._draw_handle
        if handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
            except ValueError: pass # Handle case where it might already be removed
            except Exception as e: print(f"{self.bl_idname}: Info: Error removing draw handler during cleanup: {e}")
            finally:
                OBJECT_OT_ScaleToDimensionInteractive._draw_handle = None
                self._draw_handle = None

        self._restore_wireframe(context)

        # Clear instance variables
        self._shader = None
        self._current_mouse_pos = None
        self._hover_vertex_co = None

        if context and context.area:
            context.area.tag_redraw()

    def _cancel_and_cleanup(self, context):
        """Cancel operation and perform cleanup."""
        self._cleanup(context)
        return {'CANCELLED'}

    def finish(self, context):
        """Finish operation and perform cleanup."""
        self._cleanup(context)
        return {'FINISHED'}

# Dialog Operator
class OBJECT_OT_ScaleConfirmDialog(Operator):
    bl_idname = "object.scale_confirm_dialog"
    bl_label = "Set Target Dimension"
    bl_options = {'REGISTER', 'INTERNAL'}

    # Properties passed from the calling operator
    measured_distance: FloatProperty(name="Measured Distance", default=0.0, options={'HIDDEN'})
    object_name: StringProperty(name="Object Name", default="", options={'HIDDEN'})
    original_mode: StringProperty(name="Original Mode", default="OBJECT", options={'HIDDEN'})

    # Property for user input
    target_dimension: FloatProperty(
        name="Target Dimension",
        description="Enter the desired dimension in the selected units",
        default=1.0,
        min=0.00001,
        soft_min=0.01
    )

    def invoke(self, context, event):
        settings = context.scene.scale_interactive_settings
        if self.measured_distance > 0.0001:
            self.target_dimension = convert_to_display_unit(self.measured_distance, settings)
        else:
            self.target_dimension = 1.0

        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=300)

    def draw(self, context):
        layout = self.layout
        settings = context.scene.scale_interactive_settings
        col = layout.column()
        precision = int(settings.decimal_precision) # Get precision

        # Display Measured Distance (read-only)
        row = col.row()
        row.label(text="Measured Distance:")
        display_measured_dist = convert_to_display_unit(self.measured_distance, settings)
        unit_suffix = get_unit_suffix(settings)
        # Check if the rounded value differs from the actual value
        rounded_display = round(display_measured_dist, precision)
        high_precision = round(display_measured_dist, precision + 2)
        prefix = "~" if abs(rounded_display - high_precision) > 0.0001 else ""
        row.label(text=f"{prefix}{rounded_display:.{precision}f} {unit_suffix}")

        # Target Dimension Input (editable)
        col.prop(self, "target_dimension", text=f"Target Dimension ({unit_suffix})")

    def execute(self, context):
        settings = context.scene.scale_interactive_settings
        obj_name = self.object_name
        orig_mode = self.original_mode
        measured_dist_meters = self.measured_distance
        target_dim_display = self.target_dimension

        if measured_dist_meters <= 0.000001:
            self.report({'ERROR'}, "Invalid measured distance.")
            return {'CANCELLED'}
        if target_dim_display <= 0.000001:
            self.report({'ERROR'}, "Target dimension must be positive.")
            return {'CANCELLED'}

        target_dim_meters = convert_from_display_unit(target_dim_display, settings)
        if target_dim_meters <= 0.000001:
             self.report({'ERROR'}, "Target dimension too small after unit conversion.")
             return {'CANCELLED'}

        obj = context.scene.objects.get(obj_name)
        if not obj:
            self.report({'ERROR'}, f"Object '{obj_name}' not found.")
            return {'CANCELLED'}
        if obj.type != 'MESH':
            self.report({'ERROR'}, f"Object '{obj_name}' is not a Mesh.")
            return {'CANCELLED'}

        # Perform Scaling
        scaling_factor = target_dim_meters / measured_dist_meters
        current_mode = context.mode
        needs_mode_change = False
        original_active = context.view_layer.objects.active
        original_selection_names = [o.name for o in context.selected_objects if o]

        if current_mode != 'OBJECT':
            needs_mode_change = True
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except RuntimeError as e:
                self.report({'ERROR'}, f"Failed to switch to Object Mode: {e}")
                return {'CANCELLED'}

        # Select only the target object
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        context.view_layer.objects.active = obj

        # Apply Scale
        try:
            obj.scale *= scaling_factor
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True, properties=False)
        except Exception as e:
            self.report({'ERROR'}, f"Scaling failed: {e}")
            # Attempt to restore selection and mode on error
            obj.select_set(False)
            for name in original_selection_names:
                sel_obj = context.scene.objects.get(name)
                if sel_obj: sel_obj.select_set(True)
            if original_active and original_active.name in context.scene.objects:
                context.view_layer.objects.active = original_active
            if needs_mode_change and context.view_layer.objects.active and orig_mode != 'OBJECT':
                 try:
                     mode_to_set = 'EDIT' if orig_mode == 'EDIT_MESH' else orig_mode
                     bpy.ops.object.mode_set(mode=mode_to_set)
                 except Exception: pass
            return {'CANCELLED'}

        # Restore Selection and Mode
        if obj.name not in original_selection_names:
            obj.select_set(False)
        for name in original_selection_names:
            sel_obj = context.scene.objects.get(name)
            if sel_obj and (sel_obj != obj or obj.name in original_selection_names):
                 sel_obj.select_set(True)

        restored_active = False
        if original_active and original_active.name in context.scene.objects:
            context.view_layer.objects.active = original_active
            restored_active = True
        elif obj.name in original_selection_names and obj.name in context.scene.objects:
             context.view_layer.objects.active = obj
             restored_active = True

        if needs_mode_change and orig_mode != 'OBJECT':
            current_active_after_restore = context.view_layer.objects.active
            if current_active_after_restore:
                try:
                    mode_to_set = 'EDIT' if orig_mode == 'EDIT_MESH' else orig_mode
                    bpy.ops.object.mode_set(mode=mode_to_set)
                except RuntimeError as e:
                    print(f"Warning: Could not switch object '{current_active_after_restore.name}' back to {orig_mode}: {e}")

        # Report Success
        unit_suffix = get_unit_suffix(settings)
        precision = int(settings.decimal_precision)
        rounded_target = round(target_dim_display, precision)
        high_precision_target = round(target_dim_display, precision + 2)
        prefix = "~" if abs(rounded_target - high_precision_target) > 0.0001 else ""
        self.report({'INFO'}, f"Object '{obj.name}' scaled by {scaling_factor:.4f}. New dimension: {prefix}{rounded_target:.{precision}f} {unit_suffix}")

        # Signal Main Operator to Clean Up
        OBJECT_OT_ScaleToDimensionInteractive._dialog_completed_successfully = True
        if context.area:
            context.area.tag_redraw()

        return {'FINISHED'}

    def cancel(self, context):
        self.report({'INFO'}, "Target dimension entry cancelled.")
        return {'CANCELLED'}


# Panel
class VIEW3D_PT_ScaleToDimensionInteractivePanel(Panel):
    bl_label = "Measure and Scale"
    bl_description = "Interactively measure and scale to a target dimension"
    bl_idname = "VIEW3D_PT_scale_to_dimension_interactive"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Item'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.scale_interactive_settings

        col = layout.column(align=True)

        # Unit Selection
        box = col.box()
        box.label(text="Display Units:")
        row = box.row(align=True)
        row.prop(settings, "system_unit", expand=True)

        if settings.system_unit == 'METRIC':
            row = box.row(align=True)
            row.prop(settings, "metric_unit", expand=True)

        # Decimal Precision
        row = box.row(align=True)
        row.alignment = 'LEFT' # Align label left
        row.label(text="Precision:")  # Use "Decimal Places:" for more clarity if preferred
        row.scale_x = 2  # Increase width of the dropdown menu
        row.prop(settings, "decimal_precision", text="")

        col.separator()

        # Operator Button
        obj = context.active_object
        can_run = obj and obj.type == 'MESH'
        op_row = col.row()

        is_running = OBJECT_OT_ScaleToDimensionInteractive._draw_handle is not None
        op_row.enabled = can_run and not is_running

        op_row.operator(
            OBJECT_OT_ScaleToDimensionInteractive.bl_idname,
            text="Measure and Scale",
            icon='ARROW_LEFTRIGHT')

        # Status Info
        if not can_run:
            col.label(text="Select a Mesh object.", icon='INFO')
        elif is_running:
             col.label(text="Measuring active... (ESC to cancel)", icon='INFO')

# Registration
classes = (
    ScaleInteractiveSettings,
    OBJECT_OT_ScaleToDimensionInteractive,
    OBJECT_OT_ScaleConfirmDialog,
    VIEW3D_PT_ScaleToDimensionInteractivePanel,
)

def register():
    # Ensure cleanup from previous runs
    if OBJECT_OT_ScaleToDimensionInteractive._draw_handle is not None:
        try: bpy.types.SpaceView3D.draw_handler_remove(OBJECT_OT_ScaleToDimensionInteractive._draw_handle, 'WINDOW')
        except Exception: pass
        OBJECT_OT_ScaleToDimensionInteractive._draw_handle = None

    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scale_interactive_settings = PointerProperty(type=ScaleInteractiveSettings)

def unregister():
    # Clean up draw handler
    if OBJECT_OT_ScaleToDimensionInteractive._draw_handle is not None:
        try: bpy.types.SpaceView3D.draw_handler_remove(OBJECT_OT_ScaleToDimensionInteractive._draw_handle, 'WINDOW')
        except Exception: pass
        OBJECT_OT_ScaleToDimensionInteractive._draw_handle = None

    # Remove settings property
    if hasattr(bpy.types.Scene, 'scale_interactive_settings'):
        try:
             if bpy.context.scene.get('scale_interactive_settings') is not None:
                 del bpy.types.Scene.scale_interactive_settings
        except AttributeError: pass
        except Exception as e: print(f"Warning: Could not delete scene property 'scale_interactive_settings': {e}")

    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except RuntimeError: pass # Ignore errors during unregistration

if __name__ == "__main__":
    try: unregister()
    except Exception as e: print(f"Pre-registration unregister failed: {e}")
    register()