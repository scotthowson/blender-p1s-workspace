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
from .logger import get_logger
# noinspection PyUnresolvedReferences
from bpy.app.translations import register, unregister, pgettext
import json
import os
from .. import __package__, bl_info
logger = get_logger(__name__, 'ERROR')


# noinspection PyPep8Naming
class i18n:

    @classmethod
    def translate(cls, label):
        return pgettext(label, __package__)

    @classmethod
    def load(cls):
        path = os.path.join(os.path.dirname(__file__), "lang", "lang.json")

        languages = {}
        try:
            with open(path, 'r') as f:
                translations = json.load(f)

            for locale, contexts in translations.items():
                languages[locale] = {}
                for ctx, translation in contexts.items():
                    for src, dst in translation.items():
                        languages[locale][(ctx, src)] = dst

        except:
            logger.error("%s: Error reading i18n translations" % bl_info['label'])
            import traceback
            traceback.print_exc()
            pass

        return languages

    @classmethod
    def register(cls):
        register(__package__, cls.load())

    @classmethod
    def unregister(cls):
        unregister(__package__)

    @classmethod
    def label(cls, where, text, icon="NONE", icon_value=0):
        where.label(text=text, icon=icon, icon_value=icon_value, text_ctxt=__package__, translate=True)

    @classmethod
    def prop(
        cls, where, d, attr,
        icon='NONE', expand=False, emboss=True, text=None, toggle=False, icon_only=False, icon_value=0, index=-1
    ):
        rna_prop = d.bl_rna.properties[attr]

        label = rna_prop.name

        if text is not None:
            label = text

        if icon_only:
            label = ""

        if rna_prop.type == 'ENUM':
            where.prop(
                d,
                attr,
                text=label,
                text_ctxt=__package__,
                translate=True,
                expand=expand,
                icon_only=icon_only
            )

        elif rna_prop.type == 'BOOLEAN':
            where.prop(
                d,
                attr,
                text=label,
                text_ctxt=__package__,
                translate=True,
                icon=icon,
                icon_value=icon_value,
                emboss=emboss,
                toggle=toggle,
                index=index
            )

        else:
            where.prop(
                d,
                attr,
                text=label,
                text_ctxt=__package__,
                translate=True,
                icon=icon,
                icon_value=icon_value,
                index=index
            )
