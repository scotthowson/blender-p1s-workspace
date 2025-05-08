import bpy
from bpy.types import Context
from bpy_types import Menu, Panel

from . import fasteners
from . import config
from . import operators
from . import polls
from . import properties
from . import idnames


class FastenerObjectPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def get_builder(self, props: properties.FastenerProps):
        return fasteners.builders[props.fastener_type]

    @classmethod
    def get_props(cls, context):
        return getattr(context.active_object, config.PROPS_ALIAS)


class OBJECT_PT_EditFastener(FastenerObjectPanel, Panel):
    """Object panel edit active gear"""

    bl_label = "Fastener"
    bl_idname = idnames.get_caller_idname()


    @classmethod
    def poll(cls, context):
        return all(polls.is_active_fastener(context))

    def draw(self, context: Context):
        props = self.get_props(context)
        builder = self.get_builder(props)
        builder.draw(self.layout, props)


class VIEW3D_MT_AddFastener(Menu):
    bl_idname = idnames.get_caller_idname()
    bl_label = "Fasteners"

    def draw(self, layout):
        layout = self.layout
        layout.separator()

        for fastener_type in properties.FASTENERS_ENUM:
            text = f"{fastener_type[1]}"
            if fastener_type[0] == "SCREW":
                text += " (alpha)"
            op = layout.operator(
                operators.OBJECT_OT_add_new_fastener.bl_idname,
                text=text,
                icon="LIGHT_SUN",
            )
            op.fastener_type = fastener_type[0]


def add_fastener_menu_items(self, context: Context):
    layout = self.layout
    layout.separator()
    layout.operator_context = "INVOKE_REGION_WIN"
    layout.menu(VIEW3D_MT_AddFastener.bl_idname)


ui_classes = [
    VIEW3D_MT_AddFastener,
]
for cls in FastenerObjectPanel.__subclasses__():
    ui_classes.append(cls)


def register():
    for cls in ui_classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_mesh_add.append(add_fastener_menu_items)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(add_fastener_menu_items)
    for cls in ui_classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
