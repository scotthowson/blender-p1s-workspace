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
from math import sin, cos, pi, degrees
# noinspection PyUnresolvedReferences
import bmesh
# noinspection PyUnresolvedReferences
from mathutils import Matrix, Vector
# noinspection PyUnresolvedReferences
from mathutils.geometry import interpolate_bezier
# noinspection PyUnresolvedReferences
from bpy.app import version
# noinspection PyUnresolvedReferences
import bpy
# noinspection PyUnresolvedReferences
import blf
# noinspection PyUnresolvedReferences
from gpu.shader import (
    create_from_info,
    from_builtin
)
# noinspection PyUnresolvedReferences
from gpu.types import (
    GPUOffScreen,
    GPUStageInterfaceInfo,
    GPUShaderCreateInfo,
    GPUVertFormat,
    GPUVertBuf,
    GPUIndexBuf,
    GPUBatch,
    GPUTexture,
    Buffer
)
# noinspection PyUnresolvedReferences
from gpu.matrix import (
    translate,
    scale,
    push_pop,
    load_matrix,
    load_projection_matrix
)
# noinspection PyUnresolvedReferences
from gpu.state import (
    depth_mask_set,
    blend_set,
    line_width_set,
    point_size_set,
    active_framebuffer_get
)
from .types import (
    BatchType,
    ShaderType,
    State,
    TextType,
    ConstraintType
)
from .preferences import (
    Prefs
)
from .offscreen import (
    OffscreenShader
)
from .geom import (
    Geom3d,
    View,
    Z_AXIS,
    RED,
    GREY
)
logger = get_logger(__name__, 'ERROR')

# rely on builtin shaders
USE_BUILTIN = False


class Shader:
    """
    Universal UNIFORM shader for widgets
    """
    shader = None
    # Custom type
    fmt = GPUVertFormat()
    fmt.attr_add(id="pos", comp_type='F32', len=3, fetch_mode='FLOAT')
    mvp = Matrix()

    @classmethod
    def create_shader(cls):
        if cls.shader is None:
            # :gpu.shader
            if USE_BUILTIN:
                cls.shader = from_builtin("UNIFORM_COLOR", config='DEFAULT')
            else:

                # Shader for widgets
                shader_info = GPUShaderCreateInfo()
                shader_info.push_constant('MAT4', "MVP")
                shader_info.push_constant('VEC4', 'color')
                shader_info.vertex_in(0, 'VEC3', "pos")
                shader_info.fragment_out(0, 'VEC4', "FragColor")
                shader_info.vertex_source(
                    "void main()"
                    "{"
                    "  gl_Position = MVP * vec4(pos, 1.0);"
                    "}"
                )
                shader_info.fragment_source(
                    "void main()"
                    "{"
                    "  FragColor = color;"
                    "}"
                )
                cls.shader = create_from_info(shader_info)
                del shader_info

    @classmethod
    def batch(cls, widget):
        """
        Create a batch,
        rely on our own to keep a reference of ibo and vbo for proper delete
        :param widget:
        :return:
        """
        ibo, size = OffscreenShader.create_ibo(widget)
        vbo = GPUVertBuf(len=len(widget.co), format=cls.fmt)
        vbo.attr_fill(id="pos", data=widget.co)
        batch = GPUBatch(type=widget.batch_type.name, buf=vbo, elem=ibo)
        return batch, vbo, ibo, size

    @classmethod
    def bind(cls):
        cls.shader.bind()

    # noinspection PyUnresolvedReferences
    @classmethod
    def gl_enable(cls):
        blend_set('ALPHA')

    # noinspection PyUnresolvedReferences
    @classmethod
    def gl_disable(cls):
        blend_set('NONE')

    @classmethod
    def draw(cls, drawable):

        if drawable.batch is not None:

            cls.create_shader()
            cls.bind()

            # Line and points size could be either "by widget" or preferences based
            cls.gl_enable()

            line_width_set(drawable.line_width)
            point_size_set(drawable.point_size)

            # Projection matrix for normalized 2d screen or 3d view
            if drawable.shader_type == ShaderType.UNIFORM_3D:
                # UNIFORM_3D shader
                # logger.debug("Shader.draw(UNIFORM_3D)")
                cls.mvp[:] = View.perspective_matrix @ drawable.matrix_world

            else:

                # UNIFORM_2D shader
                # location may be defined either by world coord in screen pixel
                if drawable.pixel is None:
                    pos = drawable.matrix_world.translation
                else:
                    pos = drawable.pixel[0:2]

                View.viewport_2d_projection_matrix(
                    cls.mvp,
                    pos,
                    drawable.size
                )

            cls.shader.uniform_float("color", drawable.color)

            with push_pop():
                # Reset matrix just in case ..
                load_matrix(Matrix.Identity(4))
                if USE_BUILTIN:
                    # No anti - alias in builtin ( .. but who cares ? ) so use own shader by default.
                    load_projection_matrix(cls.mvp)
                else:
                    cls.shader.uniform_float("MVP", cls.mvp)
                drawable.batch.draw(cls.shader)

            cls.gl_disable()


