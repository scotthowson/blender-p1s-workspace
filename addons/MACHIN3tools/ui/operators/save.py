import bpy
from bpy.props import BoolProperty, StringProperty
import os
import time
import subprocess
import shutil
from ... utils.draw import draw_fading_label
from ... utils.registration import get_addon, get_prefs
from ... utils.system import add_path_to_recent_files, get_incremented_paths, get_next_files, get_temp_dir
from ... utils.ui import force_ui_update, popup_message, get_icon
from ... colors import green

class New(bpy.types.Operator):
    bl_idname = "machin3.new"
    bl_label = "Current file is unsaved. Start a new file anyway?"
    bl_description = "Start new .blend file"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.wm.read_homefile(load_ui=True)

        return {'FINISHED'}

    def invoke(self, context, event):
        if bpy.data.is_dirty:
            return context.window_manager.invoke_confirm(self, event)
        else:
            bpy.ops.wm.read_homefile(load_ui=True)
            return {'FINISHED'}

class Save(bpy.types.Operator):
    bl_idname = "machin3.save"
    bl_label = "Save"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        currentblend = bpy.data.filepath

        if currentblend:
            return f"Save {currentblend}"
        return "Save unsaved file as..."

    def execute(self, context):
        currentblend = bpy.data.filepath

        if currentblend:
            bpy.ops.wm.save_mainfile()

            t = time.time()
            localt = time.strftime('%H:%M:%S', time.localtime(t))
            print("%s | Saved blend: %s" % (localt, currentblend))
            self.report({'INFO'}, 'Saved "%s"' % (os.path.basename(currentblend)))

        else:
            bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')

        return {'FINISHED'}

class SaveAs(bpy.types.Operator):
    bl_idname = "machin3.save_as"
    bl_label = "MACHIN3: Save As"
    bl_description = "Save the current file in the desired location\nALT: Save as Copy\nCTRL: Save as Asset"
    bl_options = {'REGISTER'}

    copy: BoolProperty(name="Save as Copy", default=False)
    asset: BoolProperty(name="Save as Asset", default=False)
    def invoke(self, context, event):
        self.asset = event.ctrl
        self.copy = event.alt
        return self.execute(context)

    def execute(self, context):
        assets = [obj for obj in bpy.data.objects if obj.asset_data]

        if self.asset and assets:
            print("\nINFO: Saving as Asset!")
            print(f"      Found {len(assets)} root Object/Assembly Assets in the current file")

            keep = set()
            self.get_asset_objects_recursively(assets, keep)

            remove = [obj for obj in bpy.data.objects if obj not in keep]

            for obj in remove:
                print(f"WARNING: Removing {obj.name}")
                bpy.data.objects.remove(obj, do_unlink=True)

            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

            bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT', copy=True)

        elif self.copy:
            print("\nINFO: Saving as Copy")
            bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT', copy=True)

        else:
            bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT')

        return {'FINISHED'}

    def get_asset_objects_recursively(self, assets, keep, depth=0):
        for obj in assets:
            keep.add(obj)

            if obj.type == 'EMPTY' and obj.instance_type == 'COLLECTION' and obj.instance_collection:
                self.get_asset_objects_recursively(obj.instance_collection.objects, keep, depth + 1)

class SaveIncremental(bpy.types.Operator):
    bl_idname = "machin3.save_incremental"
    bl_label = "Incremental Save"
    bl_options = {'REGISTER'}

    @classmethod
    def description(cls, context, properties):
        currentblend = bpy.data.filepath

        if currentblend:
            incrpaths = get_incremented_paths(currentblend)

            if incrpaths:
                return f"Save {currentblend} incrementally to {os.path.basename(incrpaths[0])}\nALT: Save to {os.path.basename(incrpaths[1])}"

        return "Save unsaved file as..."

    def invoke(self, context, event):
        currentblend = bpy.data.filepath

        if currentblend:
            incrpaths = get_incremented_paths(currentblend)
            savepath = incrpaths[1] if event.alt else incrpaths[0]

            if os.path.exists(savepath):
                self.report({'ERROR'}, "File '%s' exists already!\nBlend has NOT been saved incrementally!" % (savepath))
                return {'CANCELLED'}

            else:

                add_path_to_recent_files(savepath)

                bpy.ops.wm.save_as_mainfile(filepath=savepath)

                t = time.time()
                localt = time.strftime('%H:%M:%S', time.localtime(t))
                print(f"{localt} | Saved {os.path.basename(currentblend)} incrementally to {savepath}")
                self.report({'INFO'}, f"Incrementally saved to {os.path.basename(savepath)}")

        else:
            bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')

        return {'FINISHED'}

