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
import numpy as np
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
from mathutils import Matrix
# noinspection PyUnresolvedReferences
from gpu.shader import (
    create_from_info
)
# noinspection PyUnresolvedReferences
from gpu.matrix import (
    push_pop,
    load_matrix
)
# noinspection PyUnresolvedReferences
from gpu.types import (
    GPUOffScreen,
    GPUStageInterfaceInfo,
    GPUShaderCreateInfo,
    GPUVertFormat,
    GPUVertBuf,
    GPUIndexBuf,
    GPUBatch
)
# noinspection PyUnresolvedReferences
from gpu.state import (
    depth_mask_set,
    blend_set,
    line_width_set,
    point_size_set,
    active_framebuffer_get
)
from .types import BatchType
from .geom import View
logger = get_logger(__name__, 'ERROR')

# Display snap buffer as image on screen (bottom left)
DEBUG_SNAP_BUFFER = False


class OffscreenShader:
    """
    Offscreen shader
    """
    shader = None
    fmt = GPUVertFormat()
    fmt.attr_add(id="pos", comp_type='F32', len=3, fetch_mode='FLOAT')
    fmt.attr_add(id="primitive_id", comp_type='F32', len=1, fetch_mode='FLOAT')
    offset = 1

    @classmethod
    def create_shader(cls):
        """
        Create a shader
        :return:
        """
        if cls.shader is not None or bpy.app.background:
            return

        # OffScreen shader
        vert_out = GPUStageInterfaceInfo("primitive_interface")
        vert_out.flat('FLOAT', "primitive_id_var")

        shader_info = GPUShaderCreateInfo()
        shader_info.push_constant('MAT4', "MVP")
        shader_info.push_constant('FLOAT', 'offset')
        shader_info.vertex_in(0, 'VEC3', "pos")
        shader_info.vertex_in(1, 'FLOAT', "primitive_id")
        shader_info.vertex_out(vert_out)
        shader_info.fragment_out(0, 'VEC4', "FragColor")
        shader_info.vertex_source(
            "void main()"
            "{"
            "  primitive_id_var = primitive_id;"
            "  gl_Position = MVP * vec4(pos, 1.0);"
            "}"
        )

        if DEBUG_SNAP_BUFFER:
            alpha = "255.0;"
        else:
            alpha = "float(int(f/16581376)%256);"

        shader_info.fragment_source(
            "%s%s%s" % (
                (
                    "vec4 cast_to_4_bytes(float f)"
                    "{"
                    "    vec4 color;"
                    "    color.r = float(int(f)%256);"
                    "    color.g = float(int(f/256)%256);"
                    "    color.b = float(int(f/65536)%256);"
                ),
                "    color.a = {alpha};".format(alpha=alpha),
                (
                    "    return color / 255.0;"
                    "}"
                    "void main()"
                    "{"
                    "  FragColor = cast_to_4_bytes(offset + primitive_id_var);"
                    "}"
                )
            )
        )
        cls.shader = create_from_info(shader_info)
        del shader_info
        del vert_out

    @classmethod
    def create_ibo(cls, detectable):
        """
        Create index buffer
        :param detectable:
        :return:
        """
        _len = len(detectable.co)
        _indices = detectable.indices

        if _indices is None:
            # assume a list of separated items
            if detectable.batch_type == BatchType.POINTS:
                _indices = np.arange(_len, dtype='i')
            elif detectable.batch_type == BatchType.LINES:
                _indices = [(i, i + 1) for i in range(0, _len, 2)]
            else:
                _indices = [(i, i + 1, i + 2) for i in range(0, _len, 3)]

        ibo = GPUIndexBuf(type=detectable.batch_type.name, seq=_indices)
        size = len(_indices)

        return ibo, size

    @classmethod
    def batch(cls, detectable):
        """
        Create batch for shader
        :param detectable:
        :return:
        """
        _len = len(detectable.co)

        if detectable.ibo is None:
            # may reuse screen shader indices if available
            ibo, size = cls.create_ibo(detectable)
        else:
            ibo, size = detectable.ibo, detectable.buffer_size

        if detectable.batch_type == BatchType.POINTS:
            primitive_id = np.arange(_len, dtype='f4')
        elif detectable.batch_type == BatchType.LINES:
            primitive_id = np.repeat(np.arange(size, dtype='f4'), 2)
        else:
            primitive_id = np.repeat(np.arange(size, dtype='f4'), 3)

        logger.debug("OffscreenShader.batch size: %s, prinitive_id: %s" % (size, primitive_id))

        vbo = GPUVertBuf(len=_len, format=cls.fmt)
        vbo.attr_fill(id="pos", data=detectable.co)
        vbo.attr_fill(id="primitive_id", data=primitive_id)

        batch = GPUBatch(type=detectable.batch_type.name, buf=vbo, elem=ibo)

        # del temp array
        del primitive_id

        return batch, vbo, ibo, size

    @classmethod
    def reset(cls):
        """
        Reset start offset to 1
        :return:
        """
        cls.offset = 1

    @classmethod
    def bind(cls):
        cls.shader.bind()

    @classmethod
    def gl_enable(cls):
        depth_mask_set(False)
        blend_set('NONE')

    @classmethod
    def gl_disable(cls):
        blend_set('NONE')

    @classmethod
    def draw(cls, detectable):
        """
        Draw a detectable to offscreen buffer
        :param detectable:
        :return:
        """
        if detectable.offscreen_batch is not None:
            detectable.offset = cls.offset
            cls.offset += detectable.buffer_size
            cls.create_shader()
            cls.bind()

            # gpu.state
            line_width_set(1.0)
            point_size_set(1.0)

            cls.gl_enable()
            # Detectable are in world coord
            cls.shader.uniform_float("MVP", View.perspective_matrix @ detectable.matrix_world)
            cls.shader.uniform_float("offset", float(detectable.offset))

            with push_pop():
                # Reset matrix just in case ..
                load_matrix(Matrix.Identity(4))
                detectable.offscreen_batch.draw(cls.shader)

            cls.gl_disable()

        else:
            detectable.offset = 0
