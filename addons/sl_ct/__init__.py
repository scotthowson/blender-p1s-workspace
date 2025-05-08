# -*- coding:utf-8 -*-
# ##### BEGIN GPL LICENSE BLOCK #####
#
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
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

# ----------------------------------------------------------
# Author: Stephen Leger (s-leger)
#
# ----------------------------------------------------------
bl_info = {
    'name': 'CAD Transform',
    'description': 'Cad like transform',
    'author': '<s-leger> support@blender-archipack.org',
    'license': 'GPL',
    'deps': '',
    'blender': (3, 5, 0),
    'version': (2, 0, 6),
    'location': 'View3D > Tools > Cad',
    'warning': '',
    'doc_url': 'https://3dservices.ch/cad_transform',
    'tracker_url': 'https://github.com/s-leger/blender_cad_transforms/issues',
    'link': 'https://3dservices.ch/cad_transform',
    'support': 'COMMUNITY',
    'category': '3D View'
    }


__author__ = bl_info['author']
__version__ = ".".join(map(str, bl_info['version']))


if "bpy" in locals():
    pass
else:
    # noinspection PyUnresolvedReferences
    import bpy


if bpy.app.background:

    print("---------------------------------\n")
    print("{} {} :\nnot loaded in background instance.\n".format(bl_info['name'], __version__))
    print("---------------------------------\n")

    def register():
        pass

    def unregister():
        pass

else:
    # noinspection PyUnresolvedReferences
    from bpy.utils import (
        register_class,
        unregister_class,
        register_tool,
        unregister_tool
    )
    # noinspection PyUnresolvedReferences
    from bpy.types import WindowManager
    # noinspection PyUnresolvedReferences
    from bpy.props import PointerProperty

    # Register icons before addon_preferences and tools_settings
    from .icon import Icon, icons_names
    icons = Icon(icons_names)

    from .addon_preferences import (
        preferences
    )
    from .operators import operators
    from .workspace_tools import tools
    from .keymap import Keymap
    from .tools_settings import (
        SLCT_tool_settings,
        options
    )

    def register():
        global icons

        print("\n---------------------------------\n")

        try:
            # NOTE: register icons here as unregister / register may be called on the fly by other addon
            icons.register(icons_names)

            # Register translations
            from .snapi.i18n import i18n
            i18n.register()

            register_class(SLCT_tool_settings)

            # Tools settings are not stored into Scene, so they are not affected by undo
            WindowManager.slct = PointerProperty(type=SLCT_tool_settings)

            for cls in options:
                register_class(cls)

            for cls in preferences:
                register_class(cls)

            Keymap.register_shortcuts()

            for cls in operators:
                register_class(cls)

            # Register tool shortcuts for operators from preferences
            Keymap.register_keymaps(operators, tools)

            # Reversed as last is on top
            for tool in reversed(tools):
                register_tool(tool, after={"builtin.transform"}, separator=True)

            # Init tool settings and snap types from preferences
            from .snapi.preferences import Prefs
            from .snapi.types import SnapType
            prefs = Prefs.get(bpy.context)
            SnapType.from_enumproperty(prefs.snap_elements)
            ts = bpy.context.window_manager.slct
            ts.absolute_scale = prefs.absolute_scale

            print("{} {} : ready\n".format(bl_info['name'], __version__))

        except Exception as ex:
            print("{} {} : register() error:\n{}\n".format(bl_info['name'], __version__, ex))
            pass

        print("---------------------------------\n")

    def unregister():
        global icons

        print("\n---------------------------------\n")

        try:
            for tool in tools:
                unregister_tool(tool)

            for cls in reversed(operators):
                unregister_class(cls)

            for cls in reversed(preferences):
                unregister_class(cls)

            for cls in reversed(options):
                unregister_class(cls)

            unregister_class(SLCT_tool_settings)
            del WindowManager.slct

            # Never unload, would lead to errors on re-enable.
            # ERROR (bke.icons): source/blender/blenkernel/intern/icons.cc:855 BKE_icon_get: no icon for icon ID: xxx
            # icons.unregister()

            from .snapi.i18n import i18n
            i18n.unregister()

            print("{} {} : unregister() success".format(bl_info['name'], __version__))

        except Exception as ex:
            print("{} {} : unregister() error:\n{}".format(bl_info['name'], __version__, ex))
            pass

        print("---------------------------------\n")

if __name__ == "__main__":
    register()
