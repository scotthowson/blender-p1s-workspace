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
import bpy
from .logger import get_logger
logger = get_logger(__name__, 'ERROR')


class context_override:
    """ Override context in object mode
    """

    @staticmethod
    def area(context, ctx, area_type):
        # take care of context switching
        # when call from outside of 3d view
        # on subsequent calls those vars are set
        try:
            if context.space_data is None or context.space_data.type != area_type:
                for window in context.window_manager.windows:
                    screen = window.screen
                    for area in screen.areas:
                        if area.type == area_type:
                            ctx['area'] = area
                            for region in area.regions:
                                if region.type == 'WINDOW':
                                    ctx['region'] = region
                            break
        except Exception:
            pass

    @staticmethod
    def id_data(context, ctx, act, sel, filter_cb):
        """ Set id data based context variables
        :param context:
        :param ctx:
        :param act:
        :param sel:
        :param filter_cb:
        :return:
        """
        act_id_data = act.id_data
        sel_id_data = [o.id_data for o in sel]
        all_id_data = context.visible_objects
        if filter_cb is not None:
            sel_id_data = list(filter(filter_cb, sel_id_data))
            all_id_data = list(filter(filter_cb, all_id_data))
        ctx['selected_objects'] = sel_id_data
        ctx['selectable_objects'] = all_id_data
        ctx['visible_objects'] = all_id_data
        ctx['objects_in_mode'] = [act_id_data]
        # parent child relationship operators
        ctx['editable_objects'] = sel_id_data
        ctx['selected_editable_objects'] = sel_id_data
        ctx['objects_in_mode_unique_data'] = [act_id_data]
        # looks like snap use editable bases.. no more exposed in context ???
        # view_layer->basact;
        # for (Base * base = view_layer->object_bases.first ...

    @staticmethod
    def set_mode(context, ctx, mode):
        if bpy.app.version[0] > 3:
            with context.temp_override(**ctx):
                bpy.ops.object.mode_set(mode=mode)
        else:
            bpy.ops.object.mode_set(ctx, mode=mode)

    def __init__(self, context, act, sel, filter_cb=None, mode="OBJECT", area_type="VIEW_3D"):
        ctx = context.copy()
        self.context = context
        # area override
        self.area(context, ctx, area_type)

        self._act = None
        self._mode = None

        ctx['object'] = act
        ctx['active_object'] = act

        if area_type == "VIEW_3D":

            if act not in sel:
                sel.append(act)

            # view_layer <bpy_struct, ViewLayer("View Layer")>
            # active_operator  <bpy_struct, Operator>
            # collection  <bpy_struct, Collection()>
            # layer_collection <bpy_struct, LayerCollection()>
            # <Struct Object()>

            # bpy.data objects
            self.id_data(context, ctx, act, sel, filter_cb)

            if mode == "EDIT" and context.mode != "EDIT":
                self._act = ctx['view_layer'].objects.active
                ctx['view_layer'].objects.active = act
                self.set_mode(context, ctx, "EDIT")
                ctx['edit_object'] = act.id_data
                ctx['mode'] = 'EDIT_MESH'
                self._mode = "OBJECT"

            elif mode == "OBJECT" and context.mode != "OBJECT":
                self.set_mode(context, ctx, "OBJECT")
                self._mode = "EDIT"

        self._ctx = ctx

    def __enter__(self):
        return self._ctx

    def __exit__(self, exc_type, exc_val, exc_tb):

        if self._mode is not None:
            self.set_mode(self.context, self._ctx, self._mode)

        if self._act is not None:
            self._ctx['view_layer'].objects.active = self._act

        return False
