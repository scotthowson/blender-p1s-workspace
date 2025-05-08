# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2013-2024 Campbell Barton
# SPDX-FileCopyrightText: 2016-2025 Mikhail Rachinskiy


if "bpy" in locals():
    from pathlib import Path
    essentials.reload_recursive(Path(__file__).parent, locals())
else:
    import bpy
    from bpy.props import PointerProperty

    from . import essentials, localization, operators, preferences, ui


classes = essentials.get_classes((essentials, operators, preferences, ui))


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.print3d_toolbox = PointerProperty(type=preferences.SceneProperties)

    # Translations
    # ---------------------------

    bpy.app.translations.register(__package__, localization.DICTIONARY)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.print3d_toolbox

    # Translations
    # ---------------------------

    bpy.app.translations.unregister(__package__)
