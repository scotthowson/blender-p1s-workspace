import bpy

from . import ui
from . import properties
from . import operators

# from . import async_loop
from . import async_loop


bl_info = {
    "name": "Precision Bolts",
    "description": "Precision Bolts",
    "author": "Missing Field <themissingfield.com>",
    "version": (0, 1, 5),
    "blender": (4, 00, 0),
    "location": "View3D",
    "category": "Object",
}


registration_queue = (
    operators,
    properties,
    ui,
)


def register():
    async_loop.setup_asyncio_executor()
    try:
        bpy.utils.register_class(async_loop.AsyncLoopModalOperator)
    except RuntimeError as e:
        print(e)
    for item in registration_queue:
        item.register()


def unregister():
    try:
        bpy.utils.unregister_class(async_loop.AsyncLoopModalOperator)
    except RuntimeError as e:
        print(e)
    for item in registration_queue:
        item.unregister()


if __name__ == "__main__":
    register()
