import bpy
import addon_utils

for i in addon_utils.modules()[:]:
    print(i.__name__)
