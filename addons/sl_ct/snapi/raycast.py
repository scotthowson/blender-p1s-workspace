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
import bpy
# noinspection PyUnresolvedReferences
import bmesh
from math import pi, sin, cos, log2, pow
import time
# noinspection PyUnresolvedReferences
from mathutils import Vector, Matrix
from .preferences import (
    USE_TRI_OVERLAY
)
from .engine import (
    DetectEngine
)
from .geom import (
    View,
    Geom3d
)
from .types import (
    SnapItemType,
    SnapType
)
from .snapitem import (
    SnapItems
)
logger = get_logger(__name__, 'ERROR')


# Experimentation to retrieve geometry nodes instances, but still does not work
# Can't iterate over depsgraph.object_instances : crash as refs are lost over time
# Would require to retrieve real source and create objects .. so user must rely on realize instances instead.
GEOMETRY_NODES = False


class RayCastDetectEngine(DetectEngine):
    """
    A raycast based detect engine for Mesh objects
    """

    def __init__(self, context):

        DetectEngine.__init__(self, context)
        # grow radius does not make sense as would try to snap past radius and then filter out by distance..
        self._max_attempts = 1
        # search samples around mouse center
        self._cast_samples = 6
        # distance from polygon for next cast
        self._cast_threshold = 0.001
        # clipping
        self._near_clip = 0
        self._far_clip = 1e32
        # start optimizing when objects are over this value
        self._max_objects = 2000

        self._is_snapping = False
        # limit to nth intersection of ray cast
        self._max_depth = 100
        self._back_faces = True
        self._skip_selected_faces = False
        self._include = []
        self._visible_names = set()
        self._visible = []
        # object: pixel xmin xmax, ymin, ymax
        self._visible_bounds = {}
        self._visible_objects = {}
        self._edit_mode_objects = {}

    def _add_collection_instance(self, empty, space, coll):
        # objects
        _space = space @ Matrix.Translation(-coll.instance_offset)
        self._visible_objects.update({
            (o, id(_space)): _space @ o.matrix_world
            for o in coll.objects if o.type == "MESH"
        })
        # nested collection instances
        for c in coll.objects:
            if c.type == "EMPTY" and c.instance_type == "COLLECTION":
                self._add_collection_instance(c, _space @ c.matrix_world, c.instance_collection)

        # nested collections
        for sub in coll.children:
            self._add_collection_instance(empty, _space, sub)

    # def _add_geometry_nodes_instances(self, context):
    #     depsgraph = context.evaluated_depsgraph_get()
    #     # for dup in depsgraph.object_instances:
    #     #     if dup.is_instance:  # Real dupli instance
    #     #         obj = dup.instance_object
    #     #         yield (obj, dup.matrix_world.copy())
    #     #     else:  # Usual object
    #     #         obj = dup.object
    #     #         yield (obj, obj.matrix_world.copy())
    #     parents = {
    #         o.evaluated_get(depsgraph)
    #         for o in context.visible_objects
    #         if any(mod.type == "NODES" for mod in o.modifiers)
    #     }

    #     for dup in depsgraph.object_instances:
    #         if dup.is_instance and dup.parent in parents:
    #             obj = dup.instance_object
    #             # Does not work as object is the modifier owner and is altered by modifier ..
    #             # so we cant get source this way.
    #             yield bpy.data.objects[obj.name], dup.matrix_world.copy()
    #
    #         else:
    #             continue

    @staticmethod
    def create_obj_from_edit(context, o, matrix_world):
        """ Edit mode objects are not visible for ray cast, create a temporary copy in OBJECT mode.
        :param context:
        :param o: object in EDIT mode
        :param matrix_world: object's matrix_world
        :return: object copy in OBJECT mode
        """
        bm = bmesh.from_edit_mesh(o.data)
        me = bpy.data.meshes.new("CAD Transform temp - %s" % o.name)
        bm.to_mesh(me)
        bm.free()
        new_o = bpy.data.objects.new("CAD Transform temp - %s" % o.name, me)
        context.scene.collection.objects.link(new_o)
        new_o.hide_set(True)
        new_o.matrix_world[:] = matrix_world
        return new_o

    def update(self, context):
        """ Update object copy from EDIT mode one
        :return:
        """
        for (name, key), o in self._edit_mode_objects.items():
            bm = bmesh.from_edit_mesh(bpy.data.objects[name].data)
            bm.to_mesh(o.data)
            bm.free()

    def start(self, context, event):
        t = time.time()
        self._visible_objects.clear()

        # if GEOMETRY_NODES:
        #     self._visible_objects.update({
        #         (o, id(matrix_world)): matrix_world for o, matrix_world in self._add_geometry_nodes_instances(context)
        #     })
        #     print(list(self._visible_objects.keys()), list(self._visible_objects.values()))

        # id() in key provide uniqueness to handle collection instances objects
        self._visible_objects.update({
            (o, id(o.matrix_world)): o.matrix_world for o in context.visible_objects if o.type == "MESH"
        })

        if context.window_manager.slct.collection_instances:
            for empty in context.visible_objects:
                if empty.type == "EMPTY" and empty.instance_type == 'COLLECTION':
                    self._add_collection_instance(empty, empty.matrix_world, empty.instance_collection)

        # Create data from mesh in edit mode not visible by obj.ray_cast() ..
        for (o, key), matrix_world in list(self._visible_objects.items()):
            if o.mode == "EDIT":
                new_o = self.create_obj_from_edit(context, o, matrix_world)
                self._edit_mode_objects[(o.name, key)] = new_o
                del self._visible_objects[(o, key)]
                self._visible_objects[(new_o, key)] = matrix_world

        # init _visible
        self.exclude(context)

        logger.info("start %.6f" % (time.time() - t))

    def exclude_offscreen(self):
        # When view change, update exclude set on huge scenes to visible objects
        #   setup will be one time ~0.3sec on view change
        self._include.clear()

        self._visible_bounds.clear()
        t = time.time()
        v = Vector((0, 0, 0, 1))
        res = [Vector((0, 0)) for i in range(8)]
        for (o, key), matrix_world in self._visible_objects.items():
            try:
                if o.name not in self._exclude:
                    box = []
                    if self._any_visible_box(o, matrix_world, v, res, box):
                        self._visible_bounds[(o, key)] = box, matrix_world
            except ReferenceError:
                pass
        logger.debug("_visible_bounds %s %.6f" % (len(self._visible_bounds), time.time() - t))

    def exit(self):
        # cleanup exclude
        self._exclude.clear()
        self._visible_bounds.clear()
        self._visible_objects.clear()
        self._skip_selected_faces = False
        for (name, o) in self._edit_mode_objects.items():
            bpy.data.objects.remove(o, do_unlink=True)
        self._edit_mode_objects.clear()
        self._visible.clear()
        self._include.clear()

    def exclude(self, context, selection: list = None):
        self._exclude.clear()
        if selection is not None:
            self._exclude.update({o.name for o in selection})

        self.exclude_offscreen()

    @staticmethod
    def _object_ray_cast(obj, matrix: Matrix, origin: Vector, direction: Vector):
        # get the ray in object's space
        matrix_inv = Geom3d.matrix_inverted(matrix)
        ray_origin = matrix_inv @ origin
        # NOTE: use 2 points to take object's scale into account
        ray_direction = (matrix_inv @ (origin + direction)) - ray_origin
        # move back from direction
        success, location, normal, face_index = obj.ray_cast(ray_origin, ray_direction)

        if success:
            # transform into world space as obj.ray_cast() return local coord
            normal = ((matrix @ normal) - matrix.translation).normalized()
            return matrix @ location, normal, face_index
        else:
            return None, None, None

    def _deep_cast(self, context, pixel, hits: dict, deep_cast: bool):
        """ Find objects below mouse
        :param context:
        :param pixel:
        :param hits:
        :param deep_cast:
        :return:
        """
        origin, direction = View.origin_and_direction(context.space_data.region_3d, pixel)
        far_clip = self._far_clip

        if deep_cast:
            max_depth = self._max_depth
        else:
            max_depth = 1

        x, y = pixel
        closest_o = None
        closest_dist = 1e32
        for (o, coll), bound_mat in self._visible_bounds.items():

            bounding_rect, matrix_world = bound_mat
            # Check if ray is in bound box pixels of object
            xmin, xmax, ymin, ymax = bounding_rect
            if xmin < x < xmax and ymin < y < ymax:

                ray_depth = 0
                dist = self._near_clip
                orig = origin + (direction * dist)
                pos = True

                while pos is not None and dist < far_clip and ray_depth < max_depth:

                    pos, normal, face_index = self._object_ray_cast(o, matrix_world, orig, direction)

                    if pos is not None:
                        dist = (origin - pos).length

                        if o not in hits:
                            hits[o] = {}

                        # we only store one hit by face index
                        if face_index not in hits[o]:
                            hits[o][face_index] = pos, normal, matrix_world, dist, ray_depth

                        # adjust threshold in single precision range to prevent numerical issues on large objects
                        axis = max(o.dimensions)
                        if axis > 0:
                            exponent = max(0, int(log2(axis)))
                            threshold = pow(2, exponent - 21)  # 4x precision limit.
                        else:
                            # fallback to default
                            threshold = self._cast_threshold

                        if dist < closest_dist:
                            closest_dist = dist
                            closest_o = o

                        orig = pos + direction * threshold

                        ray_depth += 1

        # keep only closest if we are not in deep_cast
        if not deep_cast and closest_o is not None:
            hit = hits[closest_o]
            hits.clear()
            hits[closest_o] = hit

    @staticmethod
    def _min_edge_dist(p0: Vector, p1: Vector):
        """
        :param p0: start point
        :param p1: end point
        :return: t param along segment from p0 to p1
        """
        t = Geom3d.neareast_point_ray_line_t(View.origin, View.direction, p0, p1)

        if t is None or t <= 0:
            t, p = 0.0, p0
        elif t >= 1:
            t, p = 1.0, p1
        else:
            p = Geom3d.lerp(p0, p1, t)

        d = View.distance_pixels_from_3d_sq(p)

        return t, p, d

    def _closest_mesh_vert(self, obj, me, hits):
        for face_index, hit in hits.items():
            if face_index < len(me.polygons):
                pos, normal, matrix_world, z, ray_depth = hit

                if self._skip_selected_faces and me.polygons[face_index].select:
                    continue

                # TODO: handle "visible" state
                verts = [
                    (i, matrix_world @ me.vertices[i].co)
                    for i in me.polygons[face_index].vertices
                ]

                for i, co in verts:

                    if self._skip_selected_faces and me.vertices[i].select:
                        continue

                    dist = View.distance_pixels_from_3d_sq(co)
                    if dist < self._snap_radius_sq:
                        SnapItems.add(co, [co], dist, SnapItemType.POINT,
                                      0,
                                      normal,
                                      View.distance_from_origin(co),
                                      ray_depth,
                                      target=obj
                                      )

    def _closest_subs(self, p0: Vector, p1: Vector, snap_radius: float, s0: bool, s1: bool):
        """
        :param p0:
        :param p1:
        :param snap_radius: snap_radius squared
        :param s0: skip selected
        :param s1: skip selected
        :return: bool found, float new snap radius and closest data (typ, dist, pos, res, fac, z)
        """
        t, p, d = self._min_edge_dist(p0, p1)
        found = False
        pos = p
        dist = 1e32
        typ = None
        res = None
        fac = 0.0
        z = 1e32
        radius = snap_radius

        if SnapType.has(SnapType.VERT) and not (0.75 > t > 0.25):
            pos = p0
            skip = s0
            if t > 0.5:
                pos = p1
                skip = s1
            if not skip:
                dpix = View.distance_pixels_from_3d_sq(pos)
                if dpix < radius:
                    typ = SnapItemType.POINT
                    res = [pos]
                    found = True
                    dist = dpix
                    radius = dpix
                    z = View.distance_from_origin(pos)

        if SnapType.has(SnapType.EDGE_CENTER) and (0.75 > t > 0.25):
            if not (s0 or s1):
                pos = Geom3d.lerp(p0, p1, 0.5)
                dpix = View.distance_pixels_from_3d_sq(pos)
                if dpix < radius:
                    typ = SnapItemType.LINE | SnapItemType.CENTER
                    res = [p0, p1]
                    fac = 0.5
                    found = True
                    dist = dpix
                    radius = dpix
                    z = View.distance_from_origin(pos)

        if not found and SnapType.has(SnapType.EDGE):

            if not (s0 or s1):
                if d < radius:
                    if t > 0.5:
                        fac = 1.0 - t
                        res = [p1, p0]
                    else:
                        fac = t
                        res = [p0, p1]
                    pos = p
                    typ = SnapItemType.LINE
                    found = True
                    dist = d
                    radius = d
                    z = View.distance_from_origin(pos)

        return found, radius, (typ, dist, pos, res, fac, z)

    def _closest_mesh_face(self, obj, me, hits):

        seek_radius = self._snap_radius_sq
        snap_radius = self._snap_radius_sq

        if USE_TRI_OVERLAY:
            me.calc_loop_triangles()

        for face_index, hit in hits.items():
            if face_index < len(me.polygons):

                # Find closest item start by verts, then edges / center, face center if closest
                # and fallback to face if nothing else is found in radius

                if self._skip_selected_faces and me.polygons[face_index].select:
                    # skip selected face in edit mode when snapping to normal
                    continue

                pos, normal, matrix_world, z, ray_depth = hit

                dist = 1e32

                # must store as tris
                verts = [
                    (self._skip_selected_faces and me.vertices[v].select, matrix_world @ me.vertices[v].co)
                    for v in me.polygons[face_index].vertices
                ]

                res = None
                fac = 0
                typ = SnapItemType.TRI

                if SnapType.has(SnapType.VERT | SnapType.EDGE | SnapType.EDGE_CENTER):
                    for i, (s1, p1) in enumerate(verts):
                        s0, p0 = verts[i - 1]
                        found, radius, ret = self._closest_subs(
                            p0, p1, snap_radius, s0, s1
                        )
                        if found and (radius < seek_radius):
                            seek_radius = radius
                            typ, dist, pos, res, fac, z = ret

                if SnapType.has(SnapType.FACE_CENTER):
                    p = matrix_world @ me.polygons[face_index].center
                    dpix = View.distance_pixels_from_3d_sq(p)
                    if dpix < seek_radius:
                        pos = p
                        typ = SnapItemType.TRI | SnapItemType.CENTER
                        res = [v[1] for v in verts]
                        dist = dpix
                        z = View.distance_from_origin(pos)
                        fac = 0
                        # logger.debug("found face center %s %.4f" % (typ, dist))

                if res is None and SnapType.has(SnapType.FACE):

                    # nothing else found, skip face if something was found in curve
                    # if skip_face:
                    #    continue
                    # Store gl compatible triangulated faces coord
                    if USE_TRI_OVERLAY:
                        res = [
                            matrix_world @ me.vertices[v].co
                            for tri in me.loop_triangles for v in tri.vertices if tri.polygon_index == face_index
                        ]
                    else:
                        res = [v[1] for v in verts]
                    # fake distance max so anything else will snap before
                    dist = self._snap_radius_sq

                if res is not None:
                    SnapItems.add(pos, res, dist, typ,
                                  fac,
                                  normal,
                                  z,
                                  ray_depth,
                                  target=obj
                                  )

    def _closest_mesh_edge(self, obj, me, hits):

        snap_radius = self._snap_radius_sq
        seek_radius = self._snap_radius_sq

        for face_index, hit in hits.items():
            if face_index < len(me.polygons):

                if self._skip_selected_faces and me.polygons[face_index].select:
                    continue

                # TODO: handle "visible" state
                pos, normal, matrix_world, z, ray_depth = hit
                verts = [
                    (self._skip_selected_faces and me.vertices[v].select, matrix_world @ me.vertices[v].co)
                    for v in me.polygons[face_index].vertices
                ]
                dist = 1e32
                typ = None
                fac = 0
                res = []
                for i, (s1, p1) in enumerate(verts):
                    s0, p0 = verts[i - 1]
                    found, radius, ret = self._closest_subs(
                        p0, p1, snap_radius, s0, s1
                    )
                    if found and radius < seek_radius:
                        seek_radius = radius
                        typ, dist, pos, res, fac, z = ret

                if typ is not None:
                    SnapItems.add(pos, res, dist, typ,
                                  fac,
                                  normal,
                                  z,
                                  ray_depth,
                                  target=obj
                                  )

            else:
                logger.error("_closest_mesh_edge face_index > n polys %s > %s" % (face_index, len(me.polygons)))

    def _closest_geometry(self, context, hits_dict):
        """
        Find closest geometry
        :param context:
        :param hits_dict:
        :return:
        """
        # t = time.time()
        # TODO: handle "visible" state at object's level, including "isolated" state
        depsgraph = context.evaluated_depsgraph_get()

        for o, hits in hits_dict.items():
            if o.type == "MESH":

                if len(o.modifiers) > 0:
                    me = o.evaluated_get(depsgraph).to_mesh()
                else:
                    me = o.data

                if SnapType.has(SnapType.FACE | SnapType.FACE_CENTER):
                    self._closest_mesh_face(o, me, hits)

                elif SnapType.has(SnapType.EDGE | SnapType.EDGE_CENTER):
                    self._closest_mesh_edge(o, me, hits)

                elif SnapType.has(SnapType.VERT):
                    self._closest_mesh_vert(o, me, hits)

    def _cast(self, context, hits, radius, use_center, deep_cast):
        """
        Cast a ray
        :param context:
        :param hits:
        :param radius:
        :param use_center:
        :param deep_cast:
        :return:
        """
        # t = time.time()

        if use_center:
            self._deep_cast(context, View.pixel, hits, deep_cast)

        # when hit a face in edge / face / normal / origin modes, closest is under mouse cursor
        if len(hits) == 0 or SnapType.has(SnapType.VERT | SnapType.EDGE_CENTER | SnapType.FACE_CENTER):
            cx, cy = View.pixel
            da = 2 * pi / self._cast_samples
            for i in range(self._cast_samples):
                # cast multiple rays around radius
                a = i * da
                self._deep_cast(context, (cx + radius * cos(a), cy + radius * sin(a)), hits, deep_cast)

        n_hits, max_depth, n_faces = len(hits), 0, 0
        if n_hits > 0:
            _hits = [len(hit) for hit in hits.values()]

    @property
    def enabled(self):
        return SnapType.has(
            SnapType.VERT |
            SnapType.EDGE |
            SnapType.EDGE_CENTER |
            SnapType.FACE |
            SnapType.FACE_CENTER
            )

    def detect(self, context, event):
        """
        :param context: blender's context
        :param event: blender's mouse event
        :return:
        """
        t = time.time()
        self._is_snapping = False

        if len(self._visible_objects) < 1:
            logger.info("RaycastDetectEngine skip as there are no visible mesh")
            return

        if View.dirty:
            self.exclude_offscreen()

        hits = {}

        # Snap to geometry, use ray under mouse only on first attempt
        use_center = True

        attempts = self._max_attempts
        # Progressive grow snap radius by attempts
        snap_radius_px = int(self._snap_radius / attempts)
        radius = 0

        # Deep cast for x_ray and when snapping to normal in edit mode to skip selected faces
        sort_by_ray_depth = False  # (context.mode == "EDIT_MESH" and ConstraintType.has(ConstraintType.NORMAL))
        deep_cast = context.window_manager.slct.x_ray or sort_by_ray_depth

        while attempts > 0:

            attempts -= 1
            radius += snap_radius_px

            self._cast(context, hits, radius, use_center, deep_cast)
            use_center = False

            if len(hits) > 0:
                self._closest_geometry(context, hits)

            if SnapItems.found:
                break

        logger.info("RaycastDetectEngine found: %s %.4f sec" % (SnapItems.count(), time.time() - t))
