import bpy, itertools
from .. import __package__ as base_package

from ..functions.poll import (
    basic_poll,
    is_canvas,
    is_instanced_data,
)
from ..functions.object import (
    apply_modifier,
    convert_to_mesh,
    object_visibility_set,
    delete_empty_collection,
    delete_cutter,
    change_parent,
)
from ..functions.list import (
    list_canvases,
    list_canvas_slices,
    list_canvas_cutters,
    list_cutter_users,
    list_selected_canvases,
    list_unused_cutters,
    list_pre_boolean_modifiers,
)


#### ------------------------------ OPERATORS ------------------------------ ####

# Toggle All Cutters
class OBJECT_OT_boolean_toggle_all(bpy.types.Operator):
    bl_idname = "object.boolean_toggle_all"
    bl_label = "Toggle Boolean Cutters"
    bl_description = "Toggle all boolean cutters affecting selected canvases"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return basic_poll(context, check_linked=True) and is_canvas(context.active_object)

    def execute(self, context):
        canvases = list_selected_canvases(context)
        cutters, modifiers = list_canvas_cutters(canvases)
        slices = list_canvas_slices(canvases)

        # Toggle Modifiers
        for mod in modifiers:
            mod.show_viewport = not mod.show_viewport
            mod.show_render = not mod.show_render

        # Hide Slices
        for slice in slices:
            slice.hide_viewport = not slice.hide_viewport
            slice.hide_render = not slice.hide_render
            for mod in slice.modifiers:
                if mod.type == 'BOOLEAN' and mod.object in cutters:
                    mod.show_viewport = not mod.show_viewport
                    mod.show_render = not mod.show_render

        # Hide Unused Cutters
        other_canvases = list_canvases()
        for obj in other_canvases:
            if obj not in canvases + slices:
                if any(mod.object in cutters and mod.show_viewport for mod in obj.modifiers if mod.type == 'BOOLEAN'):
                    cutters[:] = [cutter for cutter in cutters if cutter not in [mod.object for mod in obj.modifiers]]

        for cutter in cutters:
            cutter.hide_viewport = not cutter.hide_viewport

        return {'FINISHED'}


# Remove All Cutters
class OBJECT_OT_boolean_remove_all(bpy.types.Operator):
    bl_idname = "object.boolean_remove_all"
    bl_label = "Remove Boolean Cutters"
    bl_description = "Remove all boolean cutters from selected canvases"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return basic_poll(context, check_linked=True) and is_canvas(context.active_object)

    def execute(self, context):
        prefs = context.preferences.addons[base_package].preferences

        canvases = list_selected_canvases(context)
        cutters, __ = list_canvas_cutters(canvases)
        slices = list_canvas_slices(canvases)

        # Remove Slices
        for slice in slices:
            if slice in canvases:
                canvases.remove(slice)
            delete_cutter(slice)

        for canvas in canvases:
            # Remove Modifiers
            for mod in canvas.modifiers:
                if mod.type == 'BOOLEAN' and "boolean_" in mod.name:
                    if mod.object in cutters:
                        canvas.modifiers.remove(mod)

            # remove_boolean_properties
            if canvas.booleans.canvas == True:
                canvas.booleans.canvas = False


        # Restore Orphaned Cutters
        unused_cutters, leftovers = list_unused_cutters(cutters, canvases, slices, do_leftovers=True)

        for cutter in unused_cutters:
            if cutter.booleans.carver:
                delete_cutter(cutter)
            else:
                # restore_visibility
                cutter.hide_render = False
                cutter.display_type = 'TEXTURED'
                cutter.lineart.usage = 'INHERIT'
                object_visibility_set(cutter, value=True)
                cutter.booleans.cutter = ""

                # remove_parent_&_collection
                if prefs.parent and cutter.parent in canvases:
                    change_parent(cutter, None)

                if prefs.use_collection:
                    cutters_collection = bpy.data.collections.get(prefs.collection_name)
                    if cutters_collection in cutter.users_collection:
                        bpy.data.collections.get(prefs.collection_name).objects.unlink(cutter)

        # purge_empty_collection
        if prefs.use_collection:
            delete_empty_collection()


        # Change Leftover Cutter Parent
        if prefs.parent:
            for cutter in leftovers:
                if cutter.parent in canvases:
                    other_canvases = list_cutter_users([cutter])
                    change_parent(cutter, other_canvases[0])

        return {'FINISHED'}