class Drawable:
    """
        Allow to draw objects on screen
        NOTE :
        Should rely on local matrix so we are able to
        manipulate location using that matrix and components in local space
        Ideally rely on fixed coord and matrix to set size, location and orientation.
    """

    def __init__(
            self, mat: Matrix, co: list = None, indices=None, batch_type: int = BatchType.LINES,
            shader_type: int = ShaderType.UNIFORM_3D, color: tuple = RED
    ):
        """
        :param mat:
        :param co:
        :param indices:
        :param batch_type:
        :param shader_type:
        :param color:
        """
        self.matrix_world = mat
        self.co = co
        self.indices = indices

        self.pixel = None

        # batch type
        self.batch_type = batch_type

        # Shader mode ShaderType
        self.shader_type = shader_type

        # choose colors in colors dict
        self.state = State.NORMAL

        self.colors = {
            State.NONE: GREY,
            State.NORMAL: color
        }
        prefs = Prefs.get()

        # defaults sizes
        self.line_width = prefs.line_width
        self.point_size = prefs.point_size

        # apply to 2d drawable items
        self.size = (prefs.handle_size, prefs.handle_size)

        self.enabled = True
        self.buffer_size = 0
        self.batch = None
        self.vbo = None
        self.ibo = None

    @property
    def bottom_left(self) -> Vector:
        if self.pixel is None:
            return Vector((0, 0))
        return Vector((p - 0.5 * s for p, s in zip(self.pixel, self.size)))

    @bottom_left.setter
    def bottom_left(self, pixel: Vector):
        """
        Set bottom left position on screen in pixels
        :param pixel:
        :return:
        """
        self.pixel = Vector((p + 0.5 * s for p, s in zip(pixel, self.size)))

    def theme_axis_colors(self, context, opacity: float = 1.0, state: int = ConstraintType.Z):
        """
        Use theme axis colors, and State.X, Y, Z
        :param context:
        :param opacity:
        :param state:
        :return:
        """
        theme = context.preferences.themes[0].user_interface
        self.colors = {
            ConstraintType.NONE: (1, 1, 1, opacity),
            ConstraintType.X: (*theme.axis_x, opacity),
            ConstraintType.Y: (*theme.axis_y, opacity),
            ConstraintType.Z: (*theme.axis_z, opacity)
        }
        self.state = state

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    @property
    def color(self):
        """
        :return: Color according to state
        """
        return self.colors[self.state]

    @property
    def pos(self):
        """
        :return: 3d position in world coord
        """
        return self.matrix_world.translation

    @pos.setter
    def pos(self, pos: Vector):
        """
        :param pos: 3d position in world coord
        :return:
        """
        self.matrix_world.translation[0:3] = pos[0:3]

    @property
    def valid(self):
        return self.co is not None and len(self.co) > 0

    def draw(self):
        if self.valid and self.enabled:
            # logger.debug("%s.draw()" % self.__class__.__name__)
            self._batch()
            Shader.draw(self)

    def _batch(self):
        if self.batch is None:
            try:
                self.batch, self.vbo, self.ibo, self.buffer_size = Shader.batch(self)
            except Exception as e:
                print(self.__class__.__name__, self.indices, self.batch_type, e)
                pass

    def _delete_batch(self):
        if self.vbo is not None:
            del self.vbo
        if self.ibo is not None:
            del self.ibo
        if self.batch is not None:
            del self.batch
        self.vbo = None
        self.ibo = None
        self.batch = None

    def __del__(self):
        # Detectable will delete shared ibo too
        self._delete_batch()


