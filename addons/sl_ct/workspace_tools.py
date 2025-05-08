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
import os
# noinspection PyUnresolvedReferences
from bpy.types import (
    WorkSpaceTool,
    UILayout
)
from .snapi.preferences import Prefs
from .snapi.i18n import i18n
from .keymap import Keymap
from .snapi.types import TransformType
from .snapi.transform import Transform
from .snapi.keyboard import Keyboard
from . import __version__
from . import bl_info


# Keymap items key are mode + label
bl_label = "%s %s" % (bl_info['name'], __version__)


def draw_shortcut(layout, text, item, use_row=False):
    """
    Draw shortcut map on right panel or status bar
    :param layout:
    :param text:
    :param item:
    :param use_row:
    :return:
    """
    row = layout
    if use_row:
        row = layout.row(align=True)
    key = item.type
    if item.ctrl:
        i18n.label(row, text="", icon="EVENT_CTRL")
    if item.alt:
        i18n.label(row, text="", icon="EVENT_ALT")
    if item.shift:
        i18n.label(row, text="", icon="EVENT_SHIFT")

    icons = UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys()
    icon = 'BLANK1'
    if "EVENT_%s" % key in icons:
        icon = "EVENT_%s" % key
    else:
        text = "%s (%s)" % (text, key)
    i18n.label(row, text=text, icon=icon)


def draw_settings(context, layout, tool):
    """
    Draw settings on status bar / or panels (right and tool)
    :param context:
    :param layout:
    :param tool:
    :return:
    """
    prefs = Prefs.get(context)

    trs = Transform.get_action()

    props = context.window_manager.slct
    is_panel = context.region.type in {'UI', 'WINDOW'}

    row = layout.row()
    row.use_property_split = False
    i18n.prop(row, props, "snap_elements", text="", expand=True, icon_only=True)
    if is_panel:
        row = layout.row()
        row.use_property_split = False

    i18n.prop(row, props, "collection_instances", text="", emboss=True, icon='OUTLINER_OB_GROUP_INSTANCE')
    i18n.prop(row, props, "x_ray", text="", emboss=True, icon='XRAY')
    icon = "SNAP_OFF"
    if props.snap_to_self:
        icon = "SNAP_ON"
    i18n.prop(row, props, "snap_to_self", text="", emboss=True, icon=icon)

    if is_panel:
        row = layout.row()
        row.use_property_split = False

    i18n.prop(row, props, "constraints", text="", expand=True, icon_only=True)

    if is_panel:
        row = layout.row()
        row.use_property_split = False

    i18n.prop(row, props, "individual_origins", text="", emboss=True, icon='PIVOT_INDIVIDUAL')

    if trs and trs.has(TransformType.ROTATE):
        i18n.prop(row, props, "perpendicular", text="", emboss=True, icon='SNAP_PERPENDICULAR')
        i18n.prop(row, props, "parallel", text="", emboss=True, icon='SNAP_EDGE')

    if trs and trs.has(TransformType.MOVE):
        i18n.prop(row, props, "align_to_normal", text="", emboss=True, icon='SNAP_NORMAL')

    if context.mode in {"EDIT_MESH", "EDIT_CURVE"}:
        i18n.prop(row, props, "projection", text="", emboss=True, icon='MOD_SHRINKWRAP')

    i18n.prop(row, prefs, "show_tooltips", text="", emboss=True, icon="INFO")

    if is_panel:
        row = layout.row()
        row.use_property_split = False

    i18n.prop(row, prefs, "display_type", text="", expand=True, icon_only=True)

    has_keyboard = trs is not None and trs.has(TransformType.KEYBOARD | TransformType.COPY)

    if has_keyboard:

        if is_panel:
            row = layout.row()
            row.use_property_split = False

        if trs.has(TransformType.COPY):
            if props.linked_copy:
                icon = 'LINKED'
            else:
                icon = 'UNLINKED'
            i18n.prop(row, props, "linked_copy", text="", emboss=True, icon=icon)
            row.label(text="%s : %s" % (i18n.translate("Number of copy"), Keyboard.entered))

        else:
            row.label(text="%s : %s" % (i18n.translate("Enter a value"), Keyboard.entered))

    if is_panel:
        layout.separator()
        icon = "DISCLOSURE_TRI_RIGHT"
        if prefs.display_shortcuts:
            icon = "DISCLOSURE_TRI_DOWN"
        row = layout.row(align=True)
        row.use_property_split = False
        i18n.prop(row, prefs, "display_shortcuts", icon=icon, emboss=True, toggle=False)

    if prefs.display_shortcuts or not is_panel:
        layout.separator()

        # hide when not in panel and there is a keyboard action
        # show in panel and when action is not keyboard
        if (prefs.display_shortcuts and is_panel) or (trs is None or not has_keyboard):
            i18n.label(layout, text="Tools")
            km = Keymap.tools_shortcuts(context)
            for k in km.keys():
                draw_shortcut(layout, k, km[k], use_row=is_panel)

        if is_panel:
            layout.separator()
            i18n.label(layout, text="Snap")
            for i, short in enumerate(prefs.keymap):
                if i == 11:
                    layout.separator()
                    i18n.label(layout, text="Constraint")
                elif i == 18:
                    layout.separator()
                    i18n.label(layout, text="Options")
                short.draw(layout, use_row=True)

            i18n.label(layout, text="Disable snap (hold)", icon="EVENT_CTRL")
            i18n.label(layout, text="Round (hold)", icon="EVENT_ALT")
            row = layout.row(align=True)
            i18n.label(row, text="", icon="EVENT_ALT")
            i18n.label(row, text="Round small (hold)", icon="EVENT_SHIFT")

            row = layout.row(align=True)
            i18n.label(row, text="", icon="MOUSE_LMB")
            i18n.label(row, text="Edit mode", icon="EVENT_SHIFT")
            row = layout.row(align=True)
            i18n.label(row, text="Exit edit mode", icon="MOUSE_RMB")

    if is_panel:
        layout.operator(
            "wm.url_open", text="Online documentation", icon="URL", translate=True, text_ctxt=__package__
        ).url = "https://3dservices.ch/cad_transform"


# noinspection PyPep8Naming
class SLCT_transform(WorkSpaceTool):
    """
    Object Mode
    """
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "%s.transform" % __package__
    bl_label = "%s" % bl_label
    bl_description = "Precise transforms operations"
    bl_icon = os.path.join(os.path.dirname(__file__), "icons", "ops.slcad.transform")
    bl_widget = None
    bl_keymap = ()
    translation_context = __package__
    draw_settings = draw_settings


# noinspection PyPep8Naming
class SLCT_transform_edit_mesh(SLCT_transform):
    """
    Edit mesh mode
    """
    bl_context_mode = 'EDIT_MESH'
    bl_idname = "%s.transform_edit_mesh" % __package__


# noinspection PyPep8Naming
class SLCT_transform_edit_curve(SLCT_transform):
    """
    Edit curve mode
    """
    bl_context_mode = 'EDIT_CURVE'
    bl_idname = "%s.transform_edit_curve" % __package__


# noinspection PyPep8Naming
class SLCT_transform_edit_gpencil(SLCT_transform):
    """
    Edit GP mode mode
    """
    bl_context_mode = 'EDIT_GPENCIL'
    bl_idname = "%s.transform_edit_gpencil" % __package__


tools = (
    SLCT_transform,
    SLCT_transform_edit_mesh,
    SLCT_transform_edit_curve
    # SLCT_transform_edit_gpencil
)
