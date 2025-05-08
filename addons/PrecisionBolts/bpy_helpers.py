from bpy.types import Context

def deselect_all(context: Context) -> None:
    for obj in context.selected_objects[:]:
        obj.select_set(False)
