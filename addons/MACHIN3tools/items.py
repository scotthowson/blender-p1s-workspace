import bpy
from mathutils import Vector
from . colors import red, green, blue

axis_items = [('X', 'X', ''),
              ('Y', 'Y', ''),
              ('Z', 'Z', '')]

axis_index_mapping = {'X': 0,
                      'Y': 1,
                      'Z': 2}

axis_vector_mappings = {'X': Vector((1, 0, 0)),
                        'Y': Vector((0, 1, 0)),
                        'Z': Vector((0, 0, 1))}

axis_color_mappings = {'X': red,
                       'Y': green,
                       'Z': blue}

uv_axis_items = [('U', 'U', ''),
                 ('V', 'V', '')]

ctrl = ['LEFT_CTRL', 'RIGHT_CTRL']
alt = ['LEFT_ALT', 'RIGHT_ALT']
shift = ['LEFT_SHIFT', 'RIGHT_SHIFT']

preferences_tabs = [("GENERAL", "General", ""),
                    ("KEYMAPS", "Keymaps", ""),
                    ("ABOUT", "About", "")]

matcap_background_type_items = [("THEME", "Theme", ""),
                                ("WORLD", "World", ""),
                                ("VIEWPORT", "Viewport", "")]

smartvert_mode_items = [("MERGE", "Merge", ""),
                        ("CONNECT", "Connect Paths", "")]

smartvert_merge_type_items = [("LAST", "Last", ""),
                              ("CENTER", "Center", ""),
                              ("PATHS", "Paths", "")]

smartvert_path_type_items = [("TOPO", "Topo", ""),
                             ("LENGTH", "Length", "")]

smartedge_sharp_mode_items = [('SHARPEN', 'Sharpen', ''),
                              ('CREASE', 'Crease', ''),
                              ('CHAMFER', 'Chamfer', ''),
                              ('KOREAN', 'Korean Bevel', '')]

smartedge_select_mode_items = [('BOUNDS', 'Bounds/Region', ''),
                               ('ADJACENT', 'Adjacent', '')]

focus_method_items = [('VIEW_SELECTED', 'View Selected', ''),
                      ('LOCAL_VIEW', 'Local View', '')]

focus_levels_items = [('SINGLE', 'Single', ''),
                      ('MULTIPLE', 'Multiple', '')]

align_mode_items = [('VIEW', 'View', ''),
                    ('AXES', 'Axes', '')]

align_type_items = [('MIN', 'Min', ''),
                    ('MAX', 'Max', ''),
                    ('AVERAGE', 'Average', ''),
                    ('ZERO', 'Zero', ''),
                    ('CURSOR', 'Cursor', '')]

align_direction_items = [('LEFT', 'Left', ''),
                         ('RIGHT', 'Right', ''),
                         ('TOP', 'Top', ''),
                         ('BOTTOM', 'Bottom', ''),
                         ('HORIZONTAL', 'Horizontal', ''),
                         ('VERTICAL', 'Vertical', '')]

align_space_items = [('LOCAL', 'Local', ''),
                     ('WORLD', 'World', ''),
                     ('CURSOR', 'Cursor', '')]

obj_align_mode_items = [('ORIGIN', 'Origin', ''),
                        ('CURSOR', 'Cursor', ''),
                        ('ACTIVE', 'Active', ''),
                        ('FLOOR', 'Floor', '')]

cleanup_select_items = [("NON-MANIFOLD", "Non-Manifold", ""),
                        ("NON-PLANAR", "Non-Planar", ""),
                        ("TRIS", "Tris", ""),
                        ("NGONS", "Ngons", "")]

driver_limit_items = [('NONE', 'None', ''),
                      ('START', 'Start', ''),
                      ('END', 'End', ''),
                      ('BOTH', 'Both', '')]

driver_transform_items = [('LOCATION', 'Location', ''),
                          ('ROTATION_EULER', 'Rotation', '')]

driver_space_items = [('AUTO', 'Auto', 'Choose Local or World space based on whether driver object is parented'),
                      ('LOCAL_SPACE', 'Local', ''),
                      ('WORLD_SPACE', 'World', '')]

axis_mapping_dict = {'X': 0, 'Y': 1, 'Z': 2}

uv_align_axis_mapping_dict = {'U': 0, 'V': 1}

bridge_interpolation_items = [('LINEAR', 'Linear', ''),
                              ('PATH', 'Path', ''),
                              ('SURFACE', 'Surface', '')]

view_axis_items = [("FRONT", "Front", ""),
                   ("BACK", "Back", ""),
                   ("LEFT", "Left", ""),
                   ("RIGHT", "Right", ""),
                   ("TOP", "Top", ""),
                   ("BOTTOM", "Bottom", "")]

group_location_items = [('AVERAGE', 'Average', ''),
                        ('ACTIVE', 'Active', ''),
                        ('CURSOR', 'Cursor', ''),
                        ('WORLD', 'World', '')]

extrude_mode_items = [('AVERAGED', 'Averaged', 'Extrude along Averaged Face Normals'),
                      ('EDGE', 'Edge', 'Extrude along any chosen Edge of any Object'),
                      ('NORMAL', 'Normal', 'Extrude along Individual Vertex Normals')]

