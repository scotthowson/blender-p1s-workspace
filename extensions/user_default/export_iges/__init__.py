bl_info = {
    "name": "IGES format",
    "author": "Rajeev Nair",
    "version": (2, 0, 0),
    "blender": (2, 81, 6),
    "location": "File > Export",
    "description": "Export mesh data as Subdiv bi-cubic patches in IGES format.",
    "warning": "",
    "doc_url": "https://www.digital-sculptors.com/cms/index.php/software/blender-plugins/63-export-iges.html",
    "support": 'COMMUNITY',
    "category": "Import-Export",
}

import bpy
import sys
import tempfile
import subprocess
import os
import stat

if "bpy" in locals():
    import importlib
    if "export_shape" in locals():
        importlib.reload(export_shape)

from bpy_extras.io_utils import (
    ExportHelper,
    orientation_helper,
    axis_conversion,
)

def count_faces_and_triangles():
    total_faces = 0
    total_triangles = 0
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            mesh = obj.data
            total_faces += len(mesh.polygons)
            total_triangles += sum(1 for poly in mesh.polygons if len(poly.vertices) == 3)
    return total_faces, total_triangles

def write_tmp_file(context, selection, up, forward, mods):
    #get tmp filepath and add the tmpfile
    obj_tmp = tempfile.gettempdir() + "/objtemp.obj"
    #write obj file
    global_scale = bpy.data.scenes[0].unit_settings.scale_length * 1000.0
    from mathutils import Matrix
    g_matrix = (
            Matrix.Scale(global_scale, 4) @
            axis_conversion(
                to_forward=forward,
                to_up=up,
            ).to_4x4()
        )
    from . import export_shape
    return export_shape.save(context, filepath=obj_tmp, use_selection=selection,
                        use_edges=True, use_mesh_modifiers=mods, global_matrix=g_matrix)

def subdiv_data(context, filepath, level, keep_corners, selection, batch_mode, up, forward, mods):
    cmd = os.path.dirname(os.path.abspath(__file__)) + "/osd_iges"
    #check for file permission
    mode = os.stat(cmd).st_mode
    if mode != 33261:
        print("Adding Permission")
        os.chmod(cmd, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    obj_tmp = tempfile.gettempdir() + "/objtemp.obj"
    corners = "0"
    if keep_corners:
        corners = "1"
    if batch_mode:
        view_layer = bpy.context.view_layer
        obj_active = view_layer.objects.active
        if selection == False:
            bpy.ops.object.select_all(action='SELECT')
        select = bpy.context.selected_objects
        bpy.ops.object.select_all(action='DESELECT')
        for obj in select:
            obj.select_set(True)
            view_layer.objects.active = obj
            name = bpy.path.clean_name(obj.name)
            batchfile = filepath.replace('.igs', ('_'+ name + '.igs'))
            print("Writing temperory mesh file.. \n")
            write_tmp_file(context, select, up, forward, mods)
            print("Converting data and saving as IGES...\n")
            process = subprocess.run([cmd, obj_tmp, batchfile, level, corners])
            if process.returncode == 0:
                print("Wrote IGES file", batchfile)
            if os.path.exists(obj_tmp):
                os.remove(obj_tmp)
            obj.select_set(False)
        if selection:
            view_layer.objects.active = obj_active
            for obj in select:
                obj.select_set(True)
        return {'FINISHED'}
    else:
        print("Writing temperory mesh file.. \n")
        write_tmp_file(context, selection, up, forward, mods)
        print("Converting data and saving as IGES...\n")
        process = subprocess.run([cmd, obj_tmp, filepath, level, corners])
        if process.returncode == 0:
            print("Wrote IGES file", filepath)
        if os.path.exists(obj_tmp):
            os.remove(obj_tmp)
        return {'FINISHED'}

from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from bpy.types import Operator

class CheckDialog(bpy.types.Operator):
    bl_idname = "wm.check_dialog"
    bl_label = "Many Triangles! Continue?"

    total_faces: IntProperty(name="Total Faces", default=0)
    total_triangles: IntProperty(name="Total Triangles", default=0)

    #continue_export: BoolProperty(name="Continue Export", default=False)

    def execute(self, context):
        bpy.ops.export_iges.subdiv_data('INVOKE_DEFAULT')  # Replace with your desired export operator
        return {'FINISHED'}

    def invoke(self, context, event):
        self.total_faces, self.total_triangles = count_faces_and_triangles()
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text=f"Total Faces: {self.total_faces}")
        layout.label(text=f"Total Triangles: {self.total_triangles}")

@orientation_helper(axis_forward='Y', axis_up='Z')
class ExportIges(Operator, ExportHelper):
    """Exported selected meshes as Subdiv in IGES format"""
    bl_idname = "export_iges.subdiv_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export IGES"

    # ExportHelper mixin class uses this
    filename_ext = ".igs"

    filter_glob: StringProperty(
        default="*.igs",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    use_selection: BoolProperty(
        name="Selected Only",
        description="Selected only",
        default=True,
    )

    use_batch_mode: BoolProperty(
        name="Batch Mode",
        description="Export selected objects as separate files",
        default=False,
    )

    type: EnumProperty(
        name="Refinement",
        description="Greater the refinement, more the number of patches",
        items=(
            ('1', "Level 1", "Subdiv Level 1"),
            ('2', "Level 2", "Subdiv Level 2"),
            ('3', "Level 3", "Subdiv Level 3"),
        ),
        default='3',
    )

    keep_corners: BoolProperty(
        name="Keep Corners",
        description="Smooth boundaries, but the corners are sharp",
        default=True,
    )

    axis_up: EnumProperty(
        default='Z',
    )

    axis_forward: EnumProperty(
        default='Y',
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply Modifiers",
        default=True,
    )

    def execute(self, context):
        return subdiv_data(context,
                            self.filepath,
                            self.type,
                            self.keep_corners,
                            self.use_selection,
                            self.use_batch_mode,
                            self.axis_up,
                            self.axis_forward,
                            self.apply_modifiers)


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    face_count, triangle_count = count_faces_and_triangles()
    if triangle_count > 100:
        self.layout.operator(CheckDialog.bl_idname, text="Export IGES")
    else:
        self.layout.operator(ExportIges.bl_idname, text="Export IGES")


def register():
    bpy.utils.register_class(CheckDialog)
    bpy.utils.register_class(ExportIges)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(CheckDialog)
    bpy.utils.unregister_class(ExportIges)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
