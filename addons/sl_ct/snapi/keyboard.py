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
from .types import (
    TransformType
)
from .units import Units


class Keyboard:

    _ascii = {
        ".", ",", "-", "+", "1", "2", "3",
        "4", "5", "6", "7", "8", "9", "0",
        "c", "d", "f", "i", "k", "m", "n", "t", "u",
        " ", "/", "*", "°", "(", ")"
    }

    _type = {
        'BACK_SPACE', 'DEL',
        'LEFT_ARROW', 'RIGHT_ARROW', 'RET', 'NUMPAD_ENTER', 'ESC'
    }

    entered = ""
    _pos = 0

    valid = False
    value = 0
    copy = 0

    @classmethod
    def add_types(cls, typ):
        cls._type = cls._type.union(typ)

    @classmethod
    def has(cls, event):
        return event.ascii in cls._ascii or event.type in cls._type

    @classmethod
    def clear(cls):
        cls.entered = ""
        cls._pos = 0

    @classmethod
    def _value_type(cls, trs) -> str:
        """
        Determine value type for keyboard event
        As separated method in order to reuse this class
        :param trs: TransformAction
        :return:
        """
        if trs.has(TransformType.SCALE):
            # use absolute scale when unit is specified
            if any([c in "cdfikmntu" for c in reversed(cls.entered)]):
                trs.enable(TransformType.ABSOLUTE)

            if trs.has(TransformType.ABSOLUTE):
                return "LENGTH"

            return "NONE"

        elif trs.has(TransformType.ROTATE):
            return "ROTATION"

        # default to length
        return "LENGTH"

    @classmethod
    def exit(cls):
        cls.clear()

    @classmethod
    def confirm(cls):
        cls.exit()

    @classmethod
    def cancel(cls):
        cls.valid = False
        cls.value = 0
        cls.copy = 0
        cls.exit()

    @classmethod
    def is_numeric(cls, event):
        return event.ascii in "-+/*.,0123456789()"

    @classmethod
    def press(cls, context, event, trs):
        """
        Evaluate keyboard entry
        :param context:
        :param event:
        :param trs: TransformAction
        :return: confirm: user hit ENTER, cancel: user hit ESC, value
        """
        k = event.type
        c = event.ascii

        cls.entered = cls.entered.replace("|", "")

        # context.window.cursor_set("TEXT")
        if c in cls._ascii:
            if c == ",":
                c = "."
            cls.entered = cls.entered[:cls._pos] + c + cls.entered[cls._pos:]
            cls._pos += 1

        if cls.entered:

            if k == 'BACK_SPACE':
                cls.entered = cls.entered[:cls._pos - 1] + cls.entered[cls._pos:]
                cls._pos -= 1

            elif k == 'DEL':
                cls.entered = cls.entered[:cls._pos] + cls.entered[cls._pos + 1:]

            elif k == 'LEFT_ARROW':
                cls._pos = (cls._pos - 1) % (len(cls.entered) + 1)

            elif k == 'RIGHT_ARROW':
                cls._pos = (cls._pos + 1) % (len(cls.entered) + 1)

        if trs.has(TransformType.COPY):
            # Store number of copy
            try:
                cls.copy = int(cls.entered)

            except ValueError:
                cls.copy = 1
                pass

            _entered = cls.entered

        else:
            value_type = cls._value_type(trs)
            cls.valid, cls.value, _entered = Units.from_string(context, cls.entered, value_type)

        if cls.entered != _entered:
            cls._pos += 1
            cls.entered = _entered

        cls.entered = cls.entered[:cls._pos] + "|" + cls.entered[cls._pos:]