class Circle(Drawable):

    def __init__(
            self, mat: Matrix, color: tuple = RED, batch_type: int = BatchType.LINES, size: float = None,
            shader_type: int = ShaderType.UNIFORM_2D
    ):
        """
        :param mat: matrix world
        :param color: tuple, default color
        :param batch_type: BatchType.LINES
        :param size: for ShaderType.UNIFORM_2D, size in pixels, for ShaderType.Uniform_3D radius (default to 0.5)
        :param shader_type: ShaderType.UNIFORM_2D
        """
        if shader_type & ShaderType.UNIFORM_2D > 0 or size is None:
            radius = 0.5
        else:
            radius = size

        seg = 64
        co = [(radius * cos(i * 2 * pi / seg), radius * sin(i * 2 * pi / seg), 0) for i in range(seg)]

        if batch_type == BatchType.TRIS:
            # center
            co.append((0, 0, 0))
            indices = [(seg - 1, 0, seg)]
            indices.extend([(i, i + 1, seg) for i in range(seg - 1)])
        else:
            indices = [(seg - 1, 0)]
            indices.extend([(i, i + 1) for i in range(seg - 1)])

        Drawable.__init__(self, mat, co, indices, batch_type, shader_type, color)

        if size is not None:
            self.size = (size, size)


class Square(Drawable):
    def __init__(self, mat: Matrix, color: tuple = RED, batch_type: int = BatchType.LINES, size: int = None):
        co = [
            (-0.5, -0.5, 0), (-0.5, 0.5, 0), (0.5, 0.5, 0), (0.5, -0.5, 0)
        ]
        if batch_type == BatchType.TRIS:
            indices = [
                (0, 1, 2), (2, 3, 0)
            ]
        else:
            indices = [
                (0, 1), (1, 2), (2, 3), (3, 0)
            ]
        Drawable.__init__(self, mat, co, indices, batch_type, ShaderType.UNIFORM_2D, color)
        if size is not None:
            self.size = (size, size)


class Cross(Drawable):
    def __init__(self, mat: Matrix, color: tuple = RED, size: int = None, line_width: float = None):
        co = [
            (-0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0), (0.5, -0.5, 0)
        ]
        indices = [
            (0, 1), (2, 3)
        ]
        Drawable.__init__(self, mat, co, indices, BatchType.LINES, ShaderType.UNIFORM_2D, color)
        if size is not None:
            self.size = (size, size)
        if line_width is not None:
            self.line_width = line_width


class VerticalCross(Drawable):
    def __init__(self, mat: Matrix, color: tuple = RED, size: int = None, line_width: float = None):
        co = [
            (-0.5, 0, 0), (0.5, 0, 0), (0, -0.5, 0), (0, 0.5, 0)
        ]
        indices = [
            (0, 1), (2, 3)
        ]
        Drawable.__init__(self, mat, co, indices, BatchType.LINES, ShaderType.UNIFORM_2D, color)
        if size is not None:
            self.size = (size, size)
        if line_width is not None:
            self.line_width = line_width


class Line(Drawable):
    def __init__(self, mat: Matrix, coords: list = None, color: tuple = RED):
        co = [
            (0, 0, 0), (1, 0, 0)
        ]
        indices = [
            (0, 1)
        ]
        if coords is not None:
            matrix_world = self._compute_matrix(*coords[0:2])
        else:
            matrix_world = mat
        Drawable.__init__(self, matrix_world, co, indices, BatchType.LINES, ShaderType.UNIFORM_3D, color)

    @staticmethod
    def _compute_matrix(p0, p1):
        return Geom3d.matrix_from_up_and_direction(p0, p1 - p0, Z_AXIS)

    def from_2_points(self, p0, p1):
        """ Set new position using 2 point in world
        :param p0: world coord of 1st point
        :param p1: world coord of 2nd point
        :return:
        """
        self.matrix_world[:] = self._compute_matrix(p0, p1)