class SaveVersionedStartupFile(bpy.types.Operator):
    bl_idname = "machin3.save_versioned_startup_file"
    bl_label = "Save Versioned Startup File"
    bl_options = {'REGISTER'}

    def execute(self, context):
        config_path = bpy.utils.user_resource('CONFIG')
        startup_path = os.path.join(config_path, 'startup.blend')

        if os.path.exists(startup_path):
            indices = [int(f.replace('startup.blend', '')) for f in os.listdir(bpy.utils.user_resource('CONFIG')) if 'startup.blend' in f and f != 'startup.blend']
            biggest_idx = max(indices) if indices else 0

            os.rename(startup_path, os.path.join(config_path, f'startup.blend{biggest_idx + 1}'))

            bpy.ops.wm.save_homefile()

            self.report({'INFO'}, f'Versioned Startup File saved: {biggest_idx + 1}')

        else:
            bpy.ops.wm.save_homefile()

            self.report({'INFO'}, 'Initial Startup File saved')

        return {'FINISHED'}

class LoadMostRecent(bpy.types.Operator):
    bl_idname = "machin3.load_most_recent"
    bl_label = "Load Most Recent"
    bl_description = "Load most recently used .blend file"
    bl_options = {"REGISTER"}

    def execute(self, context):
        recent_path = bpy.utils.user_resource('CONFIG', path="recent-files.txt")

        try:
            with open(recent_path) as file:
                recent_files = file.read().splitlines()
        except (IOError, OSError, FileNotFoundError):
            recent_files = []

        if recent_files:
            most_recent = recent_files[0]

            if os.path.exists(most_recent):
                bpy.ops.wm.open_mainfile(filepath=most_recent, load_ui=True)
                self.report({'INFO'}, 'Loaded most recent "%s"' % (os.path.basename(most_recent)))

            else:
                popup_message("File %s does not exist" % (most_recent), title="File not found")

        return {'FINISHED'}

class LoadPrevious(bpy.types.Operator):
    bl_idname = "machin3.load_previous"
    bl_label = "Load previous file? File has unsaved Changes!"
    bl_options = {'REGISTER'}

    load_ui: BoolProperty()
    include_backups: BoolProperty()

    @classmethod
    def poll(cls, context):
        if bpy.data.filepath:
            _, prev_file, prev_backup_file = get_next_files(bpy.data.filepath, next=False, debug=False)
            return prev_file or prev_backup_file

    @classmethod
    def description(cls, context, properties):
        folder, prev_file, prev_backup_file = get_next_files(bpy.data.filepath, next=False, debug=False)

        if not prev_file and not prev_backup_file:
            desc = "Your are at the beginning of the folder. There are no previous files to load."

        else:
            desc = f"Load Previous .blend File in Current Folder: {prev_file}"

            if prev_backup_file and prev_backup_file != prev_file:
                desc += f"\nCTRL: including Backups: {prev_backup_file}"

            desc += "\n\nALT: Keep current UI"
        return desc

    def invoke(self, context, event):
        if bpy.data.is_dirty:
            return context.window_manager.invoke_confirm(self, event)

        self.load_ui = not event.alt
        self.include_backups = event.ctrl
        return self.execute(context)

    def execute(self, context):
        folder, prev_file, prev_backup_file = get_next_files(bpy.data.filepath, next=False, debug=False)

        is_backup = self.include_backups and prev_backup_file
        file = prev_backup_file if is_backup else prev_file if prev_file else None

        if file:
            filepath = os.path.join(folder, file)

            add_path_to_recent_files(filepath)

            bpy.ops.wm.open_mainfile(filepath=filepath, load_ui=self.load_ui)
            self.report({'INFO'}, f"Loaded previous {'BACKUP ' if is_backup else ''}file '{file}'")
            return {'FINISHED'}

        return {'CANCELLED'}

