import bpy
from bpy.types import Context
from . import config

def is_active_fastener(context: Context):
    yield context.active_object is not None
    fastener_props = getattr(context.active_object, config.PROPS_ALIAS)
    yield fastener_props.is_fastener
    yield context.mode == "OBJECT"
