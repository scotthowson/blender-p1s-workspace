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
from math import degrees
# noinspection PyUnresolvedReferences
from bpy.utils.units import (
    to_string,
    to_value
)
from .preferences import Prefs
logger = get_logger(__name__, 'ERROR')

# Round rotation to avoid precision issues
ROTATION_ROUNDING = 4


class Units:

    # Size of units in meter
    _size = {
        "KILOMETERS": 1000,
        "METERS": 1,
        "CENTIMETERS": 0.01,
        "MILLIMETERS": 0.001,
        "MICROMETERS": 0.000001,
        "ADAPTIVE": None,
        "MILES": 1609.344,
        "FEET": 0.3048,
        "INCHES": 0.0254,
        "THOU":  0.0000254
    }

    # units symbol postfix
    _units = {
        "METERS": "m",
        "CENTIMETERS": "cm",
        "MILLIMETERS": "mm",
        "MICROMETERS": "um",
        "KILOMETERS": "km",
        "ADAPTIVE": "",
        "MILES": "mi",
        "FEET": "ft",
        "INCHES": "in",
        "THOU": "thou"  # not supported
    }

    _fac = 0
    _precision = 5

    @classmethod
    def to_string(cls, context, value: float, typ: str = "LENGTH") -> str:
        """
        :param context:
        :param value:
        :param typ:
        :return:
        """
        prefs = Prefs.get(context)
        us = context.scene.unit_settings

        if typ == "ROTATION":
            _value = value

        elif typ == "AREA":
            _value = value * us.scale_length * us.scale_length

        else:
            _value = value * us.scale_length

        if prefs.use_adaptive_units:
            # to_string expect a us.scale_length multiplied unit unless it is an angle

            try:
                return to_string(
                    us.system, typ, _value, precision=cls._precision, split_unit=us.use_separate, compatible_unit=False
                )
            except ValueError as ex:
                logger.error("%s\n%s : %s" % (ex, value, typ))
                return "0"

        else:

            # use raw value
            if typ == "LENGTH" and us.system in {"METRIC", "IMPERIAL"} and us.length_unit in cls._units:
                ref_unit = cls._units[us.length_unit]

            elif typ == "AREA"  and us.system in {"METRIC", "IMPERIAL"} and us.length_unit in cls._units:
                ref_unit = "%s\u00b2" %  cls._units[us.length_unit]

            elif typ == "ROTATION":
                ref_unit = "°"
                _value = round(degrees(value), ROTATION_ROUNDING)

            else:
                ref_unit = ""

            return "%.5f %s" % (_value, ref_unit)

    @classmethod
    def from_string(cls, context, txt: str, value_type: str = "LENGTH"):
        """
        # TODO: support for divider. eg:  /3 -> divide current op value by 3
        :param context:
        :param txt:
        :param value_type:
        :return:
        """

        value = 0
        line = txt

        # move - to first position when found at last one
        if len(line) > 0:
            if line[-1] == "-":
                line = "-" + line[:-1]
            _line = line
        else:
            # use 0 on empty line
            _line = "0"

        us = context.scene.unit_settings

        # Use custom unit when set by user
        if value_type == "LENGTH" and us.system in {"METRIC", "IMPERIAL"} and us.length_unit in cls._units:
            ref_unit = cls._units[us.length_unit]
        else:
            ref_unit = ""

        try:
            value = to_value(
                us.system, value_type, _line, str_ref_unit=ref_unit
            )

        except ValueError as ex:
            logger.error("%s\n%s : %s" % (ex, value_type, _line))
            return False, value, _line

        if value_type == "LENGTH":
            try:
                value /= us.scale_length
            except ZeroDivisionError as ex:
                logger.error("%s\n%s : %s" % (ex, value_type, _line))
                return False, value, _line

        return True, value, line
        
    @classmethod
    def user_unit_size(cls, context):
        """
        By default 1 blender unit = 1 m
        divided by us.scale_length
        - 1 blender unit is 1 m / us.scale_length
        - 1 blender unit is 100 cm / us.scale_length
        :param context:
        :return: conversion factor between blender unit to user unit
        """
        us = context.scene.unit_settings
        fac = 1.0 / us.scale_length
        # Use custom unit when set by user
        if us.system in {"METRIC", "IMPERIAL"}:
             if us.length_unit in cls._size:
                 fac *= cls._size[us.length_unit]
        cls._fac = fac
        return fac

    @classmethod
    def blender_to_user(cls, context, value):
        """
        Convert blender unit to user unit
        :param context:
        :param value:
        :return:
        """
        return value * cls.user_unit_size(context)

    @classmethod
    def user_to_blender(cls, context, value):
        """
        Convert user unit to blender unit
        :param context:
        :param value:
        :return:
        """
        return value / cls.user_unit_size(context)