cursor_spin_angle_preset_items = [('None', 'None', ''),
                                  ('30', '30', ''),
                                  ('45', '45', ''),
                                  ('60', '60', ''),
                                  ('90', '90', ''),
                                  ('135', '135', ''),
                                  ('180', '180', '')]

create_assembly_asset_empty_location_items = [('AVG', 'Average', 'Averaged Location of all Asset Root Objects'),
                                              ('AVGFLOOR', 'Avg. Floor', 'Averaged Location of all Asset Root Objects projected on the floor'),
                                              ('CURSOR', 'Cursor', 'Cursor Location'),
                                              ('ORIGIN', 'Origin', 'World Origin')]

create_assembly_asset_empty_collection_items = [('SCENECOL', 'Scene Collection', 'Add Asset empty to Scene Collection'),
                                                ('OBJCOLS', 'Object Collections', "Add Asset Empty to Asset Object's Colletion(s)")]

shade_mode_items = [('SMOOTH', 'Smooth', ''),
                    ('FLAT', 'Flat', '')]

asset_browser_bookmark_props = ['libref', 'catalog_id', 'display_size', 'display_type', 'valid']

letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
numbers = ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "ZERO"]
special = ["SPACE", "PLUS", "MINUS", "STAR", "EQUAL", "COMMA", "PERIOD", "COLON", "SEMI_COLON", "SLASH", "BACK_SLASH", "QUOTE", "DOUBLE-QUOTE", "LEFT_BRACKET", "RIGHT_BRACKET"]
control = ['BACK_SPACE', 'RET']

annotate_inputs = [*letters, *numbers, *special, *control]

numbers_map = {"ONE": 1,
               "TWO": 2,
               "THREE": 3,
               "FOUR": 4,
               "FIVE": 5,
               "SIX": 6,
               "SEVEN": 7,
               "EIGHT": 8,
               "NINE": 9,
               "ZERO": 0}

specials_map = {"SPACE": " ",

                "PLUS": "+",
                "MINUS": "-",
                "STAR": "*",
                "EQUAL": "=",

                "COMMA": ",",
                "PERIOD": ".",

                "SEMI_COLON": ";",
                "COLON": ":",

                "EXCLAMATION_MARK": "!",
                "QUESTION_MARK": "?",

                "SLASH": "/",
                "BACK_SLASH": "\\",

                "QUOTE": "'",
                "DOUBLE_QUOTE": '"',

                "LEFT_BRACKET": "[",
                "RIGHT_BRACKET": "]"}

eevee_preset_items = [('NONE', 'None', ''),
                      ('LOW', 'Low', 'Use Scene Lights, Ambient Occlusion and Screen Space Reflections'),
                      ('HIGH', 'High', 'Use Bloom and Screen Space Refractions'),
                      ('ULTRA', 'Ultra', 'Use Scene World and Volumetrics.\nCreate Principled Volume node if necessary')]

eevee_next_preset_items = [('NONE', 'None', 'Bare-bones'),
                           ('LOW', 'Low', 'Use Shadows and enable Raytracing'),
                           ('HIGH', 'High', 'Higher Quality Shadows and Raytracing, enable Bloom and Volumetric Shadows'),
                           ('ULTRA', 'Ultra', 'Even Higher Quality, expect things to be slow, especially when also using Volumetrics')]

eevee_passes_preset_items = [('COMBINED', 'Combined', ''),
                             ('SHADOW', 'Shadow', ''),
                             ('AO', 'AO', '')]

eevee_next_raytrace_resolution_items = [('1', '1:1', ''),
                                        ('2', '1:2', ''),
                                        ('4', '1:4', ''),
                                        ('8', '1:8', ''),
                                        ('16', '1:16', '')]

render_engine_items = [('BLENDER_EEVEE_NEXT' if bpy.app.version >= (4, 2, 0) else 'BLENDER_EEVEE', 'Eevee', ''),
                       ('CYCLES', 'Cycles', '')]

shading_light_items = [('STUDIO', 'Studio', ''),
                       ('MATCAP', 'Matcap', ''),
                       ('FLAT', 'Flat', '')]

cycles_device_items = [('CPU', 'CPU', ''),
                       ('GPU', 'GPU', '')]

compositor_items = [('DISABLED', 'Disabled', ''),
                    ('CAMERA', 'Camera', ''),
                    ('ALWAYS', 'Always', '')]

bc_orientation_items = [('LOCAL', 'Local', ''),
                        ('NEAREST', 'Nearest', ''),
                        ('LONGEST', 'Longest', '')]

tool_name_mapping_dict = {'BC': 'BoxCutter',
                          'Hops': 'HardOps',
                          'builtin.select_box': 'Select Box',
                          'builtin.annotate': 'Annotate',
                          'builtin.annotate_eraser': 'Erase',
                          'machin3.tool_hyper_cursor': 'Hyper Cursor',
                          'machin3.tool_hyper_cursor_simple': 'Simple Hyper Cursor'}

mirror_props = ['type',
                'merge_threshold',
                'mirror_object',
                'mirror_offset_u',
                'mirror_offset_v',
                'offset_u',
                'offset_v',
                'show_expanded',
                'show_in_editmode',
                'show_on_cage',
                'show_render',
                'show_viewport',
                'use_axis',
                'use_bisect_axis',
                'use_bisect_flip_axis',
                'use_clip',
                'use_mirror_merge',
                'use_mirror_u',
                'use_mirror_v',
                'use_mirror_vertex_groups']