class Pie(Drawable):

    def __init__(
            self, mat: Matrix, color: tuple = RED, batch_type: int = BatchType.LINES, size: float = None,
            radius_int: float = 0.25, radius_ext: float = 0.5,
            shader_type: int = ShaderType.UNIFORM_2D,
            seg: int = 64
    ):

        self._start = 0
        self._delta = 0

        self.seg = seg
        self.radius_ext = radius_ext
        self.radius_int = radius_int

        co = self._compute_coord(0, pi / 2)

        if batch_type == BatchType.TRIS:
            if self.radius_int > 0:
                indices = [(i, i + 1, i + seg + 1) for i in range(seg - 1)]
                indices.extend([(i + seg + 1, i + seg, i) for i in range(seg - 1)])
            else:
                indices = [(i, i + 1, seg) for i in range(seg - 1)]

        else:
            indices = [(i, i + 1) for i in range(seg - 1)]
            if self.radius_int > 0:
                indices.extend([(seg + i, seg + i + 1) for i in range(seg - 1)])
            else:
                indices.extend([(seg, 0), (seg, seg - 1)])

        Drawable.__init__(self, mat, co, indices, batch_type, shader_type, color)

        if size is not None:
            self.size = (size, size)

    def _compute_coord(self, start: float, signed_delta: float) -> list:
        """
        Set angles on xy plane, where 0 is x axis and angle is counterclockwise
        :param start: angle (radians)
        :param signed_delta: angle (radians)
        :return: list of coord on xy plane
        """
        seg = self.seg
        radius_ext = self.radius_ext
        radius_int = self.radius_int
        delta = signed_delta / (seg - 1)
        logger.debug("delta : %.4f  start: %.4f" % (degrees(signed_delta), degrees(start)))
        co = [
            (radius_ext * cos(start + i * delta), radius_ext * sin(start + i * delta), 0)
            for i in range(seg)
        ]
        if radius_int > 0:
            co.extend([
                (radius_int * cos(start + i * delta), radius_int * sin(start + i * delta), 0)
                for i in range(seg)
            ])
        else:
            co.append((0, 0, 0))
        return co

    def set_angle(self, start: float, delta: float):
        """
        Set angles on xy plane, where 0 is x axis and angle is counterclockwise
        :param start: angle (radians)
        :param delta: angle (radians)
        :return:
        """
        if self._start != start or self._delta != delta:
            self.co = self._compute_coord(start, delta)
            self._delete_batch()
            self._start = start
            self._delta = delta


class Mesh(Drawable):

    def __init__(self, context, obj, color: tuple = (1, 1, 0, 0.1), batch_type: int = BatchType.TRIS):

        prefs = Prefs.get(context)

        bm = None
        indices = None

        if len(obj.data.vertices) > prefs.max_number_of_vertex and obj.mode != "EDIT":
            # Use bounding box for huge mesh to speedup startup (  ~1 sec / 250 k points)
            _batch_type = batch_type

            #    top
            # 1 --- 2
            # | \   | \
            # |  5 -| -6
            # 0 -|- 3  |  right
            #  \ |   \ |
            #    4 --- 7

            co = [Vector(p) for p in obj.bound_box]
            if batch_type == BatchType.TRIS:
                indices = [
                    (0, 1, 2), (2, 3, 0),  # Left
                    (4, 5, 6), (6, 7, 4),  # Right
                    (1, 2, 6), (6, 5, 1),  # Top
                    (0, 3, 7), (7, 4, 0),  # Bottom
                    (2, 6, 7), (7, 3, 2),  # Front
                    (0, 1, 5), (4, 4, 0)   # Back
                ]
            elif batch_type == BatchType.LINES:
                indices = [
                    (0, 1), (2, 3), (1, 2), (3, 0),
                    (4, 5), (6, 7), (5, 6), (7, 4),
                    (0, 4), (1, 5), (2, 6), (3, 7)
                ]

        else:

            if obj.mode == "EDIT":
                bm = bmesh.from_edit_mesh(obj.data)
            else:

                if len(obj.modifiers) > 0:
                    depsgraph = context.evaluated_depsgraph_get()
                    me = obj.evaluated_get(depsgraph).to_mesh()
                else:
                    me = obj.data

                bm = bmesh.new(use_operators=True)
                bm.from_mesh(me)

            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            indices = None

            if obj.mode == "EDIT":

                _batch_type = batch_type
                co = [v.co.copy() for v in bm.verts if v.select]

                if batch_type != BatchType.POINTS:
                    # vertex index map
                    index_map = {}
                    i = 0
                    for v in bm.verts:
                        if v.select:
                            index_map[v.index] = i
                            i += 1

                    if batch_type == BatchType.TRIS:
                        loops = bm.calc_loop_triangles()
                        indices = [
                             tuple(index_map[loop.vert.index] for loop in tri) for tri in loops
                             if all(loop.face.select for loop in tri)
                        ]

                    elif batch_type == BatchType.LINES:
                        indices = [tuple(index_map[v.index] for v in ed.verts) for ed in bm.edges if ed.select]

            else:
                _batch_type = batch_type
                co = [v.co.copy() for v in bm.verts]

                if batch_type == BatchType.TRIS:
                    loops = bm.calc_loop_triangles()
                    indices = [tuple(loop.vert.index for loop in tri) for tri in loops]

                elif batch_type == BatchType.LINES:
                    indices = [tuple(v.index for v in ed.verts) for ed in bm.edges]

        # logger.debug("%s %s" % (batch_type.name, indices))
        Drawable.__init__(self, obj.matrix_world.copy(), co, indices, _batch_type, ShaderType.UNIFORM_3D, color)

        if bm is not None and obj.mode != "EDIT":
            bm.free()


