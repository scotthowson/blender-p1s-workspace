# SPDX-FileCopyrightText: 2010-2022 Blender Foundation
#
# SPDX-License-Identifier: GPL-2.0-or-later


import bpy
import bmesh
from mathutils import Matrix
from bpy.types import Operator
from bpy_extras.object_utils import AddObjectHelper
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    FloatVectorProperty,
    StringProperty,
)
from . import createMesh
from bpy_extras import object_utils


class add_mesh_bolt(Operator, AddObjectHelper):
    bl_idname = "mesh.bolt_add"
    bl_label = "Add Bolt"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}
    bl_description = "Construct many types of Bolts"

    MAX_INPUT_NUMBER = 250  # mm

    def update_head_type(self, context):
        # Reset bit type when head type is set to None.
        if self.bf_Head_Type == 'bf_Head_None':
            self.bf_Bit_Type = 'bf_Bit_None'

    Bolt: BoolProperty(name="Bolt",
                       default=True,
                       description="Bolt")
    change: BoolProperty(name="Change",
                         default=False,
                         description="change Bolt")

    # Model Types
    Model_Type_List = [('bf_Model_Bolt', 'BOLT', 'Bolt Model'),
                       ('bf_Model_Nut', 'NUT', 'Nut Model')]
    bf_Model_Type: EnumProperty(
        attr='bf_Model_Type',
        name='Model',
        description='Choose the type off model you would like',
        items=Model_Type_List, default='bf_Model_Bolt'
    )
    # Head Types
    Model_Type_List = [('bf_Head_None', 'NONE', 'No Head'),
                       ('bf_Head_Hex', 'HEX', 'Hex Head'),
                       ('bf_Head_12Pnt', '12 POINT', '12 Point Head'),
                       ('bf_Head_Cap', 'CAP', 'Cap Head'),
                       ('bf_Head_Dome', 'DOME', 'Dome Head'),
                       ('bf_Head_Pan', 'PAN', 'Pan Head'),
                       ('bf_Head_CounterSink', 'COUNTER SINK', 'Counter Sink Head')]
    bf_Head_Type: EnumProperty(
        attr='bf_Head_Type',
        name='Head',
        description='Choose the type off Head you would like',
        items=Model_Type_List, default='bf_Head_Hex',
        update=update_head_type  # Call this function when the head type changes
    )
    # Bit Types
    Bit_Type_List = [('bf_Bit_None', 'NONE', 'No Bit Type'),
                     ('bf_Bit_Allen', 'ALLEN', 'Allen Bit Type'),
                     ('bf_Bit_Torx', 'TORX', 'Torx Bit Type'),
                     ('bf_Bit_Philips', 'PHILLIPS', 'Phillips Bit Type')]
    bf_Bit_Type: EnumProperty(
        attr='bf_Bit_Type',
        name='Bit Type',
        description='Choose the type of bit to you would like',
        items=Bit_Type_List, default='bf_Bit_None'
    )
    # Nut Types
    Nut_Type_List = [('bf_Nut_Hex', 'HEX', 'Hex Nut'),
                     ('bf_Nut_Lock', 'LOCK', 'Lock Nut'),
                     ('bf_Nut_12Pnt', '12 POINT', '12 Point Nut')]
    bf_Nut_Type: EnumProperty(
        attr='bf_Nut_Type',
        name='Nut Type',
        description='Choose the type of nut you would like',
        items=Nut_Type_List, default='bf_Nut_Hex'
    ) # type: ignore
    # Shank Types
    bf_Shank_Length: FloatProperty(
        attr='bf_Shank_Length',
        name='Shank Length (mm)', default=0,
        min=0, soft_min=0, max=MAX_INPUT_NUMBER,
        description='Length of the unthreaded shank',
        unit='NONE',
    ) # type: ignore
    bf_Shank_Dia: FloatProperty(
        attr='bf_Shank_Dia',
        name='Shank Dia (mm)', default=3,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Diameter of the shank',
        unit='NONE',
    ) # type: ignore
    bf_Phillips_Bit_Depth: FloatProperty(
        attr='bf_Phillips_Bit_Depth',
        name='Bit Depth (mm)', default=1.1431535482406616,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Depth of the Phillips Bit',
        unit='NONE',
    )
    bf_Allen_Bit_Depth: FloatProperty(
        attr='bf_Allen_Bit_Depth',
        name='Bit Depth (mm)', default=1.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Depth of the Allen Bit',
        unit='NONE',
    )
    bf_Allen_Bit_Flat_Distance: FloatProperty(
        attr='bf_Allen_Bit_Flat_Distance',
        name='Flat Dist (mm)', default=2.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Flat Distance of the Allen Bit',
        unit='NONE',
    )
    # Torx Size Types
    Torx_Size_Type_List = [('bf_Torx_T10', 'T10', 'T10'),
                           ('bf_Torx_T20', 'T20', 'T20'),
                           ('bf_Torx_T25', 'T25', 'T25'),
                           ('bf_Torx_T30', 'T30', 'T30'),
                           ('bf_Torx_T40', 'T40', 'T40'),
                           ('bf_Torx_T50', 'T50', 'T50'),
                           ('bf_Torx_T55', 'T55', 'T55'),
                           ]

    bf_Torx_Size_Type: EnumProperty(
        attr='bf_Torx_Size_Type',
        name='Torx Size',
        description='Size of the Torx Bit',
        items=Torx_Size_Type_List, default='bf_Torx_T20'
    )
    bf_Torx_Bit_Depth: FloatProperty(
        attr='bf_Torx_Bit_Depth',
        name='Bit Depth (mm)', default=1.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Depth of the Torx Bit',
        unit='NONE',
    )
    bf_Hex_Head_Height: FloatProperty(
        attr='bf_Hex_Head_Height',
        name='Head Height (mm)', default=2,
        min=0, soft_min=0, max=MAX_INPUT_NUMBER,
        description='Height of the Hex Head',
        unit='NONE',
    )
    bf_Hex_Head_Flat_Distance: FloatProperty(
        attr='bf_Hex_Head_Flat_Distance',
        name='Flat Dist (mm)', default=5.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Flat Distance of the Hex Head',
        unit='NONE',
    )
    bf_12_Point_Head_Height: FloatProperty(
        attr='bf_12_Point_Head_Height',
        name='Head Height (mm)', default=3.0,
        min=0, soft_min=0, max=MAX_INPUT_NUMBER,
        description='Height of the 12 Point Head',
        unit='NONE',
    )
    bf_12_Point_Head_Flat_Distance: FloatProperty(
        attr='bf_12_Point_Head_Flat_Distance',
        name='Flat Dist (mm)', default=3.0,
        min=0.001, soft_min=0,  # limit to 0.001 to avoid calculation error
        max=MAX_INPUT_NUMBER,
        description='Flat Distance of the 12 Point Head',
        unit='NONE',
    )
    bf_12_Point_Head_Flange_Dia: FloatProperty(
        attr='bf_12_Point_Head_Flange_Dia',
        name='12 Point Head Flange Dia (mm)', default=5.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Flange diameter of the 12 point Head',
        unit='NONE',
    )
    bf_CounterSink_Head_Dia: FloatProperty(
        attr='bf_CounterSink_Head_Dia',
        name='Head Dia (mm)', default=6.300000190734863,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Diameter of the Counter Sink Head',
        unit='NONE',
    )
    bf_CounterSink_Head_Angle: FloatProperty(
        attr='bf_CounterSink_Head_Angle',
        name='Head angle', default=1.5708,
        min=0.5, soft_min=0.5,
        max=2.62,
        description='Included Angle of the Counter Sink Head',
        unit='ROTATION',
    )
    bf_Cap_Head_Height: FloatProperty(
        attr='bf_Cap_Head_Height',
        name='Head Height (mm)', default=3,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Height of the Cap Head',
        unit='NONE',
    )
    bf_Cap_Head_Dia: FloatProperty(
        attr='bf_Cap_Head_Dia',
        name='Head Dia (mm)', default=5.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Diameter of the Cap Head',
        unit='NONE',
    )
    bf_Dome_Head_Dia: FloatProperty(
        attr='bf_Dome_Head_Dia',
        name='Dome Head Dia (mm)', default=5.599999904632568,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Length of the unthreaded shank',
        unit='NONE',
    )
    bf_Pan_Head_Dia: FloatProperty(
        attr='bf_Pan_Head_Dia',
        name='Pan Head Dia (mm)', default=5.599999904632568,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Diameter of the Pan Head',
        unit='NONE',
    )

    bf_Philips_Bit_Dia: FloatProperty(
        attr='bf_Philips_Bit_Dia',
        name='Bit Dia (mm)', default=1.8199999332427979,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Diameter of the Philips Bit',
        unit='NONE',
    )

    bf_Thread_Length: FloatProperty(
        attr='bf_Thread_Length',
        name='Thread Length (mm)', default=6,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Length of the Thread',
        unit='NONE',
    )

    bf_Major_Dia: FloatProperty(
        attr='bf_Major_Dia',
        name='Major Dia (mm)', default=3,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Outside diameter of the Thread',
        unit='NONE',
    )

    bf_Pitch: FloatProperty(
        attr='bf_Pitch',
        name='Pitch (mm)', default=0.3499999940395355,
        min=0.1, soft_min=0.1,
        max=7.0,
        description='Pitch if the thread',
        unit='NONE',
    )
    bf_Minor_Dia: FloatProperty(
        attr='bf_Minor_Dia',
        name='Minor Dia (mm)', default=2.6211137771606445,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Inside diameter of the Thread',
        unit='NONE',
    )
    bf_Crest_Percent: FloatProperty(
        attr='bf_Crest_Percent',
        name='Crest Percent', default=12.5,
        min=1, soft_min=1,
        max=90,
        description='Percent of the pitch that makes up the Crest',
    )
    bf_Root_Percent: FloatProperty(
        attr='bf_Root_Percent',
        name='Root Percent', default=25,
        min=1, soft_min=1,
        max=90,
        description='Percent of the pitch that makes up the Root',
    )
    bf_Div_Count: IntProperty(
        attr='bf_Div_Count',
        name='Div count', default=36,
        min=4, soft_min=4,
        max=4096,
        description='Div count determine circle resolution',
    )
    bf_Hex_Nut_Height: FloatProperty(
        attr='bf_Hex_Nut_Height',
        name='Hex Nut Height (mm)', default=2.4000000953674316,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Height of the Hex Nut',
        unit='NONE',
    )
    bf_Hex_Nut_Flat_Distance: FloatProperty(
        attr='bf_Hex_Nut_Flat_Distance',
        name='Hex Nut Flat Dist (mm)', default=5.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Flat distance of the Hex Nut',
        unit='NONE',
    )
    bf_12_Point_Nut_Height: FloatProperty(
        attr='bf_12_Point_Nut_Height',
        name='12 Point Nut Height (mm)', default=2.4000000953674316,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Height of the 12 Point Nut',
        unit='NONE',
    )

    bf_12_Point_Nut_Flat_Distance: FloatProperty(
        attr='bf_12_Point_Nut_Flat_Distance',
        name='12 Point Nut Flat Dist (mm)', default=3.0,
        min=0.001, soft_min=0,  # limit to 0.001 to avoid calculation error
        max=MAX_INPUT_NUMBER,
        description='Flat distance of the 12 point Nut',
        unit='NONE',
    )
    bf_12_Point_Nut_Flange_Dia: FloatProperty(
        attr='bf_12_Point_Nut_Flange_Dia',
        name='12 Point Nut Flange Dia (mm)', default=5.5,
        min=0, soft_min=0,
        max=MAX_INPUT_NUMBER,
        description='Flange diameter of the 12 point Nut',
        unit='NONE',
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        # ENUMS
        col.prop(self, 'bf_Model_Type')
        col.separator()

        # Bit
        if self.bf_Model_Type == 'bf_Model_Bolt':
            if self.bf_Head_Type == 'bf_Head_None':
                col.label(text="No bit type availabe when Head is None.")
            else:
                col.prop(self, 'bf_Bit_Type')
            if self.bf_Bit_Type == 'bf_Bit_None':
                pass
            elif self.bf_Bit_Type == 'bf_Bit_Allen':
                col.prop(self, 'bf_Allen_Bit_Depth')
                col.prop(self, 'bf_Allen_Bit_Flat_Distance')
            elif self.bf_Bit_Type == 'bf_Bit_Torx':
                col.prop(self, 'bf_Torx_Bit_Depth')
                col.prop(self, 'bf_Torx_Size_Type')
            elif self.bf_Bit_Type == 'bf_Bit_Philips':
                col.prop(self, 'bf_Phillips_Bit_Depth')
                col.prop(self, 'bf_Philips_Bit_Dia')
            col.separator()
        # Head
        if self.bf_Model_Type == 'bf_Model_Bolt':
            col.prop(self, 'bf_Head_Type')
            if self.bf_Head_Type == 'bf_Head_None':
                pass
            elif self.bf_Head_Type == 'bf_Head_Hex':
                col.prop(self, 'bf_Hex_Head_Height')
                col.prop(self, 'bf_Hex_Head_Flat_Distance')
            elif self.bf_Head_Type == 'bf_Head_12Pnt':
                col.prop(self, 'bf_12_Point_Head_Height')
                col.prop(self, 'bf_12_Point_Head_Flat_Distance')
                col.prop(self, 'bf_12_Point_Head_Flange_Dia')
            elif self.bf_Head_Type == 'bf_Head_Cap':
                col.prop(self, 'bf_Cap_Head_Height')
                col.prop(self, 'bf_Cap_Head_Dia')
            elif self.bf_Head_Type == 'bf_Head_Dome':
                col.prop(self, 'bf_Dome_Head_Dia')
            elif self.bf_Head_Type == 'bf_Head_Pan':
                col.prop(self, 'bf_Pan_Head_Dia')
            elif self.bf_Head_Type == 'bf_Head_CounterSink':
                col.prop(self, 'bf_CounterSink_Head_Dia')
                col.prop(self, 'bf_CounterSink_Head_Angle')
            col.separator()
        # Shank
        if self.bf_Model_Type == 'bf_Model_Bolt':
            col.label(text='Shank')
            col.prop(self, 'bf_Shank_Length')
            col.prop(self, 'bf_Shank_Dia')
            col.separator()
        # Nut
        if self.bf_Model_Type == 'bf_Model_Nut':
            col.prop(self, 'bf_Nut_Type')
            if self.bf_Nut_Type == "bf_Nut_12Pnt":
                col.prop(self, 'bf_12_Point_Nut_Height')
                col.prop(self, 'bf_12_Point_Nut_Flat_Distance')
                col.prop(self, 'bf_12_Point_Nut_Flange_Dia')
            else:
                col.prop(self, 'bf_Hex_Nut_Height')
                col.prop(self, 'bf_Hex_Nut_Flat_Distance')

        # Thread
        col.label(text='Thread')
        if self.bf_Model_Type == 'bf_Model_Bolt':
            col.prop(self, 'bf_Thread_Length')
        col.prop(self, 'bf_Major_Dia')
        col.prop(self, 'bf_Minor_Dia')
        col.prop(self, 'bf_Pitch')
        col.prop(self, 'bf_Crest_Percent')
        col.prop(self, 'bf_Root_Percent')
        col.prop(self, 'bf_Div_Count')

        if not self.change:
            # generic transform props
            col.separator()
            col.prop(self, 'align')
            col.prop(self, 'location')
            col.prop(self, 'rotation')

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):

        # This formula ensures that bolts (or other objects) are generated at their default sizes 
        # regardless of the unit scale setting in the scene. It normalizes the scale to maintain
        # consistent dimensions across various unit configurations.
        scene = context.scene
        adjusted_scale = 0.001 / scene.unit_settings.scale_length

        if bpy.context.mode == "OBJECT":
            if context.selected_objects != [] and context.active_object and \
                (context.active_object.data is not None) and ('Bolt' in context.active_object.data.keys()) and \
                    (self.change):
                obj = context.active_object
                use_smooth = bool(obj.data.polygons[0].use_smooth)      # Copy value, do not take a reference

                mesh = createMesh.Create_New_Mesh(self, context, adjusted_scale)

                # Modify existing mesh data object by replacing geometry (but leaving materials etc)
                bm = bmesh.new()
                bm.from_mesh(mesh)
                bm.to_mesh(obj.data)
                bm.free()

                # Preserve flat/smooth choice. New mesh is flat by default
                if use_smooth:
                    bpy.ops.object.shade_smooth()
                else:
                    bpy.ops.object.shade_flat()

                bpy.data.meshes.remove(mesh)

                try:
                    bpy.ops.object.vertex_group_remove(all=True)
                except:
                    pass

            else:
                mesh = createMesh.Create_New_Mesh(self, context, adjusted_scale)
                obj = object_utils.object_data_add(context, mesh, operator=self)

            obj.data["Bolt"] = True
            obj.data["change"] = False
            for prm in BoltParameters():
                obj.data[prm] = getattr(self, prm)

        if bpy.context.mode == "EDIT_MESH":
            obj = context.edit_object
            mesh = createMesh.Create_New_Mesh(self, context, adjusted_scale)

            bm = bmesh.from_edit_mesh(obj.data)                 # Access edit mode's mesh data
            bm.from_mesh(mesh)                                  # Append new mesh data
            bmesh.update_edit_mesh(obj.data)                    # Flush changes (update edit mode's view)

            bpy.data.meshes.remove(mesh)                        # Remove temporary mesh

        return {'FINISHED'}

    def invoke(self, context, event):
        self.execute(context)

        return {'FINISHED'}

