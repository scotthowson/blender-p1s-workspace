import bpy
from . import c_utils as CTU
from . import pme
from .addon import uprefs
from .bl_utils import ctx_dict


def redraw_screen(area=None):
    view = uprefs().view
    s = view.ui_scale
    view.ui_scale = 0.5
    view.ui_scale = s


def toggle_header(_=None, area=None):
    if area is None:
        return

    area.spaces.active.show_region_header = \
        not area.spaces.active.show_region_header


def move_header(area=None, top=None, visible=None, auto=None):
    if top is None and visible is None and auto is None:
        return True

    if auto is not None and top is None:
        return True

    C = bpy.context
    area = area or C.area
    if not area:
        return True

    rh, rw = None, None
    for r in area.regions:
        if r.type == 'HEADER':
            rh = r
        elif r.type == 'WINDOW':
            rw = r

    is_visible = rh.height > 1
    is_top = rh.y > area.y

    d = ctx_dict(area=area, region=rh)
    if auto:
        if top:
            if is_top:
                toggle_header(d, area)
            else:
                with C.temp_override(**d):
                    bpy.ops.screen.region_flip()

                not is_visible and toggle_header(d, area)
        else:
            if is_top:
                with C.temp_override(**d):
                    bpy.ops.screen.region_flip()

                not is_visible and toggle_header(d, area)
            else:
                toggle_header(d, area)
    else:
        if top is not None and top != is_top:
            with C.temp_override(**d):
                bpy.ops.screen.region_flip()

        if visible is not None and visible != is_visible:
            toggle_header(d, area)

    return True


def find_area(area_type, screen=None):
    screen = screen or bpy.context.screen
    if isinstance(screen, str):
        screen = bpy.data.screens.get(screen, None)

    if screen:
        for a in screen.areas:
            if a.type == area_type:
                return a

    return None


def find_region(area, region_type):
    for r in area.regions:
        if r.type == region_type:
            return r

    return None


def focus_area(area, center=False, cmd=None):
    if isinstance(area, str):
        area = find_area(area)

    if not area:
        return

    event = pme.context.event
    move_flag = False
    if not event:
        center = True

    if center:
        x = area.x + area.width // 2
        y = area.y + area.height // 2
        move_flag = True
    else:
        x, y = event.mouse_x, event.mouse_y
        x = max(x, area.x)
        x = min(x, area.x + area.width - 1)
        y = max(y, area.y)
        y = min(y, area.y + area.height - 1)
        if x != event.mouse_x or y != event.mouse_y:
            move_flag = True

    if move_flag:
        bpy.context.window.cursor_warp(x, y)

    if cmd:
        with override_context(area, enter=False):
            bpy.ops.pme.timeout(cmd=cmd)


def override_context(
        area, screen=None, window=None, region='WINDOW', enter=True, **kwargs):
    window = window or bpy.context.window
    screen = screen or bpy.context.screen
    region = region or bpy.context.region

    if isinstance(screen, str):
        screen = bpy.data.screens.get(screen, bpy.context.screen)

    if not screen:
        oc = bpy.context.temp_override()
        enter and oc.__enter__()
        return oc

    if isinstance(area, str):
        for a in screen.areas:
            if a.type == area:
                area = a
                break
        else:
            oc = bpy.context.temp_override()
            enter and oc.__enter__()
            return oc

    if isinstance(region, str):
        for r in area.regions:
            if r.type == region:
                region = r
                break
        else:
            region = area.regions[0]

    oc = bpy.context.temp_override(
        region=region,
        area=area,
        screen=screen,
        window=window,
        blend_data=bpy.context.blend_data,
        **kwargs
    )
    enter and oc.__enter__()
    return oc


def toggle_sidebar(area=None, tools=True, value=None):
    area = area or bpy.context.area
    if isinstance(area, str):
        area = find_area(area)

    s = area.spaces.active
    if tools and hasattr(s, "show_region_toolbar"):
        if value is None:
            value = not s.show_region_toolbar

        s.show_region_toolbar = value

    elif not tools and hasattr(s, "show_region_ui"):
        if value is None:
            value = not s.show_region_ui

        s.show_region_ui = value

    return True


def register():
    pme.context.add_global("focus_area", focus_area)
    pme.context.add_global("move_header", move_header)
    pme.context.add_global("toggle_sidebar", toggle_sidebar)
    pme.context.add_global("override_context", override_context)
    pme.context.add_global("redraw_screen", redraw_screen)
