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
from .snapi.logger import get_logger

# noinspection PyUnresolvedReferences
from bpy.types import (
    Panel,
    AddonPreferences,
    Menu,
    PropertyGroup,
    Object,
    Collection
)
# noinspection PyUnresolvedReferences
from bpy.props import (
    StringProperty, BoolProperty, EnumProperty,
    IntProperty, FloatProperty,
    FloatVectorProperty, PointerProperty,
    CollectionProperty
    )
from .snapi.types import (
    SnapType
)
from .snapi.transform import (
    Transform
)
from . import icons, icons_names
from .snapi.i18n import i18n
logger = get_logger(__name__, 'ERROR')


# noinspection PyPep8Naming
class SLCT_keymap(PropertyGroup):

    name: StringProperty(name="name", default="event")
    label: StringProperty(name="label", default="Event")
    key: EnumProperty(
        name="key",
        default="A",
        items=(
            ('A', 'A', 'A', 'EVENT_A', 0),
            ('B', 'B', 'B', 'EVENT_B', 1),
            ('C', 'C', 'C', 'EVENT_C', 2),
            ('D', 'D', 'D', 'EVENT_D', 3),
            ('E', 'E', 'E', 'EVENT_E', 4),
            ('F', 'F', 'F', 'EVENT_F', 5),
            ('G', 'G', 'G', 'EVENT_G', 6),
            ('H', 'H', 'H', 'EVENT_H', 7),
            ('I', 'I', 'I', 'EVENT_I', 8),
            ('J', 'J', 'J', 'EVENT_J', 9),
            ('K', 'K', 'K', 'EVENT_K', 10),
            ('L', 'L', 'L', 'EVENT_L', 11),
            ('M', 'M', 'M', 'EVENT_M', 12),
            ('N', 'N', 'N', 'EVENT_N', 13),
            ('O', 'O', 'O', 'EVENT_O', 14),
            ('P', 'P', 'P', 'EVENT_P', 15),
            ('Q', 'Q', 'Q', 'EVENT_Q', 16),
            ('R', 'R', 'R', 'EVENT_R', 17),
            ('S', 'S', 'S', 'EVENT_S', 18),
            ('T', 'T', 'T', 'EVENT_T', 19),
            ('U', 'U', 'U', 'EVENT_U', 20),
            ('V', 'V', 'V', 'EVENT_V', 21),
            ('W', 'W', 'W', 'EVENT_W', 22),
            ('X', 'X', 'X', 'EVENT_X', 23),
            ('Y', 'Y', 'Y', 'EVENT_Y', 24),
            ('Z', 'Z', 'Z', 'EVENT_Z', 25),
            ('F1', 'F1', 'F1', 'EVENT_F1', 26),
            ('F2', 'F2', 'F2', 'EVENT_F2', 27),
            ('F3', 'F3', 'F3', 'EVENT_F3', 28),
            ('F4', 'F4', 'F4', 'EVENT_F4', 29),
            ('F5', 'F5', 'F5', 'EVENT_F5', 30),
            ('F6', 'F6', 'F6', 'EVENT_F6', 31),
            ('F7', 'F7', 'F7', 'EVENT_F7', 32),
            ('F8', 'F8', 'F8', 'EVENT_F8', 33),
            ('F9', 'F9', 'F9', 'EVENT_F9', 34),
            ('F10', 'F10', 'F10', 'EVENT_F10', 35),
            ('F11', 'F11', 'F11', 'EVENT_F11', 36),
            ('F12', 'F12', 'F12', 'EVENT_F12', 37),
            ('ZERO',  '0', '0', icons["ZERO"], 38),
            ('ONE',   '1', '1', icons["ONE"], 39),
            ('TWO',   '2', '2', icons["TWO"], 40),
            ('THREE', '3', '3', icons["THREE"], 41),
            ('FOUR',  '4', '4', icons["FOUR"], 42),
            ('FIVE',  '5', '5', icons["FIVE"], 43),
            ('SIX',   '6', '6', icons["SIX"], 44),
            ('SEVEN', '7', '7', icons["SEVEN"], 45),
            ('EIGHT', '8', '8', icons["EIGHT"], 46),
            ('NINE',  '9', '9', icons["NINE"], 47),
            ('TAB', 'TAB', 'TAB', 'EVENT_TAB', 48),
            ('SPACE', 'SPACE', 'SPACE', 'EVENT_SPACEKEY', 49),
            ('BACK_SPACE', 'BACK_SPACE', 'BACK_SPACE', icons['BACK_SPACE'], 50),
            ('NUMPAD_ZERO', 'NUMPAD_0', 'NUMPAD_0', icons["ZERO"], 51),
            ('NUMPAD_ONE', 'NUMPAD_1', 'NUMPAD_1', icons["ONE"], 52),
            ('NUMPAD_TWO', 'NUMPAD_2', 'NUMPAD_2', icons["TWO"], 53),
            ('NUMPAD_THREE', 'NUMPAD_3', 'NUMPAD_3', icons["THREE"], 54),
            ('NUMPAD_FOUR', 'NUMPAD_4', 'NUMPAD_4', icons["FOUR"], 55),
            ('NUMPAD_FIVE', 'NUMPAD_5', 'NUMPAD_5', icons["FIVE"], 56),
            ('NUMPAD_SIX', 'NUMPAD_6', 'NUMPAD_6', icons["SIX"], 57),
            ('NUMPAD_SEVEN', 'NUMPAD_7', 'NUMPAD_7', icons["SEVEN"], 58),
            ('NUMPAD_EIGHT', 'NUMPAD_8', 'NUMPAD_8', icons["EIGHT"], 59),
            ('NUMPAD_NINE', 'NUMPAD_9', 'NUMPAD_9', icons["NINE"], 60)
        )
    )
    # ('MIDDLEMOUSE', "Middle Mouse", "Middle Mouse button", "MOUSE_MMB", 61)
    alt: BoolProperty(default=False, name="alt")
    shift: BoolProperty(default=False, name="shift")
    ctrl: BoolProperty(default=False, name="ctrl")

    def draw_pref(self, layout):
        row = layout.row(align=True)
        split = row.split(factor=0.5)
        col = split.column()
        row = col.row(align=True)
        row.prop(self, "label", text="")
        col = split.column()
        row = col.row()
        row.prop(self, "key", text="", icon_only=True)
        row.prop(self, "ctrl", icon="EVENT_CTRL", icon_only=True)
        row.prop(self, "alt", icon="EVENT_ALT", icon_only=True)
        row.prop(self, "shift", icon="EVENT_SHIFT", icon_only=True)

    def draw(self, layout, use_row=True, icon_only=False):
        """Draw shortcut to status bar or panel
        :param layout:
        :param use_row:
        :param icon_only:
        :return:
        """
        row = layout

        # global icon_man
        if any([self.ctrl, self.alt, self.shift]):
            if use_row:
                row = layout.row(align=True)
            if self.ctrl:
                row.label(text="", icon="EVENT_CTRL")
            if self.alt:
                row.label(text="", icon="EVENT_ALT")
            if self.shift:
                row.label(text="", icon="EVENT_SHIFT")

        if icon_only:
            text = ""
        else:
            text = self.label

        if self.key in icons_names:
            # Custom icons
            row.label(text=text, icon_value=icons[self.key])

        elif "NUMPAD_" in self.key and self.key[7:] in icons_names:
            # Custom numeric icons, skip "NUMPAD_"
            row.label(text=text, icon_value=icons[self.key[7:]])

        else:
            icon = self.bl_rna.properties['key'].enum_items[self.key].icon
            row.label(text=text, icon=icon)

    def __str__(self):
        key = ""
        if self.ctrl:
            key += 'CTRL+'
        if self.alt:
            key += 'ALT+'
        if self.shift:
            key += 'SHIFT+'
        return "%s (%s%s)" % (self.label, key, self.key)

    def tip(self):
        """
        :return: key(s) and label, keys are compatible with both internal and blender's one
        """
        key = []

        if self.ctrl:
            key.append('EVENT_CTRL')
        if self.alt:
            key.append('EVENT_ALT')
        if self.shift:
            key.append('EVENT_SHIFT')

        if "NUMPAD_" in self.key:
            key.append(self.key[7:])

        elif self.key in icons_names:
            key.append(self.key)

        else:
            key.append(self.bl_rna.properties['key'].enum_items[self.key].icon)
        # tooltip handle translation
        return key, self.label

    def match(self, signature, value="PRESS"):
        return (self.alt, self.ctrl, self.shift, self.key, value) == signature