# Register:


def Bolt_contex_menu(self, context):
    bl_label = 'Change'

    obj = context.object
    layout = self.layout

    if obj and obj.data is not None and 'Bolt' in obj.data.keys():
        props = layout.operator("mesh.bolt_add", text="Change Bolt")
        props.change = True
        for prm in BoltParameters():
            setattr(props, prm, obj.data[prm])
        layout.separator()


def menu_func_bolt(self, context):
    layout = self.layout
    layout.separator()
    oper = self.layout.operator(add_mesh_bolt.bl_idname, text="Bolt", icon="MOD_SCREW")
    oper.change = False


classes = (
    add_mesh_bolt,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_mesh_add.append(menu_func_bolt)
    bpy.types.VIEW3D_MT_object_context_menu.prepend(Bolt_contex_menu)


def unregister():
    bpy.types.VIEW3D_MT_object_context_menu.remove(Bolt_contex_menu)
    bpy.types.VIEW3D_MT_mesh_add.remove(menu_func_bolt)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def BoltParameters():
    BoltParameters = [
        "bf_Model_Type",
        "bf_Head_Type",
        "bf_Bit_Type",
        "bf_Nut_Type",
        "bf_Shank_Length",
        "bf_Shank_Dia",
        "bf_Phillips_Bit_Depth",
        "bf_Allen_Bit_Depth",
        "bf_Allen_Bit_Flat_Distance",
        "bf_Torx_Bit_Depth",
        "bf_Torx_Size_Type",
        "bf_Hex_Head_Height",
        "bf_Hex_Head_Flat_Distance",
        "bf_CounterSink_Head_Dia",
        "bf_CounterSink_Head_Angle",
        "bf_Cap_Head_Height",
        "bf_Cap_Head_Dia",
        "bf_Dome_Head_Dia",
        "bf_Pan_Head_Dia",
        "bf_Philips_Bit_Dia",
        "bf_Thread_Length",
        "bf_Major_Dia",
        "bf_Pitch",
        "bf_Minor_Dia",
        "bf_Crest_Percent",
        "bf_Root_Percent",
        "bf_Div_Count",
        "bf_Hex_Nut_Height",
        "bf_Hex_Nut_Flat_Distance",
    ]
    return BoltParameters