class Curve(Drawable):

    @classmethod
    def _interp_bezier(cls, p0, p1, segs: list, resolution: int):
        """
        Interpolate bezier segment
        :param p0: curve.bezier_point
        :param p1: curve.bezier_point
        :param segs: list of segments to fill
        :param resolution: number of sub divisions
        :return:
        """

        if (resolution == 0 or
                (p0.handle_right_type == 'VECTOR' and
                 p1.handle_left_type == 'VECTOR')):
            segs.append(p0.co[0:3])

        else:
            seg = interpolate_bezier(p0.co,
                                     p0.handle_right,
                                     p1.handle_left,
                                     p1.co,
                                     resolution + 1)
            segs.extend([p[0:3] for p in seg[:-2]])

    @classmethod
    def curve_size(cls, obj):
        curve = obj.data
        size = 0
        for i, spl in enumerate(curve.splines):
            # limited support for nurbs
            if spl.type in {'POLY', 'NURBS'}:
                size += len(spl.points)
            elif spl.type == 'BEZIER':
                size += len(spl.bezier_points)
        return size

    @classmethod
    def from_curve(cls, obj):
        indices = []
        co = []
        k0 = 0
        curve = obj.data
        for i, spl in enumerate(curve.splines):
            # limited support for nurbs
            if spl.type in {'POLY', 'NURBS'}:
                if len(spl.points) < 2:
                    continue
                co.extend([p.co[0:3] for p in spl.points])
            elif spl.type == 'BEZIER':
                pts = spl.bezier_points
                # limit resolution on huge curves
                if len(pts) < 2:
                    continue
                elif len(pts) > 500:
                    resolution = 0
                else:
                    resolution = curve.resolution_u
                for j, p1 in enumerate(pts[1:]):
                    cls._interp_bezier(pts[j], p1, co, resolution)
                if spl.use_cyclic_u:
                    cls._interp_bezier(pts[-1], pts[0], co, resolution)
                else:
                    co.append(pts[-1].co[0:3])
            else:
                # fix issue #9 Nurbs curve crash blender
                continue
            # last index
            k1 = len(co)
            indices.extend([(j, j + 1) for j in range(k0, k1 - 1)])
            if spl.use_cyclic_u:
                indices.append((k1 - 1, k0))
            # first index
            k0 = k1
        return co, indices

    @staticmethod
    def from_edit_curve(obj):
        co = []
        curve = obj.data
        for i, spl in enumerate(curve.splines):
            # limited support for nurbs
            if spl.type in {'POLY', 'NURBS'}:
                if len(spl.points) < 2:
                    continue
                co.extend([p.co[0:3] for p in spl.points if p.select])
            elif spl.type == 'BEZIER':
                # pts = spl.bezier_points
                # limit resolution on huge curves
                co.extend([p.co[0:3] for p in spl.bezier_points if p.select_control_point])
            else:
                continue

        return co

    def __init__(self, context, obj, color: tuple = (1, 1, 0, 0.1)):

        prefs = Prefs.get(context)
        indices = None

        if obj.mode == "EDIT":
            co = self.from_edit_curve(obj)
            batch_type = BatchType.POINTS

        elif self.curve_size(obj) > prefs.max_number_of_vertex:
            # Use bounding box for huge mesh to speedup startup (  ~1 sec / 250 k points)

            #    top
            # 1 --- 2
            # | \   | \
            # |  5 -| -6
            # 0 -|- 3  |  right
            #  \ |   \ |
            #    4 --- 7

            co = [Vector(p) for p in obj.bound_box]
            batch_type = BatchType.LINES
            indices = [
                (0, 1), (2, 3), (1, 2), (3, 0),
                (4, 5), (6, 7), (5, 6), (7, 4),
                (0, 4), (1, 5), (2, 6), (3, 7)
            ]

        else:
            co, indices = self.from_curve(obj)
            batch_type = BatchType.LINES

        Drawable.__init__(self, obj.matrix_world.copy(), co, indices, batch_type, ShaderType.UNIFORM_3D, color)


