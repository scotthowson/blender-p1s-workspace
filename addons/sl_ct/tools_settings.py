# -*- coding:utf-8 -*-

# #
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110- 1301, USA.
#
# 
# <pep8 compliant>

# ----------------------------------------------------------
# Author: Stephen Leger (s-leger)
#
# ----------------------------------------------------------
# noinspection PyUnresolvedReferences
from bpy.types import (
    PropertyGroup,
    Panel
)
# noinspection PyUnresolvedReferences
from bpy.props import (
    StringProperty, BoolProperty, EnumProperty,
    IntProperty, FloatProperty,
    FloatVectorProperty, PointerProperty,
    CollectionProperty
)
from .snapi.i18n import i18n
from .snapi.types import (
    SnapType,
    ConstraintType
)

from . import bl_info
from . import icons


def get_snap_type(self):
    return SnapType.get()


def set_snap_type(self, mode):
    SnapType.set(mode)
    return None


def get_constraint_type(self):
    return ConstraintType.get()


def set_constraint_type(self, mode):
    ConstraintType.set_axis(mode)
    return None


def get_perpendicular(self):
    return ConstraintType.has(ConstraintType.PERPENDICULAR)


def set_perpendicular(self, state):
    ConstraintType.set_perpendicular(state)
    return None


def get_parallel(self):
    return ConstraintType.has(ConstraintType.PARALLEL)


def set_parallel(self, state):
    ConstraintType.set_parallel(state)
    return None


# noinspection PyPep8Naming
class SLCT_tool_settings(PropertyGroup):

    bl_idname = '%s.tool_settings' % __package__
    bl_label = bl_info['name']

    translation_context = __package__

    # MUST match SnapType and prefs
    snap_elements: EnumProperty(
        name="Snap elements",
        items=(
            ('VERT', "Vertex", "Vertex", 'SNAP_VERTEX', int(SnapType.VERT)),
            ('EDGE', "Edge", "Edge", 'SNAP_EDGE', int(SnapType.EDGE)),
            ('FACE', "Face", "Face", 'SNAP_FACE', int(SnapType.FACE)),
            ('GRID', "Grid", "Grid", 'SNAP_GRID', int(SnapType.GRID)),
            ('EDGE_CENTER', "Edge Center", "Edge Center", 'SNAP_MIDPOINT', int(SnapType.EDGE_CENTER)),
            ('FACE_CENTER', "Face Center", "Face Center", 'SNAP_FACE_CENTER', int(SnapType.FACE_CENTER)),
            ('ORIGIN', "Object origin / cursor", "Object origin / cursor", 'OBJECT_ORIGIN', int(SnapType.ORIGIN)),
            ('BOUNDS', "Bounding box", "Bounding box", 'SHADING_BBOX', int(SnapType.BOUNDS)),
            ('ISOLATED', "Isolated mesh", "Isolated edges/verts (slow)", 'OUTLINER_DATA_MESH', int(SnapType.ISOLATED)),
        ),
        options={'ENUM_FLAG'},
        get=get_snap_type,
        set=set_snap_type
    )
    x_ray: BoolProperty(
        name="X ray",
        description="Snap through geometry",
        default=False
    )
    # Must match with ConstraintType
    constraints: EnumProperty(
        name="Constraint",
        items=(
            ('X', "X", "X axis", icons["x_axis"], int(ConstraintType.AXIS | ConstraintType.X)),
            ('Y', "Y", "Y axis", icons["y_axis"], int(ConstraintType.AXIS | ConstraintType.Y)),
            ('Z', "Z", "Z axis", icons["z_axis"], int(ConstraintType.AXIS | ConstraintType.Z)),
            ('YZ', "YZ", "YZ plane", icons["x_plane"], int(ConstraintType.PLANE | ConstraintType.X)),
            ('XZ', "XZ", "XZ plane", icons["y_plane"], int(ConstraintType.PLANE | ConstraintType.Y)),
            ('XY', "XY", "XY plane", icons["z_plane"], int(ConstraintType.PLANE | ConstraintType.Z)),
        ),
        get=get_constraint_type,
        set=set_constraint_type
    )
    #     ('PERPENDICULAR', "Perpendicular", "Perpendicular", "SNAP_PERPENDICULAR", int(ConstraintType.PERPENDICULAR))
    perpendicular: BoolProperty(
        name="Perpendicular",
        description="Rotate perpendicular to edge",
        get=get_perpendicular,
        set=set_perpendicular
    )
    parallel: BoolProperty(
        name="Parallel",
        description="Rotate parallel to edge",
        get=get_parallel,
        set=set_parallel
    )
    align_to_normal: BoolProperty(
        name="Align to normal",
        description="Align object to normal",
        default=False
    )
    projection: BoolProperty(
        name="Projection",
        description="Project selected vertex to plane / line",
        default=False
    )
    individual_origins: BoolProperty(
        name="Individual origins",
        description="Apply transform in each object local space",
        default=False
    )
    absolute_scale: BoolProperty(
        name="Absolute scale",
        description="Keyboard scale values are absolute",
        default=False
    )
    snap_to_self: BoolProperty(
        name="Snap to self",
        description="Object does snap to itself",
        default=True
    )
    linked_copy: BoolProperty(
        name="Instance",
        description="Link object's data",
        default=True
    )
    collection_instances: BoolProperty(
        name="Collection instances",
        description="Snap to collection instances",
        default=True
    )


# noinspection PyPep8Naming
class SLCT_PT_tools_options:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"
    bl_label = bl_info['name']

    translation_context = __package__

    def draw(self, context):
        # noinspection PyUnresolvedReferences
        layout = self.layout
        slct = context.window_manager.slct
        layout.use_property_split = True
        layout.use_property_decorate = False
        i18n.prop(layout, slct, "absolute_scale", text="Absolute scale")


# noinspection PyPep8Naming
class SLCT_PT_tools_options_object(SLCT_PT_tools_options, Panel):
    bl_parent_id = "VIEW3D_PT_tools_object_options"
    bl_context = ".objectmode"


# noinspection PyPep8Naming
class SLCT_PT_tools_options_mesh(SLCT_PT_tools_options, Panel):
    bl_parent_id = "VIEW3D_PT_tools_meshedit_options"
    bl_context = ".mesh_edit"


# noinspection PyPep8Naming
class SLCT_PT_tools_options_curve(SLCT_PT_tools_options, Panel):
    bl_context = ".curve_edit"


# TODO: implement tool settings for gp, nurbs etc..

options = (
    SLCT_PT_tools_options_object,
    SLCT_PT_tools_options_mesh,
    SLCT_PT_tools_options_curve
)
