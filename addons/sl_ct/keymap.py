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
from . import bl_info, __version__
from .snapi.keyboard import Keyboard
from .snapi.preferences import Prefs
from .snapi.i18n import i18n
bl_label = "%s %s" % (bl_info['name'], __version__)


# Default keymap, loaded at install time to init preferences
default_keymap = {
    # name,     key, label,         tip,    ctrl, alt, shift

    # (11) snap modes 0 - 11
    "VERT": ("V", "Vertex"),
    "EDGE": ("E", "Edge"),
    "EDGE_CENTER": ("E", "Edge Center", False, False, True),
    "FACE": ("F", "Face"),
    "FACE_CENTER": ("F", "Face Center", False, False, True),
    "GRID": ("G", "Grid"),
    "ORIGIN": ("O", "Origin"),
    "BOUNDS": ("B", "Bounding box"),
    "ISOLATED": ("I", "Isolated mesh elements"),
    "CLEAR_SNAP": ("SPACE", "Clear snap", False, False, True),
    "X_RAY": ("X", "X ray", True, False, False),

    # (9) constraints 11- 20, also define scale 1d 2d 3d and rotation axis
    "X": ("X", "X axis"),
    "Y": ("Y", "Y axis"),
    "Z": ("Z", "Z axis"),
    "YZ": ("X", "YZ plane", False, False, True),
    "XZ": ("Y", "XZ plane", False, False, True),
    "XY": ("Z", "XY plane", False, False, True),
    "SWITCH_SPACE": ("TAB", "Switch [World | Local | User]"),
    "PERPENDICULAR": ("P", "Perpendicular (Rotation)", False, False, False),
    "PARALLEL": ("P", "Parallel (Rotation)", False, False, True),

    # (12) 20+
    "PIVOT": ("C", "Set pivot"),
    "EDIT_PIVOT": ("C", "Edit Pivot", False, True, False),
    "EDIT_GRID": ("G", "Edit Grid", False, True, False),
    "LOCAL_GRID": ("G", "Local Grid", False, False, True),
    "RESET_TO_WORLD": ("W", "Reset to world", False, True, False),
    "AVERAGE": ("A", "Average"),
    "HELPER": ("H", "Create helpers"),
    "ROTATE": ("R", "Rotate helper"),
    "MOVE": ("G", "Move helper"),
    "SCALE": ("S", "Scale helper"),
    "REMOVE_HELPER": ("BACK_SPACE", "Delete", False, False, False),
    "CLEAR_HELPERS": ("BACK_SPACE", "Delete all helpers / context", False, False, True),
    "AS_MESH": ("M", "Export helpers as mesh"),

}