class LoadNext(bpy.types.Operator):
    bl_idname = "machin3.load_next"
    bl_label = "Load next file? File has unsaved Changes!"
    bl_options = {'REGISTER'}

    load_ui: BoolProperty()
    include_backups: BoolProperty()

    @classmethod
    def poll(cls, context):
        if bpy.data.filepath:
            _, next_file, next_backup_file = get_next_files(bpy.data.filepath, next=True, debug=False)
            return next_file or next_backup_file

    @classmethod
    def description(cls, context, properties):
        folder, next_file, next_backup_file = get_next_files(bpy.data.filepath, next=True, debug=False)

        if not next_file and not next_backup_file:
            desc = "You have reached the end of the folder. There are no next files to load."

        else:
            desc = f"Load Next .blend File in Current Folder: {next_file}"

            if next_backup_file and next_backup_file != next_file:
                desc += f"\nCTRL: including Backups: {next_backup_file}"

            desc += "\n\nALT: Keep current UI"
        return desc

    def invoke(self, context, event):
        if bpy.data.is_dirty:
            return context.window_manager.invoke_confirm(self, event)

        self.load_ui = not event.alt
        self.include_backups = event.ctrl
        return self.execute(context)

    def execute(self, context):
        folder, next_file, next_backup_file = get_next_files(bpy.data.filepath, next=True, debug=False)

        is_backup = self.include_backups and next_backup_file
        file = next_backup_file if is_backup else next_file if next_file else None

        if file:
            filepath = os.path.join(folder, file)

            add_path_to_recent_files(filepath)

            bpy.ops.wm.open_mainfile(filepath=filepath, load_ui=self.load_ui)

            self.report({'INFO'}, f"Loaded next {'BACKUP ' if is_backup else ''}file '{file}'")
            return {'FINISHED'}

        else:
            popup_message([f"You have reached the end of blend files in '{folder}'", "There are still some backup files though, which you can load via CTRL"], title="End of folder reached")

        return {'CANCELLED'}

class OpenTemp(bpy.types.Operator):
    bl_idname = "machin3.open_temp_dir"
    bl_label = "Open"
    bl_description = "Open System's Temp Folder, which is used to Save Files on Quit, Auto Saves and Undo Saves"
    bl_options = {'REGISTER', 'UNDO'}

    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    filepath: StringProperty(subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})

    filter_blender: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_backup: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    load_ui: BoolProperty(name="Load UI", default=True)
    def execute(self, context):
        bpy.ops.wm.open_mainfile(filepath=self.filepath, load_ui=self.load_ui)
        return {'FINISHED'}

    def invoke(self, context, event):
        self.directory = get_temp_dir(context)

        if self.directory:

            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        return {'CANCELLED'}

decalmachine = None

class Purge(bpy.types.Operator):  
    bl_idname = "machin3.purge_orphans"
    bl_label = "MACHIN3: Purge Orphans"
    bl_options = {'REGISTER', 'UNDO'}

    recursive: BoolProperty(name="Recursive Purge", default=False)
    @classmethod
    def description(cls, context, properties):
        desc = "Purge Orphans\nALT: Purge Orphans Recursively"

        if bpy.app.version >= (4, 2, 0):
            desc += "\nSHIFT: Purge Preview"
        return desc

    def invoke(self, context, event):
        if bpy.app.version >= (4, 2, 0) and event.shift:

            bpy.ops.outliner.orphans_purge('INVOKE_DEFAULT')
            return {'FINISHED'}

        global decalmachine
        
        if decalmachine is None:
            decalmachine = get_addon('DECALmachine')[0]

        self.recursive = event.alt

        before_meshes_count = len(bpy.data.meshes)
        before_curves_count = len(bpy.data.curves)
        before_objects_count = len(bpy.data.objects)
        before_materials_count = len(bpy.data.materials)
        before_images_count = len(bpy.data.images)
        before_nodegroups_count = len(bpy.data.node_groups)
        before_collections_count = len(bpy.data.collections)
        before_scenes_count = len(bpy.data.scenes)
        before_worlds_count = len(bpy.data.worlds)

        if decalmachine:
            bpy.ops.machin3.remove_decal_orphans()

        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=self.recursive)

        empty_collections = [col for col in bpy.data.collections if not col.objects and not col.children and col.users == 1 and not col.use_fake_user]

        if empty_collections:
            bpy.data.batch_remove(empty_collections)

        after_meshes_count = len(bpy.data.meshes)
        after_curves_count = len(bpy.data.curves)
        after_objects_count = len(bpy.data.objects)
        after_materials_count = len(bpy.data.materials)
        after_images_count = len(bpy.data.images)
        after_nodegroups_count = len(bpy.data.node_groups)
        after_collections_count = len(bpy.data.collections)
        after_scenes_count = len(bpy.data.scenes)
        after_worlds_count = len(bpy.data.worlds)

        meshes_count = before_meshes_count - after_meshes_count
        curves_count = before_curves_count - after_curves_count
        objects_count = before_objects_count - after_objects_count
        materials_count = before_materials_count - after_materials_count
        images_count = before_images_count - after_images_count
        nodegroups_count = before_nodegroups_count - after_nodegroups_count
        collections_count = before_collections_count - after_collections_count
        scenes_count = before_scenes_count - after_scenes_count
        worlds_count = before_worlds_count - after_worlds_count

        if any([meshes_count, curves_count, objects_count, materials_count, images_count, nodegroups_count, collections_count, scenes_count, worlds_count]):
            total_count = meshes_count + curves_count + objects_count + materials_count + images_count + nodegroups_count + collections_count + scenes_count + worlds_count

            msg = [f"Removed {total_count} data blocks!"]

            if meshes_count:
                msg.append(f" • {meshes_count} meshes")

            if curves_count:
                msg.append(f" • {curves_count} curves")

            if objects_count:
                msg.append(f" • {objects_count} objects")

            if materials_count:
                msg.append(f" • {materials_count} materials")

            if images_count:
                msg.append(f" • {images_count} images")

            if nodegroups_count:
                msg.append(f" • {nodegroups_count} node groups")

            if scenes_count:
                msg.append(f" • {scenes_count} scenes")

            if worlds_count:
                msg.append(f" • {worlds_count} worlds")

            popup_message(msg, title="Recursive Purge" if event.alt else "Purge")

        else:
            draw_fading_label(context, text="Nothing to purge.", color=green)

        return {'FINISHED'}

