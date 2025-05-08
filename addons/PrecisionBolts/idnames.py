""" id names """
import inspect
from collections import ChainMap

operators = {
    "OBJECT_OT_load_nut_preset": "object.load_nut_preset",
    "OBJECT_OT_load_screw_preset": "object.load_screw_preset",
    "OBJECT_OT_load_bolt_preset": "object.load_bolt_preset",
    "OBJECT_OT_load_threaded_rod_preset": "object.load_threaded_rod_preset",
    "OBJECT_OT_save_fastener_preset": "object.save_fastener_preset",
    "OBJECT_OT_add_new_fastener": "object.add_new_fastener",
    "OBJECT_OT_create_fastener_counterpart": "object.create_fastener_counterpart",
    "OBJECT_OT_apply_thread_preset": "object.load_thread_preset",
    "WM_OT_bolts_open_sys_folder": "wm.bolts_open_sys_folder",
}

panels = {
    "OBJECT_PT_EditFastener":  "OBJECT_PT_EditFastener",
}

menus = {
    "VIEW3D_MT_AddFastener": "VIEW3D_MT_AddFastener",
}



idnames = ChainMap(operators, panels, menus)

def get_caller_idname():
    """ Lookup callers name and return its idname"""
    caller = inspect.stack()[1].function
    return idnames.get(caller)


def auto_operator_idname():
    """ Automatic bl_idname from callers name """
    caller = inspect.stack()[1].function
    namespace = caller.split("_")[0].lower()
    name = caller.split("OT_")[1]
    return f"{namespace}.{name}"
