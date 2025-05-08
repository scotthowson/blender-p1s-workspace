import bpy_types
from . utils import registration as r
from . utils.group import update_group_name
from . utils.application import is_context_safe

def object_name_change(context):
    if is_context_safe(context):
        active = context.active_object#

        if active:

            if active.M3.is_group_empty and r.get_prefs().group_auto_name:
                update_group_name(active)

def group_color_change(context):
    if is_context_safe(context):
        active = context.active_object

        if active and active.M3.is_group_empty:
            objects = [obj for obj in active.children if obj.M3.is_group_object and not obj.M3.is_group_empty]

            for obj in objects:
                obj.color = active.color

def gp_annotation_tint_change(context):
    if is_context_safe(context):
        active = context.active_object

        gp = active if active and active.type == 'GREASEPENCIL' else None

        if gp:
            tint_color = gp.data.layers.active.tint_color

            active.color = (*tint_color, 1)

            mat = active.data.materials.get('NoteMaterial')
            if mat:
                mat.grease_pencil.color = (*tint_color, 1)