class Clean(bpy.types.Operator):
    bl_idname = "machin3.clean_out_blend_file"
    bl_label = "Clean out .blend file!"
    bl_options = {'REGISTER', 'UNDO'}

    remove_custom_brushes: BoolProperty(name="Remove Custom Brushes", default=False)
    has_selection: BoolProperty(name="Has Selected Objects", default=False)
    @classmethod
    def poll(cls, context):
        d = bpy.data
        return any([d.scenes, d.objects, d.materials, d.images, d.collections, d.texts, d.actions, d.brushes, d.worlds, d.meshes, d.node_groups, d.libraries])

    @classmethod
    def description(cls, context, properties):
        desc = "Clean out entire .blend file"

        if context.selected_objects:
            desc += " (except selected objects)"

        desc += '\nALT: Remove non-default Brushes too'
        return desc

    def draw(self, context):
        layout = self.layout
        column = layout.column()

        text = "This will remove everything in the current .blend file"

        if self.remove_custom_brushes:
            text += ", including custom Brushes"

        if self.has_selection:
            if self.remove_custom_brushes:
                text += ", but except the selected objects"
            else:
                text += ", except the selected objects"

        text += "!"

        column.label(text=text, icon_value=get_icon('error'))

    def invoke(self, context, event):
        self.has_selection = True if context.selected_objects else False
        self.remove_custom_brushes = event.alt

        width = 600 if self.has_selection and self.remove_custom_brushes else 450 if self.has_selection or self.remove_custom_brushes else 300

        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=width)

    def execute(self, context):
        sel = [obj for obj in context.selected_objects]
        remove_objs = [obj for obj in bpy.data.objects if obj not in sel]
        bpy.data.batch_remove(remove_objs)

        if sel:
            mcol = context.scene.collection

            for obj in sel:
                if obj.name not in mcol.objects:
                    mcol.objects.link(obj)
                    print(f"WARNING: Adding {obj.name} to master collection to ensure visibility/accessibility")

        remove_scenes = [scene for scene in bpy.data.scenes if scene != context.scene]
        bpy.data.batch_remove(remove_scenes)

        bpy.data.batch_remove(bpy.data.materials)

        bpy.data.batch_remove(bpy.data.images)
        
        bpy.data.batch_remove(bpy.data.collections)

        bpy.data.batch_remove(bpy.data.texts)

        bpy.data.batch_remove(bpy.data.actions)

        if self.remove_custom_brushes:
            print("WARNING: Removing Custom Brushes")
            default_brushes_names = self.get_default_brushes()
            remove_brushes = [brush for brush in bpy.data.brushes if brush.name not in default_brushes_names]
            bpy.data.batch_remove(remove_brushes)

        bpy.data.batch_remove(bpy.data.worlds)

        bpy.data.batch_remove(bpy.data.node_groups)

        if annotations := bpy.data.grease_pencils.get('Annotations'):
            if bpy.app.version < (4, 3, 0):
                annotations.clear()

                annotations.layers.new('Note')
                
            else:
                bpy.data.grease_pencils.remove(annotations)
                bpy.ops.gpencil.annotation_add()

        bpy.data.batch_remove(bpy.data.libraries)

        bpy.ops.outliner.orphans_purge(do_recursive=True)

        if bpy.data.meshes:
            selmeshes = [obj.data for obj in sel if obj.type == 'MESH']
            remove_meshes = [mesh for mesh in bpy.data.meshes if mesh not in selmeshes]

            if remove_meshes:
                print("WARNING: Removing leftover meshes")
                bpy.data.batch_remove(remove_meshes)

        if context.space_data.local_view:
            bpy.ops.view3d.localview(frame_selected=False)

        context.space_data.shading.use_scene_world = False
        context.space_data.shading.use_scene_world_render = False

        context.space_data.shading.use_scene_lights = False
        context.space_data.shading.use_scene_lights_render = False

        return {'FINISHED'}

    def get_default_brushes(self):
        if bpy.app.version >= (4, 2, 0):
            default_brushes_names = ['Add', 
                                     'Airbrush', 
                                     'Average', 
                                     'Blob', 
                                     'Blur', 
                                     'Boundary', 
                                     'Clay', 
                                     'Clay Strips', 
                                     'Clay Thumb', 
                                     'Clone', 
                                     'Clone Stroke', 
                                     'Cloth', 
                                     'Crease', 
                                     'Darken', 
                                     'Draw', 
                                     'Draw Face Sets', 
                                     'Draw Sharp', 
                                     'Elastic Deform', 
                                     'Eraser Hard', 
                                     'Eraser Point', 
                                     'Eraser Soft', 
                                     'Eraser Stroke', 
                                     'Fill', 
                                     'Fill Area', 
                                     'Fill/Deepen', 
                                     'Flatten/Contrast', 
                                     'Grab', 'Grab Stroke', 
                                     'Inflate/Deflate', 
                                     'Ink Pen', 
                                     'Ink Pen Rough', 
                                     'Layer', 
                                     'Lighten', 
                                     'Marker Bold', 
                                     'Marker Chisel', 
                                     'Mask', 
                                     'Mix', 
                                     'Multi-plane Scrape', 
                                     'Multiply', 
                                     'Multires Displacement Eraser', 
                                     'Multires Displacement Smear', 
                                     'Nudge', 
                                     'Paint', 
                                     'Pen', 
                                     'Pencil', 
                                     'Pencil Soft', 
                                     'Pinch Stroke', 
                                     'Pinch/Magnify', 
                                     'Pose', 
                                     'Push Stroke', 
                                     'Randomize Stroke', 
                                     'Rotate', 
                                     'Scrape/Peaks', 
                                     'SculptDraw', 
                                     'Simplify', 
                                     'Slide Relax', 
                                     'Smear', 
                                     'Smooth', 
                                     'Smooth Stroke', 
                                     'Snake Hook', 
                                     'Soften', 
                                     'Strength Stroke', 
                                     'Subtract', 
                                     'TexDraw', 
                                     'Thickness Stroke', 
                                     'Thumb', 
                                     'Tint', 
                                     'Twist Stroke', 
                                     'Vertex Average', 
                                     'Vertex Blur', 
                                     'Vertex Draw', 
                                     'Vertex Replace', 
                                     'Vertex Smear',
                                     'Weight Average',
                                     'Weight Blur',
                                     'Weight Draw',
                                     'Weight Smear']
        else:
            default_brushes_names = ['Add', 'Airbrush', 'Average', 'Blob', 'Blur', 'Boundary', 'Clay', 'Clay Strips', 'Clay Thumb', 'Clone', 'Clone Stroke', 'Cloth', 'Crease', 'Darken', 'Draw', 'Draw Face Sets', 'Draw Sharp', 'Draw Weight', 'Elastic Deform', 'Eraser Hard', 'Eraser Point', 'Eraser Soft', 'Eraser Stroke', 'Fill', 'Fill Area', 'Fill/Deepen', 'Flatten/Contrast', 'Grab', 'Grab Stroke', 'Inflate/Deflate', 'Ink Pen', 'Ink Pen Rough', 'Layer', 'Lighten', 'Marker Bold', 'Marker Chisel', 'Mask', 'Mix', 'Multi-plane Scrape', 'Multiply', 'Multires Displacement Eraser', 'Nudge', 'Paint', 'Pen', 'Pencil', 'Pencil Soft', 'Pinch Stroke', 'Pinch/Magnify', 'Pose', 'Push Stroke', 'Randomize Stroke', 'Rotate', 'Scrape/Peaks', 'SculptDraw', 'Simplify', 'Slide Relax', 'Smear', 'Smooth', 'Smooth Stroke', 'Snake Hook', 'Soften', 'Strength Stroke', 'Subtract', 'TexDraw', 'Thickness Stroke', 'Thumb', 'Tint', 'Twist Stroke', 'Vertex Average', 'Vertex Blur', 'Vertex Draw', 'Vertex Replace', 'Vertex Smear']
        return default_brushes_names