def update_display_type(self, context):
    Transform.update_display_type(self.display_type)


# noinspection PyPep8Naming
class SLCT_Prefs(AddonPreferences):
    bl_idname = __package__

    translation_context = __package__

    # Must match tools_settings
    snap_elements: EnumProperty(
        name="snap_elements",
        items=(
            ('VERT', "Vertex", "Vertex", 'SNAP_VERTEX', int(SnapType.VERT)),
            ('EDGE', "Edge", "Edge", 'SNAP_EDGE', int(SnapType.EDGE)),
            ('FACE', "Face", "Face", 'SNAP_FACE', int(SnapType.FACE)),
            ('GRID', "Grid", "Grid", 'SNAP_GRID', int(SnapType.GRID)),
            ('EDGE_CENTER', "Edge Center", "Edge Center", 'SNAP_MIDPOINT', int(SnapType.EDGE_CENTER)),
            ('FACE_CENTER', "Face Center", "Face Center", 'SNAP_FACE_CENTER', int(SnapType.FACE_CENTER)),
            ('ORIGIN', "Object origin / cursor", "Object origin / cursor", 'OBJECT_ORIGIN', int(SnapType.ORIGIN)),
            ('BOUNDS', "Bounding box", "Bounding box", 'SHADING_BBOX', int(SnapType.BOUNDS)),
            ('ISOLATED', "Isolated mesh", "Isolated edges / verts (slow)", 'OUTLINER_DATA_MESH', int(SnapType.ISOLATED))
        ),
        options={'ENUM_FLAG'},
        default={'VERT', 'EDGE', 'FACE', 'EDGE_CENTER', 'FACE_CENTER', 'ORIGIN', 'BOUNDS', 'ISOLATED'}
    )
    space_order: EnumProperty(
        name="Space order",
        items=(
            ('LWU', "Local / World / User", "Space toggle order Local / World / User"),
            ('LUW', "Local / User / World", "Space toggle order Local / User / World"),
            ('WLU', "World / Local / User", "Space toggle order World / Local / User"),
            ('WUL', "World / User / Local", "Space toggle order World / User / Local"),
            ('UWL', "User / World / Local", "Space toggle order User / World / Local"),
            ('ULW', "User / Local / World", "Space toggle order User / Local / World"),
        )
    )
    cursor_theme: EnumProperty(
        name="Cursor theme",
        items=(
            ('DARK', "Dark", "Dark", 0),
            ('LIGHT', "Light", "Light", 1),
         )
    )
    cursor_size: EnumProperty(
        name="Cursor size",
        items=(
            ('32', "Small", "Small (32 px)", 0),
            ('48', "Medium", "Medium (48 px)", 1),
            ('64', "Large", "Large (64 px)", 2),
            ('128', "Extra large", "Extra large (128 px)", 3),
        ),
        default="48"
    )
    use_adaptive_units: BoolProperty(
        name="Adaptive units",
        description="Units may change according to size magnitude",
        default=True
    )

    use_numpad_for_navigation: BoolProperty(
        name="Use numpad for navigation",
        description="Use numpad for screen navigation, hold ALT to start numerical input",
        default=False
    )
    release_confirm: BoolProperty(
        name="Release confirm",
        description="Confirm on mouse release",
        default=False
    )
    confirm_exit: BoolProperty(
        name="Exit on confirm",
        description="Exit on confirm",
        default=True
    )
    keep_snap_on_start: BoolProperty(
        name="Keep snap mode",
        description="Keep current snap mode when re-starting operators\n"
        "When disabled, use preferences snap mode on re-start",
        default=False
    )
    keep_constraint_on_exit: BoolProperty(
        name="Keep constraint mode",
        description="Keep current constraint mode when re-starting operator",
        default=False
    )
    use_fast_rotation: BoolProperty(
        name="Fast rotation pivot",
        description="Setup rotation pivot using 2 points",
        default=True
    )
    use_fast_scale: BoolProperty(
        name="Fast scale pivot",
        description="Setup scale pivot using 2 points",
        default=True
    )
    absolute_scale: BoolProperty(
        name="Absolute scale",
        description="Keyboard scale values are absolute",
        default=False
    )
    sanitize_scale: BoolProperty(
        name="Sanitize scale",
        description="Reset 0 scale axis of objects",
        default=True
    )

    snap_radius: IntProperty(
        name="Snap radius in pixels",
        description="How far we do we detect items (size in pixels) default 12",
        default=12
    )
    font_size: IntProperty(
        name="Text size in pixels",
        description="Text font size in pixels default 16",
        default=16
    )
    line_width: FloatProperty(
        name="Line width",
        description="Width of lines",
        default=2.5
    )
    point_size: FloatProperty(
        name="Point size",
        description="Size of points",
        default=6.5
    )
    detectable_point_size: FloatProperty(
        name="Detectable Point size",
        description="Size of detectable points",
        default=4
    )
    handle_size: IntProperty(
        name="Handle Size",
        description="Handle size in pixels",
        default=15
    )
    color_preview: FloatVectorProperty(
        name="Preview",
        description="Base color for previews",
        subtype='COLOR_GAMMA',
        default=(1.0, 1.0, 0.0, 0.2),
        size=4,
        min=0, max=1
    )
    color_tooltips_keys: FloatVectorProperty(
        name="Tips keys",
        description="Tooltip keys",
        subtype='COLOR_GAMMA',
        default=(0, 0, 0, 0.5),
        size=4,
        min=0, max=1
    )
    color_tooltips_header: FloatVectorProperty(
        name="Tip header",
        description="Tooltip header",
        subtype='COLOR_GAMMA',
        default=(0, 0.2, 0.2, 0.7),
        size=4,
        min=0, max=1
    )
    color_feedback_frame: FloatVectorProperty(
        name="Feedback frame",
        description="Feedback frame",
        subtype='COLOR_GAMMA',
        default=(0.0, 0.0, 0.0, 0.8),
        size=4,
        min=0, max=1
    )
    color_feedback_bg: FloatVectorProperty(
        name="Feedback background",
        description="Feedback background",
        subtype='COLOR_GAMMA',
        default=(1.0, 1.0, 1.0, 0.3),
        size=4,
        min=0, max=1
    )
    color_feedback_text: FloatVectorProperty(
        name="Feedback text",
        description="Feedback text",
        subtype='COLOR_GAMMA',
        default=(0.0, 0.0, 0.0, 0.8),
        size=4,
        min=0, max=1
    )
    color_handle_normal: FloatVectorProperty(
        name="Handle normal",
        description="Base handle color when not selected",
        subtype='COLOR_GAMMA',
        default=(0, 1.0, 1.0, 0.7),
        size=4,
        min=0, max=1
    )
    color_handle_hover: FloatVectorProperty(
        name="Handle over",
        description="Handle color when mouse over",
        subtype='COLOR_GAMMA',
        default=(1.0, 1.0, 0.0, 0.7),
        size=4,
        min=0, max=1
    )
    color_handle_active: FloatVectorProperty(
        name="Handle active",
        description="Handle colour when active",
        subtype='COLOR_GAMMA',
        default=(1.0, 0.0, 0.0, 0.8),
        size=4,
        min=0, max=1
    )
    color_active: FloatVectorProperty(
        name="Active",
        description="Helper colour when active",
        subtype='COLOR_GAMMA',
        default=(1.0, 0.0, 1.0, 0.8),
        size=4,
        min=0, max=1
    )
    color_hover: FloatVectorProperty(
        name="Over",
        description="Over items colour",
        subtype='COLOR_GAMMA',
        default=(1.0, 1.0, 0.0, 0.8),
        size=4,
        min=0, max=1
    )
    color_selected: FloatVectorProperty(
        name="Selected",
        description="Selected items colour",
        subtype='COLOR_GAMMA',
        default=(1.0, 0.0, 0.0, 0.5),
        size=4,
        min=0, max=1
    )
    color_helpers_normal: FloatVectorProperty(
        name="Snap helpers normal",
        description="Snap helpers items colour",
        subtype='COLOR_GAMMA',
        default=(0.0, 1.0, 1.0, 0.5),
        size=4,
        min=0, max=1
    )
    color_helpers_hover: FloatVectorProperty(
        name="Snap helpers over",
        description="Snap helpers items colour",
        subtype='COLOR_GAMMA',
        default=(1.0, 1.0, 0.0, 0.5),
        size=4,
        min=0, max=1
    )
    color_detectable: FloatVectorProperty(
        name="Detectable points",
        description="Detectable points",
        subtype='COLOR_GAMMA',
        default=(1, 1, 1, 0.2),
        size=4,
        min=0, max=1
    )
    color_detectable_bounds: FloatVectorProperty(
        name="Bounding box",
        description="Bounding box",
        subtype='COLOR_GAMMA',
        default=(0, 1, 0, 0.2),
        size=4,
        min=0, max=1
    )
    color_detectable_origin: FloatVectorProperty(
        name="Origin",
        description="Object origin",
        subtype='COLOR_GAMMA',
        default=(0, 0, 1, 0.4),
        size=4,
        min=0, max=1
    )
    color_detectable_isolated: FloatVectorProperty(
        name="Isolated points",
        description="Isolated points",
        subtype='COLOR_GAMMA',
        default=(1, 0, 1, 0.2),
        size=4,
        min=0, max=1
    )
    color_detectable_median: FloatVectorProperty(
        name="Median point",
        description="Median point of selection",
        subtype='COLOR_GAMMA',
        default=(1, 0, 1, 1),
        size=4,
        min=0, max=1
    )
    color_detectable_center: FloatVectorProperty(
        name="Center of selection",
        description="Center of selection bounding box",
        subtype='COLOR_GAMMA',
        default=(0, 1, 1, 1),
        size=4,
        min=0, max=1
    )
    color_text: FloatVectorProperty(
        name="Text",
        description="Text color",
        subtype='COLOR_GAMMA',
        default=(0.95, 0.95, 0.95, 1.0),
        size=4,
        min=0, max=1
    )
    color_average: FloatVectorProperty(
        name="Average",
        description="Average circle color",
        subtype='COLOR_GAMMA',
        default=(0, 0.5, 1, 0.3),
        size=4,
        min=0, max=1
    )
    color_preview_context: FloatVectorProperty(
        name="Preview context",
        description="Preview context color",
        subtype='COLOR_GAMMA',
        default=(1, 0, 0.5, 0.3),
        size=4,
        min=0, max=1
    )
    color_snap: FloatVectorProperty(
        name="Snap",
        description="Snap circle color",
        subtype='COLOR_GAMMA',
        default=(1, 0.5, 0, 0.7),
        size=4,
        min=0, max=1
    )
    show_tooltips: BoolProperty(
        name="Display tooltips",
        description="Display tooltips on screen",
        default=True
    )
    display_shortcuts: BoolProperty(
        name="Display shortcuts",
        description="Display shortcuts in status bar",
        default=True
    )
    max_number_of_vertex: IntProperty(
        name="Max number of vertex",
        description="Display as bound box when number of vertex exceed this value",
        default=1000
    )
    display_type: EnumProperty(
        name="Viewport Display",
        description="Temporary viewport display mode of moving object",
        items=(
            ('WIRE', "Wireframe", "Wireframe", 'SHADING_WIRE', 0),
            ('SOLID', "Solid", "Solid", 'SHADING_SOLID', 1),
            ('TEXTURED', "Textured", "Textured", 'SHADING_TEXTURE', 2)
        ),
        default='WIRE',
        update=update_display_type
    )
    keymap: CollectionProperty(type=SLCT_keymap)

    def template_color(self, layout, label, prop, text=""):
        row = layout.row()
        col = row.column()
        i18n.label(col, text=label)
        col = row.column()
        col.prop(self, prop, text=text)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        i18n.label(box, text="Interaction")

        i18n.prop(box, self, "release_confirm")
        i18n.prop(box, self, "confirm_exit")
        i18n.prop(box, self, "use_numpad_for_navigation")
        i18n.prop(box, self, "show_tooltips")
        i18n.prop(box, self, "keep_constraint_on_exit")

        box = layout.box()
        i18n.label(box, text="CAD Transform 0.9.x compatibility")
        i18n.prop(box, self, "use_fast_rotation")
        i18n.prop(box, self, "use_fast_scale")

        box = layout.box()
        i18n.label(box, text="Operators options")
        i18n.prop(box, self, "space_order")
        i18n.prop(box, self, "absolute_scale")

        i18n.prop(box, self, "use_adaptive_units")
        i18n.prop(box, self, "max_number_of_vertex")
        box = layout.box()
        i18n.label(box, "Temporary display type")
        row = box.row()
        row.use_property_split = False
        i18n.prop(row, self, "display_type", text="", expand=True, icon_only=True)
        box = layout.box()
        i18n.label(box, text="Default snap")
        i18n.prop(box, self, "snap_radius")
        row = box.row()
        row.use_property_split = False
        i18n.prop(row, self, "snap_elements", text="", expand=True, icon_only=True)
        i18n.prop(box, self, "keep_snap_on_start")

        box = layout.box()
        i18n.label(box, text="Sanity check")
        i18n.prop(box, self, "sanitize_scale")

        box = layout.box()
        i18n.label(box, text="General")
        i18n.prop(box, self, "line_width")
        i18n.prop(box, self, "point_size")
        box = layout.box()
        i18n.label(box, text="Cursor")
        i18n.prop(box, self, "cursor_size")
        i18n.prop(box, self, "cursor_theme")
        box = layout.box()
        i18n.label(box, text="Feedback")
        i18n.prop(box, self, "font_size")
        self.template_color(box, "Text", "color_text")
        self.template_color(box, "Tooltip header", "color_tooltips_header")
        self.template_color(box, "Tooltip keys", "color_tooltips_keys")
        self.template_color(box, "Feedback frame", "color_feedback_frame")
        self.template_color(box, "Feedback background", "color_feedback_bg")
        self.template_color(box, "Feedback text", "color_feedback_text")
        box = layout.box()
        i18n.label(box, text="Preview")
        self.template_color(box, "Snap circle", "color_snap")
        self.template_color(box, "Average circle", "color_average")
        self.template_color(box, "Preview", "color_preview")
        self.template_color(box, "Preview context", "color_preview_context")
        box = layout.box()
        i18n.label(box, text="Helper")
        self.template_color(box, "Helper", "color_helpers_normal")
        self.template_color(box, "Helper over", "color_helpers_hover")
        box = layout.box()
        i18n.label(box, text="Detectables")
        i18n.prop(box, self, "detectable_point_size")
        self.template_color(box, "Default", "color_detectable")
        self.template_color(box, "Bounding box", "color_detectable_bounds")
        self.template_color(box, "Object origin", "color_detectable_origin")
        self.template_color(box, "Isolated points", "color_detectable_isolated")
        self.template_color(box, "Median point of selection", "color_detectable_median")
        self.template_color(box, "Center of selection", "color_detectable_center")
        box = layout.box()
        i18n.label(box, text="Handles")
        i18n.prop(box, self, "handle_size")
        self.template_color(box, "Handle normal", "color_handle_normal")
        self.template_color(box, "Handle over", "color_handle_hover")
        self.template_color(box, "Handle active", "color_handle_active")

        box = layout.box()
        i18n.label(box, text="Keymap")

        i18n.label(box, text="Snap")
        for key in self.keymap[0:11]:
            key.draw_pref(box)
        i18n.label(box, text="Constraint")
        for key in self.keymap[11:20]:
            key.draw_pref(box)
        i18n.label(box, text="Options")
        for key in self.keymap[21:]:
            key.draw_pref(box)

    def key(self, name):
        k = self.keymap.get(name)
        if k:
            return k.key.lower()
        return ""

    def match(self, name: str, signature: tuple, value="PRESS") -> bool:
        """
        :param name:
        :param signature:
        :param value:
        :return: Bool true when event with name match signature
        """
        shorts = name.split(",")
        for sname in shorts:
            short = self.keymap.get(sname)
            if short is not None and short.match(signature, value):

                return True
        return False

    def tip(self, name: str):
        """
        :param name:
        :return: tooltip
        """
        shorts = name.split(",")
        for sname in shorts:
            short = self.keymap.get(sname)
            if short is not None:
                return short.tip()
        return ["NONE"], "not found"


preferences = (
    SLCT_keymap,
    SLCT_Prefs
)