# Apply All Cutters
class OBJECT_OT_boolean_apply_all(bpy.types.Operator):
    bl_idname = "object.boolean_apply_all"
    bl_label = "Apply All Boolean Cutters"
    bl_description = "Apply all boolean cutters on selected canvases"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return basic_poll(context, check_linked=True) and is_canvas(context.active_object)


    def invoke(self, context, event):
        # Filter Objects
        self.canvases = []
        for obj in list_selected_canvases(context):
            # excude_canvases_with_shape_keys
            if obj.data.shape_keys:
                self.report({'ERROR'}, f"Modifiers can't be applied to {obj.name} because it has shape keys")
                continue

            self.canvases.append(obj)


        if any(obj for obj in self.canvases if is_instanced_data(obj)):
            return context.window_manager.invoke_confirm(self, event,
                                                        title="Apply Boolean Cutters", confirm_text="Yes", icon='WARNING',
                                                        message=("Canvas object(s) have instanced object data.\n"
                                                                 "In order to apply modifiers, they need to be made single-user.\n"
                                                                 "Do you proceed?"))
        else:
            return self.execute(context)


    def execute(self, context):
        prefs = context.preferences.addons[base_package].preferences

        cutters, __ = list_canvas_cutters(self.canvases)
        slices = list_canvas_slices(self.canvases)

        for cutter in cutters:
            for face in cutter.data.polygons:
                face.select = True

        for canvas in itertools.chain(self.canvases, slices):
            context.view_layer.objects.active = canvas

            # Apply Modifiers
            if prefs.apply_order == 'ALL':
                convert_to_mesh(context, canvas)

            elif prefs.apply_order == 'BEFORE':
                modifiers = list_pre_boolean_modifiers(canvas)
                for mod in modifiers:
                    apply_modifier(context, canvas, mod, single_user=True)

            elif prefs.apply_order == 'BOOLEANS':
                for mod in canvas.modifiers:
                    if mod.type == 'BOOLEAN' and "boolean_" in mod.name:
                        apply_modifier(context, canvas, mod, single_user=True)

            # remove_boolean_properties
            canvas.booleans.canvas = False
            canvas.booleans.slice = False


        # Purge Orphaned Cutters
        unused_cutters, leftovers = list_unused_cutters(cutters, self.canvases, slices, do_leftovers=True)

        purged_cutters = []
        for cutter in unused_cutters:
            if cutter not in purged_cutters:
                # Transfer Children
                for child in cutter.children:
                    change_parent(child, cutter.parent)

                # Purge
                delete_cutter(cutter)
                purged_cutters.append(cutter)

        # purge_empty_collection
        if prefs.use_collection:
            delete_empty_collection()


        # Change Leftover Cutter Parent
        if prefs.parent:
            for cutter in leftovers:
                if cutter.parent in self.canvases:
                    other_canvases = list_cutter_users([cutter])
                    change_parent(cutter, other_canvases[0])

        return {'FINISHED'}



#### ------------------------------ REGISTRATION ------------------------------ ####

addon_keymaps = []

classes = [
    OBJECT_OT_boolean_toggle_all,
    OBJECT_OT_boolean_remove_all,
    OBJECT_OT_boolean_apply_all,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # KEYMAP
    addon = bpy.context.window_manager.keyconfigs.addon
    km = addon.keymaps.new(name="Object Mode")

    kmi = km.keymap_items.new("object.boolean_apply_all", 'NUMPAD_ENTER', 'PRESS', shift=True, ctrl=True)
    kmi.active = True
    addon_keymaps.append((km, kmi))


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # KEYMAP
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