class Keymap:

    @classmethod
    def register_keymaps(cls, operators, workspace_tools):
        """ Register operators in workspace tool keymap
        :param operators:
        :param workspace_tools:
        :return:
        """
        # Default native tools support : select and select_box + edges ring and loops
        km = [
            # Keymap.keymap_for_operator(context, "view3d.select_box")
            (
                'view3d.select_box',
                {'type': 'B', 'value': 'PRESS'},
                {'properties': [('wait_for_input', True)]}
            ),
            (
                'view3d.select_box',
                {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG'},
                {'properties': [('wait_for_input', True)]}
            ),
            (
                'view3d.select_box',
                {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG', 'shift': 1},
                {'properties': [('mode', 'ADD'), ('wait_for_input', True)]}
            ),
            (
                'view3d.select_box',
                {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG', 'ctrl': 1},
                {'properties': [('mode', 'SUB'), ('wait_for_input', True)]}
            ),
            (
                'view3d.select_box',
                {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG', 'shift': 1, 'ctrl': 1},
                {'properties': [('mode', 'AND'), ('wait_for_input', True)]}
            ),
            # Keymap.keymap_for_operator(context, "view3d.select")
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK'},
                {'properties': [
                    ("center", False),
                    ("deselect", False),
                    ("deselect_all", True),
                    ("enumerate", False),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", False),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': 1},
                {'properties': [
                    ("center", False),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", False),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", True),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'ctrl': 1},
                {'properties': [
                    ("center", True),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", False),
                    ("extend", False),
                    ("object", True),
                    ("select_passthrough", False),
                    ("toggle", False),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'alt': 1},
                {'properties': [
                    ("center", False),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", True),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", False),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': 1, 'ctrl': 1},
                {'properties': [
                    ("center", True),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", False),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", True),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'ctrl': 1, 'alt': 1},
                {'properties': [
                    ("center", True),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", True),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", False),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': 1, 'alt': 1},
                {'properties': [
                    ("center", False),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", True),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", True),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': 1, 'ctrl': 1, 'alt': 1},
                {'properties': [
                    ("center", True),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", True),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", True),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK'},
                {'properties': [
                    ("center", False),
                    ("deselect", False),
                    ("deselect_all", True),
                    ("enumerate", False),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", False),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "view3d.select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': 1},
                {'properties': [
                    ("center", False),
                    ("deselect", False),
                    ("deselect_all", False),
                    ("enumerate", False),
                    ("extend", False),
                    ("object", False),
                    ("select_passthrough", False),
                    ("toggle", True),
                    # ("vert_without_handles", False),
                ]}
            ),
            (
                "mesh.loop_select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': 1, 'alt': 1},
                {'properties': [
                    ("toggle", True),
                ]}
            ),
            (
                "mesh.loop_select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'alt': 1},
                {'properties': []}
            ),
            (
                "mesh.edgering_select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'alt': 1, 'ctrl': 1},
                {'properties': [
                    ("ring", True)
                ]}
            ),
            (
                "mesh.edgering_select",
                {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': 1, 'alt': 1, 'ctrl': 1},
                {'properties': [
                    ("toggle", True),
                    ("ring", True)
                ]}
            )
        ]

        for op in operators:
            km.append(
                (op.bl_idname, {"type": op.default_shortcut, "value": 'PRESS'}, None)
            )

        km = tuple(km)
        for tool in workspace_tools:
            tool.bl_keymap = km

    @classmethod
    def register_shortcuts(cls):
        km = Prefs.get().keymap

        

        kb = set()
        for name, shortcut in default_keymap.items():
            short = km.get(name)
            if short is None:
                short = km.add()
            else:
                kb.add(short.key)
                continue
            # will reach this part at addon setup time
            # after that keymap is found into preferences
            slen = len(shortcut)
            short.name = name
            short.key = shortcut[0]
            short.label = i18n.translate(shortcut[1])
            short.ctrl = slen > 2 and shortcut[2]
            short.alt = slen > 3 and shortcut[3]
            short.shift = slen > 4 and shortcut[4]
            kb.add(short.key)
        Keyboard.add_types(kb)

    @classmethod
    def modifier_from_item(cls, kmi):
        kw = {}
        for (attr, default) in (
                ("any", False),
                ("shift", False),
                ("ctrl", False),
                ("alt", False),
                ("oskey", False),
                ("key_modifier", 'NONE'),
                ("direction", 'ANY')
        ):
            val = getattr(kmi, attr)
            if val != default:
                kw[attr] = val
        return kw

    @classmethod
    def properties_from_item(cls, kmi):
        kw = []
        defaults = {
            "mode": "SET",
            "wait_for_input": False,
            "xmax": 0,
            "xmin": 0,
            "ymax": 0,
            "ymin": 0
        }

        def filter_by_type(x):
            return (
                isinstance(x, str) or
                isinstance(x, bool) or
                isinstance(x, int) or
                isinstance(x, float)
            )

        for attr in dir(kmi.properties):
            val = getattr(kmi.properties, attr)
            if (
                    not attr.startswith("_") and
                    filter_by_type(val) and
                    attr not in defaults
            ):
                kw.append((attr, val))

        for attr, default in defaults.items():
            if hasattr(kmi.properties, attr):
                val = getattr(kmi.properties, attr)
                if val != default:
                    kw.append((attr, val))
        if kw:
            return {'properties': kw}
        return None

    @classmethod
    def key_from_item(cls, kmi):
        kw = {"type": kmi.type, "value": kmi.value}
        kw.update(cls.modifier_from_item(kmi))
        if kmi.repeat and (
                (kmi.map_type == 'KEYBOARD' and kmi.value in {'PRESS', 'ANY'}) or
                (kmi.map_type == 'TEXTINPUT')
        ):
            kw["repeat"] = True
        return kw

    @classmethod
    def as_keymap_def(cls, kmi) -> tuple:
        return (
            kmi.idname,
            cls.key_from_item(kmi),
            cls.properties_from_item(kmi)
        )

    @classmethod
    def dict_as_tuple(cls, d):
        return tuple((k, v) for (k, v) in sorted(d.items()))

    @classmethod
    def get_keymap(cls, context, mode: str = "", space_type: str = "VIEW_3D", keymap: str = "active"):

        wm = context.window_manager
        if keymap == "active":
            keymaps = wm.keyconfigs.active.keymaps

        elif keymap == "user":
            keymaps = wm.keyconfigs.user.keymaps

        else:
            keymaps = wm.keyconfigs.addon.keymaps

        return [
            km for km in keymaps
            if (space_type == "" or km.space_type == space_type) and (mode == "" or mode in km.name)
        ]

    @classmethod
    def keymap_for_operator(
            cls, context, operator: str = "", mode: str = "", space_type: str = "VIEW_3D", keymap: str = "active"
    ):
        keymaps = cls.get_keymap(context, mode, space_type, keymap)
        res = []
        unique = set()
        for km in keymaps:
            for op, kmi in km.keymap_items.items():
                if op == operator:
                    kdef = cls.as_keymap_def(kmi)
                    kstr = str(kdef)
                    if kstr not in unique:
                        unique.add(kstr)
                        res.append(kdef)
        return res

    @classmethod
    def pretty_print(cls, km):
        for kmi in km:
            print("(")
            print("\"%s\"," % kmi[0])
            print(kmi[1], ",")
            print("{'properties': [")
            for prop in kmi[2]['properties']:
                k, v = prop
                print("\t(\"%s\", %s)," % (k, "\"%s\"" % v if isinstance(v, str) else v))
            print("]}")
            print("),")

    @classmethod
    def tools_shortcuts(cls, context) -> dict:
        mode = " ".join([c.capitalize() for c in context.mode.split("_")])
        keymap = cls.get_keymap(context, mode, "", "user")
        return {
            op.replace("%s." % __package__, "").capitalize(): kmi
            for km in keymap
            for op, kmi in km.keymap_items.items()
            if op.startswith(__package__)
        }

    @classmethod
    def signature(
            cls, context, operator: str, mode: str = "", space_type: str = "VIEW_3D", keymap: str = "active"
    ) -> set:
        """
        :param context:
        :param operator: bl.id_name of operator
        :param mode: context.mode " ".join([c.capitalize() for c in context.mode.split("_")])
        :param space_type: in ["EMPTY", "VIEW_3D" ...]
        :param keymap: keymap type in [active | user | addon]
        :return: event signature for operator
        """
        keymap = cls.get_keymap(context, mode, space_type, keymap)
        return {
            (bool(kmi.alt), bool(kmi.ctrl), bool(kmi.shift), kmi.type, "PRESS")
            for km in keymap
            for op, kmi in km.keymap_items.items()
            if op == operator
        }