class ReloadLinkedLibraries(bpy.types.Operator):
    bl_idname = "machin3.reload_linked_libraries"
    bl_label = "MACHIN3: Reload Linked Liraries"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bpy.data.libraries

    def execute(self, context):
        reloaded = []

        for lib in bpy.data.libraries:
            lib.reload()
            reloaded.append(lib.name)
            print(f"Reloaded Library: {lib.name}")

        self.report({'INFO'}, f"Reloaded {'Library' if len(reloaded) == 1 else f'{len(reloaded)} Libraries'}: {', '.join(reloaded)}")

        return {'FINISHED'}

has_skribe = None
has_screencast_keys = None

class ScreenCast(bpy.types.Operator):
    bl_idname = "machin3.screen_cast"
    bl_label = "MACHIN3: Screen Cast"
    bl_description = "Screen Cast Operators"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        screencast_keys = get_addon('Screencast Keys')[0]

        if screencast_keys:
            return "Screen Cast recent Operators and Keys"
        return "Screen Cast Recent Operators"

    def execute(self, context):
        self.get_use_keys(debug=True)

        setattr(context.window_manager, 'M3_screen_cast', not context.window_manager.M3_screen_cast)

        if self.use_screencast_keys or self.use_skribe:
            self.toggle_keys(context)

        force_ui_update(context)

        return {'FINISHED'}

    def get_use_keys(self, debug=False):
        global has_skribe, has_screencast_keys

        if has_skribe is None:
            has_skribe = bool(shutil.which('skribe'))

        if has_screencast_keys is None:
            enabled, foldername, _, _ = get_addon('Screencast Keys')

            if foldername:
                if not enabled and get_prefs().screencast_use_screencast_keys:
                    print("INFO: Enabling Screencast Keys Addon")
                    bpy.ops.preferences.addon_enable(module=foldername)

                has_screencast_keys = True
            else:
                has_screencast_keys = False

        self.use_screencast_keys = has_screencast_keys and get_prefs().screencast_use_screencast_keys
        self.use_skribe = has_skribe and get_prefs().screencast_use_skribe

        if debug:
            print("skribe exists:", has_skribe)
            print("       use it:", self.use_skribe)

            print("screncast keys exists:", has_screencast_keys)
            print("               use it:", self.use_screencast_keys)

    def toggle_keys(self, context, debug=False):
        def toggle_screencast_keys(context):
            enabled = get_addon('Screencast Keys')[0]

            if enabled:

                current = context.workspace
                other = [ws for ws in bpy.data.workspaces if ws != current]

                if other:
                    context.window.workspace = other[0]
                    context.window.workspace = current

                bpy.ops.wm.sk_screencast_keys('INVOKE_DEFAULT')

        def toggle_skribe():
            if is_casting:
                if debug:
                    print("turning skribe ON!")

                try:
                    subprocess.Popen('skribe', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    print("WARNING: SKRIBE not found?")
                    print(e)

            else:
                if debug:
                    print("turning skribe OFF!")

                try:
                    subprocess.Popen('pkill -f SKRIBE'.split())

                except Exception as e:
                    print("WARNING: something went wrong")
                    print(e)

        is_casting = context.window_manager.M3_screen_cast

        if bpy.app.version >= (4, 2, 0):

            if self.use_screencast_keys:
                toggle_screencast_keys(context)

            elif self.use_skribe:
                toggle_skribe()

        else:
            if self.use_skribe:
                toggle_skribe()

            elif self.use_screencast_keys:
                toggle_screencast_keys(context)