class Text:

    def __init__(self, context, text: str = None, typ: int = TextType.LEFT | TextType.TEXT_2D, color=None):
        prefs = Prefs.get(context)

        if color is None:
            self.color = prefs.color_text
        else:
            self.color = color

        self.font_size = prefs.font_size
        self.type = typ
        self.text = text
        self.enabled = True

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    def _size(self, font_id, dpi):
        # Signature change on blender 4.x
        if version[0] > 3:
            blf.size(font_id, self.font_size)
        else:
            blf.size(font_id, self.font_size, dpi)

    def draw(self, context, pos: Vector, txt: str = ""):
        """
        :param context:
        :param pos: location in 2d or 3d depending on text type, for 2d may be negative
        :param txt: optional, replace text on the fly
        :return:
        NOTE:
            2d location is from BOTTOM left
            Text in 3d will not draw when off screen
            Text in 2d are assumed to be on screen
        """
        if not self.enabled:
            return

        if self.text is None:
            _txt = txt
        else:
            _txt = self.text

        if _txt is None or _txt == "":
            return

        if self.type & TextType.TEXT_3D:

            if View.is_not_on_screen(pos):
                return
            x, y = View.screen_location(pos)

        else:
            x, y = pos[0:2]
            # Allow negative values from top / right
            if x < 0:
                x += View.window[0]
            if y < 0:
                y += View.window[1]

        dpi, font_id = context.preferences.system.dpi, 0
        self._size(font_id, dpi)

        if not (self.type & TextType.LEFT):
            text_size = blf.dimensions(font_id, _txt)
            if self.type & TextType.CENTER:
                x -= 0.5 * text_size[0]
            elif self.type & TextType.LEFT:
                x -= text_size[0]
            if self.type & TextType.MIDDLE:
                y -= text_size[1]

        blf.color(0, *self.color)
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, _txt)

    def size(self, context, txt):
        if self.text is None:
            _txt = txt
        else:
            _txt = self.text

        dpi, font_id = context.preferences.system.dpi, 0
        self._size(font_id, dpi)
        return blf.dimensions(font_id, _txt)


class ImageShader:
    """
    A shader for images
    """
    _shader = None
    _batch = None

    fmt = GPUVertFormat()
    fmt.attr_add(id="pos", comp_type='F32', len=2, fetch_mode='FLOAT')
    fmt.attr_add(id="texCoord", comp_type='F32', len=2, fetch_mode='FLOAT')

    @classmethod
    def create_shader(cls):
        if cls._shader is None:
            # :gpu.shader
            cls._shader = from_builtin("IMAGE")

    @classmethod
    def batch(cls):
        """
        Create a batch,
        :return:
        """
        if cls._batch is None:
            coords = ((0, 0), (1, 0), (1, 1), (0, 1))
            vbo = GPUVertBuf(len=4, format=cls.fmt)
            vbo.attr_fill(id="pos", data=coords)
            vbo.attr_fill(id="texCoord", data=coords)
            cls._batch = GPUBatch(type="TRI_FAN", buf=vbo)

    @classmethod
    def bind(cls):
        cls._shader.bind()

    @classmethod
    def gl_enable(cls):
        blend_set('ALPHA')

    @classmethod
    def gl_disable(cls):
        blend_set('NONE')

    @classmethod
    def draw(cls, texture: GPUTexture, position: Vector, width: int, height: int):
        """
        :param texture:
        :param position: bottom left location in pixels
        :param width: desired width of image in pixels
        :param height: desired height of image in pixels
        :return:
        """

        cls.create_shader()
        cls.batch()
        cls.bind()
        cls.gl_enable()

        # rely on builtin transforms
        with push_pop():
            translate(position)
            scale((width, height))
            cls._shader.uniform_sampler("image", texture)
            cls._batch.draw(cls._shader)

        cls.gl_disable()


