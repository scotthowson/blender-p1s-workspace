import bpy
from bpy.props import FloatProperty, FloatVectorProperty, BoolProperty
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from ... utils.draw import draw_circle, draw_label, draw_mesh_wire
from ... utils.registration import get_prefs
from ... utils.ui import get_scale, get_zoom_factor, init_timer_modal, set_countdown, get_timer_progress
from ... colors import white, blue, yellow

class DrawGroupRestPose(bpy.types.Operator):
    bl_idname = "machin3.draw_group_rest_pose"
    bl_label = "MACHIN3: Draw Group Rest Pose"
    bl_options = {'INTERNAL'}

    location: FloatVectorProperty(name="Location", subtype='TRANSLATION', default=Vector((0, 0, 0)))
    size: FloatProperty(name="Size", default=1)
    time: FloatProperty(name="Time (s)", default=1)
    alpha: FloatProperty(name="Alpha", default=0.3, min=0.1, max=1)
    reverse: BoolProperty(name="Reverse the Motion", default=False)
    def draw_HUD(self, context):
        alpha = get_timer_progress(self) * self.alpha * (5 if self.reverse else 1)
        scale = get_timer_progress(self) * 5

        if self.reverse:
            scale = 2 / scale

        location2d, zoom_factor = self.get_location2d_and_zoom_factor(context, self.location)
        draw_circle(location2d, radius=scale * (self.size / zoom_factor), width=5, color = blue if self.reverse else white, alpha=alpha)

    def modal(self, context, event):
        context.area.tag_redraw()

        if self.countdown < 0:
            self.finish(context)
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def finish(self, context):
        context.window_manager.event_timer_remove(self.TIMER)
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

    def execute(self, context):
        self.time = get_prefs().HUD_fade_group / 3
        init_timer_modal(self)

        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.TIMER = context.window_manager.event_timer_add(0.01, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def get_location2d_and_zoom_factor(self, context, location):
        location2d = location_3d_to_region_2d(context.region, context.region_data, coord=location)
        zoom_factor = get_zoom_factor(context, location, scale=10)
        return location2d, zoom_factor

class DrawUnGroupable(bpy.types.Operator):
    bl_idname = "machin3.draw_ungroupable"
    bl_label = "MACHIN3: Draw Ungroupable"
    bl_options = {'INTERNAL'}

    time: FloatProperty(name="Time (s)", default=1)
    alpha: FloatProperty(name="Alpha", default=1, min=0.1, max=1)
    def draw_HUD(self, context):
        if context.area == self.area:
            scale = get_scale(context)
            alpha = get_timer_progress(self) * self.alpha

            for loc2d, _ in self.batches:
                draw_label(context, title="Ungroupable", coords=loc2d - Vector((0, 36 * scale)), color=yellow, alpha=alpha)
                draw_label(context, title="Object is parented", coords=loc2d - Vector((0, 54 * scale)), color=white, alpha=alpha / 2)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self) * self.alpha * 0.5

            for _, batch in self.batches:
                draw_mesh_wire(batch, color=yellow, alpha=alpha)

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        else:
            self.finish(context)
            return {'CANCELLED'}

        if self.countdown < 0:
            self.finish(context)
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def finish(self, context):
        context.window_manager.event_timer_remove(self.TIMER)
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

    def execute(self, context):
        from .. group import ungroupable_batches
        self.batches = ungroupable_batches

        self.time = get_prefs().HUD_fade_group * 4
        init_timer_modal(self)

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.TIMER = context.window_manager.event_timer_add(0.01, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
