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
from math import sqrt
# noinspection PyUnresolvedReferences
from mathutils import Matrix, Vector
# noinspection PyUnresolvedReferences
import bmesh
# noinspection PyUnresolvedReferences
import bpy
import time
# noinspection PyUnresolvedReferences
from gpu.types import (
    GPUOffScreen
)
# noinspection PyUnresolvedReferences
from gpu.state import (
    depth_mask_set,
    blend_set,
    line_width_set,
    point_size_set,
    active_framebuffer_get
)
from .drawable import (
    Cross,
    Curve,
    Image,
    ImageShader
)
from .offscreen import OffscreenShader, DEBUG_SNAP_BUFFER
from .types import (
    SnapType,
    BatchType,
    SnapItemType,
    SnapTargetType
)
from .geom import (
    View,
    Geom3d,
    MATRIX_WORLD,
    ZERO,
    RED
)
from .snapitem import (
    SnapItems
)
from .widgets import (
    SnapHelper,
    SnapHelpers,
    Detectable,
    DetectablePoints,
    DetectableLines
)
from .engine import (
    DetectEngine
)
logger = get_logger(__name__, 'ERROR')


# display snap buffer as blender image
DEBUG_DRAW_AS_IMAGE = False


class RasterDetectEngine(DetectEngine):
    """
    Detect engine using off screen raster for objects not reachable by rays like curves
    """

    def __init__(self, context):
        DetectEngine.__init__(self, context)
        self._buf_size = 2 * self._snap_radius + 1

        # self.depth_range = Vector((0, 1e64))

        # GPUOffScreen
        self._offscreen = None

        # Detectable
        self._virtuals = []
        # Detectable objects filter by window visibility
        self._detectables = []

        # gpu.types.Buffer
        self._snap_buf = None
        self._debug_buf = None

        # gpu.types.GPUTexture
        self._debug_tex = None

        # A cross to show coord found detectable when dist is inconsistent
        self._debug_snap = Cross(Matrix(), RED, 25, 8)

    @property
    def detectable(self) -> list:
        """
        Available detectable items, real Detectable and virtual SnapHelper ones
        :return:
        """
        # NOTE: visible first as they are removable by index
        return self._detectables + self._virtuals + SnapHelpers.helpers()

    def exclude_offscreen(self):
        # When view change, update exclude set on huge scenes to visible objects
        #   > 30k objects is 0.3sec / raycast init
        #   setup will be one time ~0.3sec on view change
        t = time.time()
        v = Vector((0, 0, 0, 1))
        self._detectables.clear()
        res = [Vector((0, 0)) for i in range(8)]
        for detectable in self._visible_objects:
            obj = detectable.obj
            if obj.name not in self._exclude:
                detectable.bound_rect.clear()
                if self._any_visible_box(obj, detectable.matrix_world, v, res, detectable.bound_rect):
                    self._detectables.append(detectable)
        logger.debug("_visible_bounds %s %.6f" % (len(self._detectables), time.time() - t))

    def exclude(self, context, selection: list = None):
        self._exclude.clear()
        if selection is not None:
            self._exclude.update({o.name for o in selection})

        self.exclude_offscreen()

    def _create_batch(self, context, detectable: Detectable):
        """
        Create Detectable.batch on demand
        :param context:
        :param detectable:
        :return:
        """
        if detectable.offscreen_batch is None:
            # TODO: support for other blender objects : nurbs, grease pencil ..
            if hasattr(detectable.obj, 'data'):
                cls = detectable.obj.type
                if cls == 'MESH':
                    self.mesh(context, detectable)
                elif cls == 'CURVE':
                    self.curve(context, detectable)
            else:
                detectable.create_batch()

    def _detectable_by_index(self, index: int):
        """
        Find detectable by index
        :param index:
        :return:
        """
        for detectable in self.detectable:
            if detectable.offset > 0:
                i = index - detectable.offset
                if 0 <= i < detectable.buffer_size:
                    return detectable
        logger.error("_detectable_by_index(index: %s) not found !" % index)
        return None

    def _detectable_by_type(self, obj, typ: int):
        """
        Find detectable by obj and batch type
        :param obj:
        :param typ:
        :return:
        """
        for detectable in self.detectable:
            if detectable.obj == obj and detectable.batch_type == typ:
                return detectable
        return None

    def _add_collection_instance_objects(self, empty, space, coll):
        _space = space @ Matrix.Translation(-coll.instance_offset)
        for o in coll.objects:
            # collection objects
            if o.type in {'CURVE', 'GPENCIL', 'NURBS'}:
                # space = empty.matrix_world
                mat = _space @ o.matrix_world
                d0 = DetectableLines(o, mat, SnapType.EDGE | SnapType.EDGE_CENTER | SnapType.VERT)
                self._visible_objects.add(d0)
            # nested collection instance
            elif o.type == 'EMPTY' and o.instance_type == 'COLLECTION':
                sub = o.instance_collection
                for c in sub.objects:
                    self._add_collection_instance_objects(c, _space @ c.matrix_world, sub)

        # nested collections
        for c in coll.children:
            self._add_collection_instance_objects(empty, _space, c)

    def init_objects(self, context, isolated: bool = True):
        """
        Init blender objects
        :param context: blender context
        :param isolated: init isolated mesh elements, optional as it may take ages on huge mesh
        :return: None
        """
        self._visible_objects.clear()
        for obj in context.visible_objects:

            if isolated and obj.type == 'MESH':
                mat = obj.matrix_world.copy()
                d0 = DetectableLines(obj, mat, SnapType.EDGE | SnapType.EDGE_CENTER | SnapType.ISOLATED)
                d1 = DetectablePoints(obj, mat, SnapType.VERT | SnapType.ISOLATED)
                self._visible_objects.add(d0)
                self._visible_objects.add(d1)

            elif obj.type in {'CURVE', 'GPENCIL', 'NURBS'}:
                mat = obj.matrix_world.copy()
                d0 = DetectableLines(obj, mat, SnapType.EDGE | SnapType.EDGE_CENTER | SnapType.VERT)
                self._visible_objects.add(d0)

            elif (
                    context.window_manager.slct.collection_instances and
                    obj.type == "EMPTY" and
                    obj.instance_type == 'COLLECTION'
            ):
                self._add_collection_instance_objects(obj, obj.matrix_world, obj.instance_collection)
                # Not supported as lazy init will only init first found objects by obj and BatchType

                # if isolated and o.type == {'MESH'}:
                #     mat = obj.matrix_world @ o.matrix_world
                #     d0 = DetectableLines(o, mat, SnapType.EDGE | SnapType.EDGE_CENTER | SnapType.ISOLATED)
                #     d1 = DetectablePoints(o, mat, SnapType.VERT | SnapType.ISOLATED)
                #     self._visible_objects.add(d0)
                #     self._visible_objects.add(d1)

    def remove_empty(self, to_remove: list):
        """
        Mesh objects lazy init may lead to empty objects when there are no "isolated" items, so
        Remove empty Detectable from stack
        :param to_remove: list index of items to remove
        :return:
        """
        logger.debug("remove_empty() to_remove %s" % to_remove)

        for i in reversed(to_remove):
            detectable = self._detectables.pop(i)
            self._visible_objects.remove(detectable)
            logger.debug("remove empty %s" % detectable.obj)

    def update(self, context):
        """ Init virtual Detectable for objects after transform
        :param context:
        :return:
        """
        self._virtuals.clear()
        self._init_bounds(context)
        self._init_origins(context)
        self._init_cursor(context)
        self._init_pivots(context)
        self._init_edit_mode_selection_center(context)

    def _add_collection_instance_bounds(self, helper, space, coll, co):
        _space = space @ Matrix.Translation(-coll.instance_offset)

        for c in coll.objects:

            # collection objects
            tm = _space @ c.matrix_world
            co.extend([tm @ Vector(p) for p in c.bound_box])
            # nested collection instance
            if c.type == 'EMPTY' and c.instance_type == 'COLLECTION':
                self._add_collection_instance_bounds(c, _space @ c.matrix_world, c.instance_collection, co)

        # nested collection
        for sub in coll.children:
            self._add_collection_instance_bounds(helper, _space, sub, co)

    def _init_bounds(self, context):
        """
        Setup object bounding box
        :param context:
        :return:
        """
        co = []
        for o in context.visible_objects:
            tm = o.matrix_world
            co.extend([tm @ Vector(p) for p in o.bound_box])

        if context.window_manager.slct.collection_instances:
            for o in context.visible_objects:
                # instance_type ‘VERTS’, ‘FACES’ -> dupli verts / dupli faces
                if o.type == 'EMPTY' and o.instance_type == 'COLLECTION':
                    self._add_collection_instance_bounds(o, o.matrix_world, o.instance_collection, co)

        self._virtuals.append(
            DetectablePoints('bounds', MATRIX_WORLD, SnapType.BOUNDS, co)
        )

    def _add_collection_instance_origins(self, helper, space, coll, co):
        _space = space @ Matrix.Translation(-coll.instance_offset)
        co.extend([
            _space @ c.matrix_world.translation
            for c in coll.objects
        ])
        for c in coll.objects:
            if c.type == 'EMPTY' and c.instance_type == 'COLLECTION':
                self._add_collection_instance_origins(c, _space @ c.matrix_world, c.instance_collection, co)
        for c in coll.children:
            self._add_collection_instance_origins(helper, _space, c, co)

    def _init_edit_mode_selection_center(self, context):
        for obj in context.visible_objects:

            # edit mesh selected vertex center
            if obj.type == "MESH" and obj.mode == "EDIT":
                bm = bmesh.from_edit_mesh(obj.data)
                coords = [v.co for v in bm.verts if v.select]
                if len(coords) > 0:

                    co = obj.matrix_world @ Vector([0.5 * (min(axis) + max(axis)) for axis in zip(*coords)])
                    self._virtuals.append(
                        DetectablePoints('center', MATRIX_WORLD, SnapType.CENTER, [co])
                    )
                bm.free()

    def _init_origins(self, context):
        """
        Setup object's origin
        :param context:
        :return:
        """
        co = [
            o.matrix_world.translation.copy()
            for o in context.visible_objects
        ]

        if context.window_manager.slct.collection_instances:
            for o in context.visible_objects:
                if o.type == 'EMPTY' and o.instance_type == 'COLLECTION':
                    self._add_collection_instance_origins(o, o.matrix_world, o.instance_collection, co)

        # co.append(context.scene.cursor.location.copy())
        self._virtuals.append(
            DetectablePoints('origins', MATRIX_WORLD, SnapType.ORIGIN, co)
        )

    def _init_cursor(self, context):
        """
        Setup cursor location
        :param context:
        :return:
        """
        self._virtuals.append(
            DetectablePoints('cursor', context.scene.cursor.matrix, SnapType.CURSOR, [ZERO])
        )

    def _init_pivots(self, context):
        sel = context.selected_objects
        size = len(sel)
        if size > 0:
            median = Vector()
            bbox = []
            for o in sel:
                median += o.matrix_world.translation
                bbox.extend([o.matrix_world @ pt for pt in [Vector(o.bound_box[0]), Vector(o.bound_box[6])]])
            median = (1.0 / size) * median
            self._virtuals.append(
                DetectablePoints('median', MATRIX_WORLD, SnapType.VIRTUAL | SnapType.ORIGIN, [median])
            )
            x, y, z = zip(*bbox)
            center = 0.5 * Vector((min(x) + max(x), min(y) + max(y), min(z) + max(z)))
            self._virtuals.append(
                DetectablePoints('center', MATRIX_WORLD, SnapType.VIRTUAL | SnapType.BOUNDS, [center])
            )

    def gpencil(self, context, detectable):
        """
        TODO: implementation
        :param context:
        :param detectable:
        :return:
        """
        obj = detectable.obj
        if obj.mode == 'EDIT_GPENCIL':
            pass
        pass

    def mesh(self, context, detectable):
        """
        Fill mesh coord data, lazy
        :param context:
        :param detectable:
        :return:
        """
        t = time.time()

        context.window.cursor_set("WAIT")

        obj = detectable.obj

        if obj.mode == "EDIT":
            bm = bmesh.from_edit_mesh(obj.data)
        else:
            bm = bmesh.new(use_operators=True)
            bm.from_mesh(obj.data)

        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        co = [v.co.copy() for v in bm.verts if not v.link_edges]

        _detectable = self._detectable_by_type(obj, BatchType.POINTS)

        if _detectable is None:
            logger.error("detectable type POINTS not found %s" % obj.name)

        elif len(co) > 0:
            _detectable.co = co
            _detectable.create_batch()
        else:
            _detectable.is_empty = True

        co = []
        for ed in bm.edges:
            if ed.is_wire:
                co.extend([ed.verts[0].co.copy(), ed.verts[1].co.copy()])

        _detectable = self._detectable_by_type(obj, BatchType.LINES)
        if _detectable is None:
            logger.error("detectable type LINES not found %s" % obj.name)

        elif len(co) > 0:
            _detectable.co = co
            _detectable.create_batch()
        else:
            _detectable.is_empty = True

        if obj.mode != "EDIT":
            bm.free()

        logger.debug("mesh isolated verts edges evaluation: %s  %.4f sec" % (obj.name, time.time() - t))

    @staticmethod
    def curve(context, detectable):
        """
        Fill curve coord data, lazy
        :param context:
        :param detectable:
        :return:
        """
        # coord in local space
        context.window.cursor_set("WAIT")

        co, indices = Curve.from_curve(detectable.obj)

        if len(co) > 0:
            edges_co = []
            for i, (v0, v1) in enumerate(indices):
                edges_co.extend([co[v0], co[v1]])
            detectable.co = edges_co
            # detectable.indices = indices
            detectable.create_batch()

    def start(self, context, event):
        """
        Start engine, init Detectable, View and GPUOffScreen
        :param context:
        :param event:
        :return:
        """
        t = time.time()
        # fill detectable array, depends on ISOLATED as it may take ages on huge mesh
        self.init_objects(context, SnapType.has(SnapType.ISOLATED))
        logger.info("init_objects %.7f" % (time.time() - t))

        # fill virtuals
        self.update(context)

        logger.info("start %.7f" % (time.time() - t))

        # Must init view before GPUOffScreen creation
        View.init(context, event)
        OffscreenShader.reset()
        self._offscreen = GPUOffScreen(*View.window, format='RGBA8')

    @staticmethod
    def delete(what):
        if what is not None:
            del what

    def __del__(self):
        self._virtuals.clear()
        self._detectables.clear()
        self.delete(self._offscreen)
        self.delete(self._snap_buf)
        self.delete(self._debug_buf)
        self.delete(self._debug_tex)

    def exit(self):
        """
        Clean up on exit
        :return:
        """
        self.__del__()
        self._offscreen = None
        self._snap_buf = None
        self._debug_buf = None
        self._debug_tex = None
        self._detectables.clear()
        self._virtuals.clear()
        self._offscreen = None
        logger.debug("RasterDetectEngine.exit()")

    def _reset(self):
        """
        Reset off screen buffer to void and re-init offset in Detectable
        :return:
        """
        OffscreenShader.reset()

        logger.info(
            "\n\n\n#####################################\n\n\n"
            "RasterDetectEngine._reset()  clear frame buffer"
            "\n\n\n#####################################\n\n\n"
        )

        for i, detectable in enumerate(self.detectable):    # + SnapHelpers.helpers()):
            if detectable.is_empty or detectable.offset == 0:
                continue
            detectable.offset = 0
            logger.debug("_reset(index: %s) %s" % (i, detectable))

        # based on View
        self.exclude_offscreen()

        fb = active_framebuffer_get()
        fb.clear(color=(0.0, 0.0, 0.0, 0.0))

    @staticmethod
    def four_bytes_as_index(pixel):
        """
        Retrieve index from pixel color + alpha byte values
        :param pixel:
        :return:
        """
        r, g, b, a = pixel
        if DEBUG_SNAP_BUFFER:
            # inhibit alpha as it is set to 1 in OffscreenShader
            a = 0
        raw = ((a * 256 + b) * 256 + g) * 256 + r
        return int(round(raw, 0))

    def _process_buffer(self, buffer):
        """
        Find if any pixel contains index data
        :param buffer:
        :return:
        """
        loc = [self._snap_radius, self._snap_radius]
        d = 1
        m = self._buf_size
        maxi = 2 * m - 1
        res = False
        found = {0}

        while m < maxi:
            # axis x, y -> y, x in buffer
            for i in range(2):
                # move x and y
                while 2 * loc[i] * d < m:
                    x, y = loc
                    # logger.debug("x: %s y: %s" % (x, y))
                    index = self.four_bytes_as_index(buffer[y][x])
                    loc[i] += d
                    if index not in found:
                        found.add(index)
                        detectable = self._detectable_by_index(index)
                        if detectable is not None:
                            # Detect all as points must snap before lines
                            if self._snap_item(detectable, index - detectable.offset):
                                logger.info("RasterDetectEngine._detectable_by_index(%s) found: %s %s %s" % (
                                    index,
                                    detectable,
                                    x, y
                                ))
                                res = True

            d = -d
            m += 4 * self._snap_radius * d + 1

        return res

    def _debug_dist(self, dist, co, detectable):

        if dist > 2 * self._snap_radius_sq:
            self._debug_snap.pos = co
            self._debug_snap.show()
            fmt = "\n\n\n########################################\n\n\n"
            fmt += "Error in buffer, dist %.4f > buffer View: %s Location: %s %s\n\n\n"
            logger.info(fmt % (
                    sqrt(dist),
                    View.pixel,
                    View.screen_location(co),
                    detectable
                )
            )
            # self._reset()
        elif dist > self._snap_radius_sq:
            self._debug_snap.pos = co
            self._debug_snap.show()
            logger.info("dist %.4f > snap_radius View: %s Location: %s %s" % (
                sqrt(dist),
                View.pixel,
                View.screen_location(co),
                detectable
            ))
        elif not DEBUG_SNAP_BUFFER:
            self._debug_snap.hide()

    def _snap_item(self, detectable, index: int = 0) -> bool:
        """
        Create SnapItem from found detectable and fill with relevant coord and type
        :param detectable:
        :param index:
        :return:
        """

        dist = 0
        if detectable.batch_type == BatchType.POINTS:
            co = detectable.get_co(index)
            dist = View.distance_pixels_from_3d_sq(co)
            self._debug_dist(dist, co, detectable)

            if dist < self._snap_radius_sq:
                return SnapItems.add(
                    co, [co], dist, SnapItemType.POINT, 0, detectable.normal,
                    target_type=SnapTargetType.POINT,
                    target=detectable.obj
                )

        elif detectable.batch_type == BatchType.LINES:

            s0, s1 = detectable.get_co(index)

            # TODO: add target type using virtual snap items classes for Circle
            #   if isinstance(detectable, SnapHelperCircle) target_type = SnapTargetType.CIRCLE
            #   must also add circle center and size (vector with x as radius) in seg_co

            p2, p3 = View.line
            fac = Geom3d.neareast_point_line_line_t(s0, s1, p2, p3)
            # Not found ..
            if fac is None:
                # View is parallel to line
                logger.info(
                    "_snap_item() : fac is NONE (view direction is parallel to line) %s %s" % (index, detectable)
                )
                return False

            if fac > 0.5:
                # always store seg_co from closest to farthest
                s0, s1 = s1, s0
                fac = 1.0 - fac

            seg_co = [s0, s1]
            # vertex, if we are close enough to ends or edge center mode is not enabled
            if SnapType.has(SnapType.VERT) and (not (0.75 > fac > 0.25) or SnapType.has_not(SnapType.EDGE_CENTER)):
                co = s0
                dist = View.distance_pixels_from_3d_sq(co)
                # NOTE: by definition dist is always under dist_px - dist is a circle / where buffer size is square
                # distance greater than 1.41 dist pix means there is something wrong in index ..
                self._debug_dist(dist, co, detectable)

                if dist < self._snap_radius_sq:

                    return SnapItems.add(
                        co, seg_co, dist, SnapItemType.POINT, 0, detectable.normal,
                        target_type=SnapTargetType.LINE,
                        target=detectable.obj
                    )

            # edge center, if we are near center or snap mode is not vertex
            if SnapType.has(SnapType.EDGE_CENTER) and ((0.75 > fac > 0.25) or SnapType.has_not(SnapType.VERT)):
                co = Geom3d.lerp(s0, s1, 0.5)
                dist = View.distance_pixels_from_3d_sq(co)
                self._debug_dist(dist, co, detectable)

                if dist < self._snap_radius_sq:
                    return SnapItems.add(
                        co, seg_co, dist, SnapItemType.LINE | SnapItemType.CENTER, 0.5, detectable.normal,
                        target_type=SnapTargetType.LINE,
                        target=detectable.obj
                    )

            # snap anywhere on edge
            if SnapType.has(SnapType.EDGE):

                if 0.0 < fac < 1.0:
                    co = Geom3d.lerp(s0, s1, fac)
                else:
                    if fac < 0.0:
                        fac = 0.0
                    co = s0

                dist = View.distance_pixels_from_3d_sq(co)
                self._debug_dist(dist, co, detectable)

                if dist < self._snap_radius_sq:
                    return SnapItems.add(
                        co, seg_co, dist, SnapItemType.LINE, fac, detectable.normal,
                        target_type=SnapTargetType.LINE,
                        target=detectable.obj
                    )

        elif detectable.batch_type == BatchType.TRIS:
            tris_co = detectable.get_co(index)

            # if SnapType.has(SnapType.FACE_CENTER):
            #   center = Geom3d.triangle_center(*tris_co)
            #   normal = Geom3d.triangle_normal(*tris_co)
            #     co, normal = detectable.matrix_world @ center, detectable.matrix_world.to_3x3() @ normal
            #     dist = View.distance_pixels_from_3d_sq(co)
            #     if dist < self._snap_radius:
            #         return SnapItems.add(co, tris_co, dist, SnapItemType.TRI | SnapItemType.CENTER, 0,
            #                                 detectable.normal,
            #                                 target_type=SnapTargetType.POLY,
            #                                 target=detectable.obj)
            if SnapType.has(SnapType.FACE):
                co = Geom3d.intersect_line_tri(*View.line, *tris_co)
                if co is not None:
                    dist = View.distance_pixels_from_3d_sq(co)
                    if dist < self._snap_radius:
                        return SnapItems.add(
                            co, tris_co, 0, SnapItemType.TRI, 0,  detectable.normal,
                            View.distance_from_origin(co),
                            0,
                            target_type=SnapTargetType.POLY,
                            target=detectable.obj
                        )

        logger.debug("_snap_item(%s) dist: %s > dist_px: %s" % (index, dist, self._snap_radius))
        return False

    @property
    def enabled(self):
        """
        Compute engine enabled state given snap modes
        :return:
        """
        return SnapType.has(
            SnapType.VERT |
            SnapType.EDGE |
            SnapType.EDGE_CENTER |
            SnapType.ORIGIN |
            SnapType.BOUNDS
            # SnapType.CURSOR |
            # SnapType.ISOLATED |
            # SnapType.VIRTUAL
        )

    def detect(self, context, event):

        t = time.time()

        with self._offscreen.bind():

            if View.dirty:
                # View is "dirty" when pers matrix does change
                # Snap mode changes also trigger dirty state
                self._reset()
                # reset dirty state
                View.dirty = False

            t1 = time.time()

            to_remove = []

            pixel_x, pixel_y = View.pixel

            # draw detectable when required
            for i, detectable in enumerate(self.detectable):

                if detectable.offset > 0 or detectable.is_empty:
                    continue

                obj = detectable.obj

                if obj in {'origins'}:
                    in_threshold = SnapType.has(SnapType.ORIGIN)

                elif obj in {'cursor'}:
                    in_threshold = SnapType.has(SnapType.CURSOR)

                elif obj in {'bounds'}:
                    in_threshold = SnapType.has(SnapType.BOUNDS)

                elif obj in {'center', 'median'}:
                    in_threshold = SnapType.has(SnapType.BOUNDS | SnapType.ORIGIN | SnapType.VIRTUAL | SnapType.CENTER)

                elif isinstance(detectable, SnapHelper):
                    # virtual ones
                    in_threshold = True

                else:
                    # check objects under ray using bound rect
                    xmin, xmax, ymin, ymax = detectable.bound_rect
                    in_threshold = xmin < pixel_x < xmax and ymin < pixel_y < ymax

                if in_threshold:
                    self._create_batch(context, detectable)  # Lazy create only at draw time
                    OffscreenShader.draw(detectable)
                    logger.info("OffscreenShader.draw(index: %s) %s" % (i, detectable))

                    if detectable.is_empty:
                        to_remove.append(i)

            if to_remove:
                self.remove_empty(to_remove)

            logger.debug("RasterDetectEngine.detect( draw ) %.4f" % (time.time() - t1))

            w = h = self._buf_size
            x = int(min(View.window[0] - w, max(0, View.pixel[0] - self._snap_radius)))
            y = int(min(View.window[1] - h, max(0, View.pixel[1] - self._snap_radius)))

            # gpu.state
            fb = active_framebuffer_get()

            # Read to snap buffer
            if self._snap_buf is None:
                # create a buffer
                self._snap_buf = fb.read_color(
                    x, y,
                    w, h,
                    4, 0, 'UBYTE'
                )
            else:
                # re use the same buffer
                fb.read_color(
                    x, y,
                    w, h,
                    4, 0, 'UBYTE', data=self._snap_buf
                )

            # Analyse buffer
            found = self._process_buffer(self._snap_buf.to_list())

            # Flag set in .offscreen
            if DEBUG_SNAP_BUFFER:
                # Update only on change
                if self._debug_tex is None:
                    pos = (0, 0)
                else:
                    pos = self._debug_tex[1]

                if self._debug_buf is None:
                    self._debug_buf = fb.read_color(
                        x, y,
                        w, h,
                        4, 0, 'FLOAT'
                    )
                else:
                    if pos != (x, y):
                        fb.read_color(
                            x, y,
                            w, h,
                            4, 0, 'FLOAT', data=self._debug_buf
                        )

                if pos != (x, y):
                    del self._debug_tex
                    pixel = 100, 100
                    size = 100, 100
                    img = Image.texture(self._debug_buf, (w, h))
                    # self._debug_tex = [img, (x, y), w, h]
                    self._debug_tex = [img, pixel, *size]

                # self.as_image(
                #     buffer,
                #     w, h,
                #     "snap_buffer"
                # )

            if DEBUG_DRAW_AS_IMAGE:
                w, h = [int(x) for x in View.window]
                self.as_image(
                    fb.read_color(0, 0, w, h, 4, 0, 'UBYTE'),
                    w,
                    h,
                    "full_screen"
                )

            logger.debug("with self._offscreen.bind() success")

        logger.info("RasterDetectEngine found: %s %.4f sec" % (SnapItems.count(), time.time() - t))
        return found

    def draw_debug(self):
        """
        Draw snap Buffer on screen
        :return:
        """
        if self._debug_tex is not None:
            logger.debug("RasterDetectEngine.debug_draw()")
            tex, pos, w, h = self._debug_tex
            ImageShader.draw(tex, pos, w, h)

        self._debug_snap.draw()

    def draw(self, context):
        """
        Offscreen buffer draw
        :param context:
        :return:
        """
        for detectable in self._detectables + self._virtuals:
            if detectable.batch_type == BatchType.POINTS and SnapType.has(detectable.mode):
                detectable.draw()

        if DEBUG_SNAP_BUFFER:
            self.draw_debug()

    @staticmethod
    def as_image(buffer, w, h, image_name):
        """
        For debug purposes, draw a buffer into a blender image
        :param buffer:
        :param w:
        :param h:
        :param image_name:
        :return:
        """
        if image_name not in bpy.data.images:
            image = bpy.data.images.new(image_name,  w, h)
        else:
            image = bpy.data.images[image_name]
            image.scale(w, h)

        buffer.dimensions = w * h * 4
        image.pixels = [v * 1000.0 for v in buffer]
        image.update()
