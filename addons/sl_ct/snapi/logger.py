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
import logging
from logging import config
from .. import __package__

# When True, set logger to individual files level
DEBUG = False


conf = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '%(asctime)-15s %(levelname)8s %(filename)s %(lineno)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'stream': 'ext://sys.stderr',
        }
    },
    'loggers': {
        __package__: {'level': 'ERROR'}
    },
    'root': {
        'level': 'WARNING',
        'handlers': ['console'],
    }
}


def get_logger(name: str = "", level: str = 'INFO'):

    if DEBUG:

        conf['loggers'].update({
            name: {'level': level}
        })
        config.dictConfig(conf)
        return logging.getLogger(name)

    else:
        config.dictConfig(conf)
        return logging.getLogger(__package__)