class Image:

    """
    Handle Images in own .dat file format or from bpy.data.images
    Unless we do have access to other
    from sl_ct.snapi.drawable import Image

    filename = "/home/xxx/CAD_Transform_2/test.dat"
    display_size = (32, 32)

    img = Image(filename, display_size)
    img.center = Vector((100, 100))

    # draw handler
    img.draw()

    # dump blender image in Buffer compatible file format .dat
    Image.save(filename, bpy.data.images[image_name])

    # Convert images to .dat file
    Image.convert(source, dest)
    """
    def __init__(self, filename, display_size: Vector = None):
        # source image size
        self._size = Vector((0, 0))
        # GPUTexture
        self._texture = None
        # Buffer
        self._buf = None
        # bottom left
        self._bottom_left = Vector((0, 0))
        self.load(filename)

        if display_size is None:
            self._display_size = self._size
        else:
            self._display_size = Vector(display_size[0:2])

        self.enabled = True

    def show(self):
        self.enabled = True

    def hide(self):
        self.enabled = False

    @property
    def center(self):
        return self._bottom_left + 0.5 * self._display_size

    @center.setter
    def center(self, pixel: Vector):
        """
        Set center position on screen in pixels
        :param pixel:
        :return:
        """
        self._bottom_left[:] = pixel - 0.5 * self._display_size

    @property
    def bottom_left(self):
        return self._bottom_left

    @bottom_left.setter
    def bottom_left(self, pixel: Vector):
        """
        Set bottom left position on screen in pixels
        :param pixel:
        :return:
        """
        self._bottom_left[:] = pixel

    def draw(self):
        if self.enabled:
            ImageShader.draw(self._texture, self._bottom_left, *self._display_size)

    @staticmethod
    def texture(buf: Buffer, size: tuple, fmt: str = 'RGBA8') -> GPUTexture:
        """
        gpu.types.GPUTexture(size, layers=0, is_cubemap=False, format='RGBA8', data=None)
        This object gives access to off GPU textures.
        :param fmt: (str) – Internal data format inside GPU memory. Possible values are:
            RGBA8UI, RGBA8I, RGBA8, RGBA32UI, RGBA32I, RGBA32F, RGBA16UI, RGBA16I, RGBA16F, RGBA16,
            RG8UI, RG8I, RG8, RG32UI, RG32I, RG32F, RG16UI, RG16I, RG16F, RG16, R8UI, R8I, R8, R32UI,
            R32I, R32F, R16UI, R16I, R16F, R16, R11F_G11F_B10F, DEPTH32F_STENCIL8, DEPTH24_STENCIL8,
            SRGB8_A8, RGB16F, SRGB8_A8_DXT1, SRGB8_A8_DXT3, SRGB8_A8_DXT5, RGBA8_DXT1,
            RGBA8_DXT3, RGBA8_DXT5, DEPTH_COMPONENT32F, DEPTH_COMPONENT24, DEPTH_COMPONENT16,
        :param buf: gpu.types.Buffer
        :param size: (tuple or int) – Dimensions of the texture 1D, 2D, 3D or cubemap.
        :return: gpu.types.GPUTexture
        """
        return GPUTexture(size, layers=0, is_cubemap=False, format=fmt, data=buf)

    def load(self, filename: str):
        """Load a Buffer compatible dump of pixels (see save)
        :param filename: either bpy.data.images name or file name
        :return:
        """
        if filename in bpy.data.images:
            image = bpy.data.images[filename]
            w, h = image.size
            if w == 0 or h == 0:
                raise ValueError("Image must be saved !")
            res = {'pixels': image.pixels[:]}

        else:
            import json
            import gzip
            with gzip.open(filename, 'rt') as f:
                res = json.load(f)
            w = res['w']
            h = res['h']

        self._size[:] = (w, h)
        self._buf = Buffer('FLOAT', w * h * 4, res['pixels'])
        self._texture = self.texture(self._buf, (w, h))

    @classmethod
    def convert(cls, source: str, dest: str):
        """Dump image file pixels as Buffer compatible format
        :param source: source
        :param dest: destination file name
        :return:
        """
        image = bpy.data.images.load(source, check_existing=False)
        cls.save(dest, image)
        bpy.data.images.remove(image)

    @classmethod
    def save(cls, filename: str, image):
        """Dump blender image object pixels as Buffer compatible format
        :param filename:
        :param image: Blender image data block
        :return:
        """
        import json
        import gzip
        w, h = image.size[:]
        data = {'w': w, 'h': h, 'pixels': image.pixels[:]}
        with gzip.open(filename, 'wt') as f:
            json.dump(data, f)

    def __del__(self):
        del self._texture
        del self._buf
