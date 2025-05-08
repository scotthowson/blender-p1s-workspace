import bpy
from bpy.props import StringProperty, BoolProperty
from ... utils.draw import draw_fading_label
from ... utils.ui import get_mouse_pos
from ... colors import white, yellow, blue

class SetSnappingPreset(bpy.types.Operator):
    bl_idname = "machin3.set_snapping_preset"
    bl_label = "MACHIN3: Set Snapping Preset"
    bl_description = "Set Snapping Preset"
    bl_options = {'REGISTER', 'UNDO'}

    additive: BoolProperty(name="Additive Snap Elements", default=False)
    element: StringProperty(name="Snap Element")
    target: StringProperty(name="Snap Target")
    align_rotation: BoolProperty(name="Align Rotation")

    def draw(self, context):
        layout = self.layout
        column = layout.column()
        ts = context.scene.tool_settings

        column.label(text=f"Elements: {', '.join(e for e in ts.snap_elements)}")
        column.label(text=f"Target: {self.target}")

        if self.element not in ['INCREMENT', 'VOLUME']:
            column.label(text=f"Align Rotation: {self.align_rotation}")

    @classmethod
    def description(cls, context, properties):
        dscr = "Set Snapping Preset"

        if properties.element == 'VERTEX':
            dscr += "\n  VERTEX"

        elif properties.element == 'EDGE':
            dscr += "\n  EDGE"

        elif properties.element == 'FACE' and properties.align_rotation:
            dscr += "\n  FACE + Align Rotation"

        elif properties.element in ['INCREMENT', 'GRID']:
            dscr += "\n  GRID"

        elif properties.element == 'VOLUME':
            dscr += "\n  VOLUMNE"

        dscr += "\n\nALT: Set Snap Element addtively"
        return dscr

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'VIEW_3D'

    def invoke(self, context, event):
        self.additive = event.alt

        get_mouse_pos(self, context, event, hud=False)
        return self.execute(context)

    def execute(self, context):
        ts = context.scene.tool_settings

        if self.additive:
            ts.snap_elements = ts.snap_elements.union({self.element})

        else:
            ts.snap_elements = {self.element}

        if self.element == 'INCREMENT':
            ts.use_snap_grid_absolute = True

        elif self.element == 'VOLUME':
            pass

        else:
            ts.snap_target = self.target
            ts.use_snap_align_rotation = self.align_rotation

        text = ["Additive Snapping" if self.additive else "Snapping"]
        color = [yellow if self.additive else white, white]
        alpha = [1 if self.additive else 0.7, 1]

        text.append(ts.snap_target + " | " + " + ".join(e for e in ts.snap_elements))

        if ts.use_snap_align_rotation:
            text.append("Align Rotation")
            color.append(blue)

        time = 2 if self.additive else 1

        draw_fading_label(context, text=text, x=self.mouse_pos.x, y=self.mouse_pos.y, center=False, color=color, alpha=alpha, move_y=10 * time, time=time)
        return {'FINISHED'}
