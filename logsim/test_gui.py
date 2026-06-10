"""Test GUI canvas helpers without opening a wxPython window."""

import importlib
import math
import sys
import types
from types import SimpleNamespace


def install_gui_dependency_stubs():
    """Install tiny wx/OpenGL stubs for headless GUI helper tests."""
    wx_module = types.ModuleType("wx")
    wxcanvas_module = types.ModuleType("wx.glcanvas")
    opengl_module = types.ModuleType("OpenGL")
    gl_module = types.ModuleType("OpenGL.GL")
    glu_module = types.ModuleType("OpenGL.GLU")
    glut_module = types.ModuleType("OpenGL.GLUT")

    class DummyWidget:
        """Object that accepts any GUI construction call."""

        def __init__(self, *args, **kwargs):
            """Ignore GUI constructor arguments."""

    wx_module.Frame = DummyWidget
    wx_module.Panel = DummyWidget
    wx_module.Timer = DummyWidget
    wx_module.BoxSizer = DummyWidget
    wx_module.StaticBox = DummyWidget
    wx_module.StaticBoxSizer = DummyWidget
    wx_module.Button = DummyWidget
    wx_module.ToggleButton = DummyWidget
    wx_module.StaticText = DummyWidget
    wx_module.SpinCtrl = DummyWidget
    wx_module.Slider = DummyWidget
    wx_module.Choice = DummyWidget
    wx_module.RadioBox = DummyWidget
    wx_module.ListBox = DummyWidget
    wx_module.TextCtrl = DummyWidget
    wx_module.MenuBar = DummyWidget
    wx_module.Menu = DummyWidget
    wx_module.FileDialog = DummyWidget
    wx_module.MessageDialog = DummyWidget
    wx_module.Colour = lambda *args: args
    wx_module.GetKeyState = lambda *args: False
    wx_module.WXK_SHIFT = 0

    wxcanvas_module.GLCanvas = DummyWidget
    wxcanvas_module.GLContext = DummyWidget
    wxcanvas_module.WX_GL_RGBA = 1
    wxcanvas_module.WX_GL_DOUBLEBUFFER = 2
    wxcanvas_module.WX_GL_DEPTH_SIZE = 3

    glut_module.GLUT_BITMAP_HELVETICA_12 = object()
    glut_module.glutInit = lambda *args, **kwargs: None
    glut_module.glutBitmapCharacter = lambda *args, **kwargs: None
    glu_module.gluPerspective = lambda *args, **kwargs: None

    def missing_gl_attribute(_name):
        """Return a no-op function for any OpenGL symbol."""
        return lambda *args, **kwargs: None

    gl_module.__getattr__ = missing_gl_attribute
    opengl_module.GL = gl_module
    opengl_module.GLU = glu_module
    opengl_module.GLUT = glut_module

    sys.modules.setdefault("wx", wx_module)
    sys.modules.setdefault("wx.glcanvas", wxcanvas_module)
    sys.modules.setdefault("OpenGL", opengl_module)
    sys.modules.setdefault("OpenGL.GL", gl_module)
    sys.modules.setdefault("OpenGL.GLU", glu_module)
    sys.modules.setdefault("OpenGL.GLUT", glut_module)


try:
    gui = importlib.import_module("gui")
except ModuleNotFoundError as error:
    if error.name not in {"wx", "OpenGL"}:
        raise
    install_gui_dependency_stubs()
    sys.modules.pop("gui", None)
    gui = importlib.import_module("gui")

MyGLCanvas = gui.MyGLCanvas


class FakeNames:
    """Minimal name lookup object for canvas layout tests."""

    def __init__(self, names):
        """Store display names by device or port ID."""
        self.names = names

    def get_name_string(self, name_id):
        """Return the display string for an ID."""
        return self.names.get(name_id, str(name_id))


class FakeDevices:
    """Small device collection exposing the canvas-facing API."""

    LOW = 0
    HIGH = 1
    RISING = 2
    FALLING = 3
    BLANK = 4
    CLOCK = "CLOCK"
    QBAR_ID = "QBAR"

    def __init__(self, device_list, names=None):
        """Store fake devices and display names."""
        self.devices_list = device_list
        self._devices = {
            device.device_id: device for device in self.devices_list
        }
        self.names = FakeNames(names or {})

    def get_signal_name(self, device_id, output_id):
        """Return a signal name in the same form as the real device API."""
        device_name = self.names.get_name_string(device_id)
        if output_id is None:
            return device_name
        return device_name + "." + self.names.get_name_string(output_id)

    def get_device(self, device_id):
        """Return a fake device by ID."""
        return self._devices.get(device_id)


def fake_device(device_id, device_kind="GATE", inputs=None):
    """Create a minimal fake device object."""
    return SimpleNamespace(
        device_id=device_id,
        device_kind=device_kind,
        inputs=inputs or {},
        outputs={None: FakeDevices.LOW},
    )


def make_canvas(devices):
    """Create a MyGLCanvas instance without running wx initialisation."""
    canvas = MyGLCanvas.__new__(MyGLCanvas)
    canvas.devices = devices
    canvas.zoom = 1.0
    canvas.pan_x = 0
    canvas.pan_y = 0
    canvas.hover_3d_name = None
    canvas.default_cycle_width = 28
    canvas.cycle_width = canvas.default_cycle_width
    canvas.row_height = 34
    canvas.min_row_band = 11
    canvas.high_offset = 18
    canvas.low_offset = 4
    canvas.circuit_pin_spacing = 12
    canvas.circuit_margin_x = 36
    canvas.circuit_margin_top = 46
    canvas.circuit_margin_bottom = 24
    canvas.scope_first_cycle = 0
    canvas.scope_first_row = 0
    canvas.scope_row_zoom = 1.0
    canvas.scope_geometry = {}
    canvas.trace_display_3d = False
    canvas.trace_3d_rotate_x = 28.0
    canvas.trace_3d_rotate_y = -34.0
    canvas.trace_3d_pan_x = 0.0
    canvas.trace_3d_pan_y = -4.0
    canvas.trace_3d_zoom = 1.0
    canvas.trace_3d_drag_active = False
    canvas.circuit_scroll_x = 0
    canvas.circuit_scroll_y = 0
    canvas.circuit_geometry = {}
    canvas.circuit_display_3d = False
    canvas.circuit_3d_rotate_x = 34.0
    canvas.circuit_3d_rotate_y = -40.0
    canvas.circuit_3d_pan_x = 0.0
    canvas.circuit_3d_pan_y = 0.0
    canvas.circuit_3d_zoom = 1.0
    canvas.circuit_3d_drag_active = False
    canvas.circuit_3d_wire_base = 10.0
    canvas.circuit_3d_wire_band = 56.0
    canvas.dark_mode = False
    canvas.colour_blind_mode = False
    canvas.trace_colours = [
        (0.20, 0.23, 0.78),
        (0.16, 0.50, 0.26),
        (0.70, 0.22, 0.22),
    ]
    canvas.colour_blind_trace_colours = [
        (0.00, 0.45, 0.70),
        (0.90, 0.62, 0.00),
        (0.00, 0.62, 0.45),
    ]
    return canvas


def test_initial_scope_uses_waveform_layout_before_first_run():
    """Test if the startup oscilloscope uses the real row layout."""
    devices = FakeDevices(
        [fake_device("CLK"), fake_device("DATA"), fake_device("OUT")],
        {"CLK": "CLK", "DATA": "DATA_SW", "OUT": "FINAL_TEST"},
    )
    canvas = make_canvas(devices)
    monitor_items = [
        (("CLK", None), []),
        (("DATA", None), []),
        (("OUT", None), []),
    ]
    calls = {}
    rendered_text = []

    canvas.draw_rectangle = lambda *args: None
    canvas.draw_scope_header = lambda *args: None
    canvas.render_text = lambda *args: rendered_text.append(args)
    canvas.draw_scope_grid = lambda *args: calls.setdefault("grid", args)
    canvas.draw_scope_scrollbars = (
        lambda *args: calls.setdefault("scrollbars", args)
    )
    canvas.draw_empty_scope_rows = (
        lambda *args: calls.setdefault("empty_rows", args)
    )
    canvas.draw_scope_axis = lambda *args: calls.setdefault("axis", args)

    canvas.draw_oscilloscope((0, 0, 800, 360), monitor_items)

    assert any("Press Run" in text[0] for text in rendered_text)
    assert calls["grid"][4] == 10
    assert calls["scrollbars"][6] == 10
    assert calls["scrollbars"][7] == 10
    assert calls["scrollbars"][8] == 0
    assert calls["scrollbars"][9] == len(monitor_items)
    assert calls["scrollbars"][10] == len(monitor_items)
    assert calls["empty_rows"][4] == monitor_items
    assert calls["empty_rows"][5] == 10
    assert calls["empty_rows"][6] == 0
    assert calls["axis"][2:] == (10, 0, 10)


def test_initial_scope_respects_vertical_scroll_for_many_monitors():
    """Test if the startup scope only draws visible monitor rows."""
    devices = FakeDevices(
        [fake_device(index) for index in range(12)],
        {index: "SIG_" + str(index) for index in range(12)},
    )
    canvas = make_canvas(devices)
    canvas.scope_first_row = 3
    monitor_items = [((index, None), []) for index in range(12)]
    calls = {}

    canvas.draw_rectangle = lambda *args: None
    canvas.draw_scope_header = lambda *args: None
    canvas.render_text = lambda *args: None
    canvas.draw_scope_grid = lambda *args: None
    canvas.draw_scope_scrollbars = (
        lambda *args: calls.setdefault("scrollbars", args)
    )
    canvas.draw_empty_scope_rows = (
        lambda *args: calls.setdefault("empty_rows", args)
    )
    canvas.draw_scope_axis = lambda *args: None

    canvas.draw_oscilloscope((0, 0, 640, 260), monitor_items)

    visible_items = calls["empty_rows"][4]
    assert visible_items == monitor_items[3:6]
    assert calls["empty_rows"][6] == 3
    assert calls["scrollbars"][9] == 12
    assert calls["scrollbars"][10] == 3


def test_empty_scope_rows_draw_blank_aligned_traces():
    """Test if pre-run rows draw labels, level marks, and blank traces."""
    devices = FakeDevices(
        [fake_device("A"), fake_device("B")],
        {"A": "DATA_SW", "B": "FINAL_TEST"},
    )
    canvas = make_canvas(devices)
    monitor_items = [(("A", None), []), (("B", None), [])]
    labels = []
    colour_indexes = []
    level_rows = []
    traces = []

    def trace_colour(device_id, output_id, index):
        colour_indexes.append(index)
        return (index, 0, 0)

    canvas.trace_colour_for_monitor = trace_colour
    canvas.render_text = lambda text, *args: labels.append(text)
    canvas.draw_signal_level_scale = (
        lambda *args: level_rows.append(args)
    )
    canvas.draw_digital_signal = lambda *args: traces.append(args)

    canvas.draw_empty_scope_rows(
        10, 100, 20, 120, monitor_items, 5, first_row=4
    )

    assert labels == ["DATA_SW", "FINAL_TEST"]
    # Colours are keyed on the signal identity (device order), not the row,
    # so they stay fixed as monitors are added or removed.
    assert colour_indexes == [0, 1]
    assert len(level_rows) == 2
    assert len(traces) == 2
    assert traces[0][2] == [devices.BLANK] * 5
    assert traces[1][2] == [devices.BLANK] * 5


def test_signal_colour_index_is_stable_per_signal_identity():
    """Test if colour indices follow device order and ignore monitor order."""
    devices = FakeDevices(
        [fake_device("A"), fake_device("B"), fake_device("C")],
        {"A": "SIG_A", "B": "SIG_B", "C": "SIG_C"},
    )
    canvas = make_canvas(devices)

    index_a = canvas.signal_colour_index("A", None)
    index_b = canvas.signal_colour_index("B", None)
    index_c = canvas.signal_colour_index("C", None)

    # Each signal gets a distinct index fixed by device declaration order.
    assert [index_a, index_b, index_c] == [0, 1, 2]
    # Querying again (e.g. after monitors change) returns the same indices.
    assert canvas.signal_colour_index("B", None) == index_b
    assert canvas.signal_colour_index("C", None) == index_c


def test_trace_colour_for_monitor_handles_accessibility_modes():
    """Test if trace colours honour clock, QBAR, and colour-blind rules."""
    devices = FakeDevices(
        [
            fake_device("CLK", device_kind=FakeDevices.CLOCK),
            fake_device("DFF"),
        ]
    )
    canvas = make_canvas(devices)

    assert canvas.trace_colour_for_monitor("CLK", None, 0) == (
        0.20, 0.55, 0.25
    )
    assert canvas.trace_colour_for_monitor("DFF", devices.QBAR_ID, 1) == (
        0.48, 0.30, 0.68
    )

    canvas.colour_blind_mode = True

    assert canvas.trace_colour_for_monitor("CLK", None, 4) == (
        canvas.colour_blind_trace_colours[1]
    )


def test_visible_signal_window_pads_short_3d_traces():
    """Test if 3D trace windows keep every visible cycle aligned."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    window = canvas.visible_signal_window(
        [devices.LOW, devices.HIGH], first_cycle=1, cycle_count=4
    )

    assert window == [
        devices.HIGH, devices.BLANK, devices.BLANK, devices.BLANK
    ]
    assert canvas.visible_signal_window(
        [devices.HIGH], 0, 3, use_blank=True
    ) == [devices.BLANK, devices.BLANK, devices.BLANK]


def test_signal_height_3d_maps_digital_levels():
    """Test if 3D traces raise high/rising levels above low/falling."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    assert canvas.signal_height_3d(devices.HIGH) > (
        canvas.signal_height_3d(devices.LOW)
    )
    assert canvas.signal_height_3d(devices.RISING) == (
        canvas.signal_height_3d(devices.HIGH)
    )
    assert canvas.signal_height_3d(devices.FALLING) == (
        canvas.signal_height_3d(devices.LOW)
    )
    assert canvas.signal_height_3d(devices.BLANK) is None


def test_trace_display_3d_toggle_refreshes_canvas():
    """Test if the 3D trace display can be toggled on the canvas."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    refreshed = []
    canvas.Refresh = lambda: refreshed.append(True)
    canvas.init = True

    canvas.set_trace_display_3d(True)

    assert canvas.trace_display_3d is True
    assert canvas.init is False
    assert canvas.trace_3d_drag_active is False
    assert refreshed == [True]


def test_circuit_content_size_grows_only_for_complex_diagrams():
    """Test if simple circuits fit while crowded circuits get scroll space."""
    simple_devices = FakeDevices(
        [
            fake_device("SW"),
            fake_device("GATE", inputs={"I1": ("SW", None)}),
        ],
        {"SW": "SW", "GATE": "GATE"},
    )
    simple_canvas = make_canvas(simple_devices)

    assert simple_canvas.circuit_content_size(500, 300) == (500, 300)

    crowded_device_list = [
        fake_device("SW_" + str(index)) for index in range(8)
    ]
    crowded_device_list.append(
        fake_device(
            "OUT",
            inputs={
                "I" + str(index): ("SW_" + str(index), None)
                for index in range(8)
            },
        )
    )
    crowded_devices = FakeDevices(
        crowded_device_list,
        {device.device_id: device.device_id for device in crowded_device_list},
    )
    crowded_canvas = make_canvas(crowded_devices)

    content_width, content_height = crowded_canvas.circuit_content_size(
        300, 220
    )

    assert content_width > 300
    assert content_height > 220


def test_reset_view_clears_canvas_scroll_and_zoom_state():
    """Test if reset view restores canvas navigation state."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    refreshed = []
    canvas.Refresh = lambda: refreshed.append(True)
    canvas.pan_x = 30
    canvas.pan_y = -20
    canvas.zoom = 1.5
    canvas.circuit_scroll_x = 42
    canvas.circuit_scroll_y = 64
    canvas.circuit_drag_mode = "vertical"
    canvas.scope_first_cycle = 15
    canvas.scope_first_row = 3
    canvas.scope_drag_mode = "horizontal"
    canvas.trace_3d_rotate_x = -10
    canvas.trace_3d_rotate_y = 80
    canvas.trace_3d_pan_x = 22
    canvas.trace_3d_pan_y = -18
    canvas.trace_3d_zoom = 2.3
    canvas.trace_3d_drag_active = True
    canvas.follow_latest_cycles = True
    canvas.init = True

    canvas.reset_view()

    assert canvas.pan_x == 0
    assert canvas.pan_y == 0
    assert canvas.zoom == 1.0
    assert canvas.circuit_scroll_x == 0
    assert canvas.circuit_scroll_y == 0
    assert canvas.circuit_drag_mode is None
    assert canvas.scope_first_cycle == 0
    assert canvas.scope_first_row == 0
    assert canvas.scope_drag_mode is None
    assert canvas.trace_3d_rotate_x == 28.0
    assert canvas.trace_3d_rotate_y == -34.0
    assert canvas.trace_3d_pan_x == 0.0
    assert canvas.trace_3d_pan_y == -4.0
    assert canvas.trace_3d_zoom == 1.0
    assert canvas.trace_3d_drag_active is False
    assert canvas.follow_latest_cycles is False
    assert canvas.init is False
    assert refreshed == [True]


def test_display_bounds_enforce_circuit_and_scope_minimum_regions():
    """Test if sizing keeps circuit and scope independently readable."""
    devices = FakeDevices([fake_device("A"), fake_device("OUT")])
    canvas = make_canvas(devices)
    canvas.min_circuit_height = 220
    canvas.min_scope_height = 280
    canvas.min_view_width = 760
    canvas.canvas_horizontal_padding = 36
    canvas.canvas_top_margin = 18
    canvas.scope_y = 20
    canvas.scope_gap = 8

    min_width, min_height = canvas.minimum_visual_size()
    circuit_bounds, scope_bounds = canvas.calculate_display_bounds(
        SimpleNamespace(width=min_width, height=min_height)
    )

    assert circuit_bounds[2] >= canvas.min_view_width
    assert circuit_bounds[3] >= canvas.min_circuit_height
    assert scope_bounds[2] >= canvas.min_view_width
    assert scope_bounds[3] >= canvas.min_scope_height
    assert circuit_bounds[1] >= scope_bounds[1] + scope_bounds[3]


def test_display_bounds_never_exceed_actual_canvas_width():
    """Test if drawing bounds stay inside the visible canvas width."""
    devices = FakeDevices([fake_device("A"), fake_device("OUT")])
    canvas = make_canvas(devices)
    canvas.min_circuit_height = 220
    canvas.min_scope_height = 280
    canvas.min_view_width = 760
    canvas.canvas_horizontal_padding = 36
    canvas.canvas_top_margin = 18
    canvas.scope_y = 20
    canvas.scope_gap = 8

    narrow_width = 600
    circuit_bounds, scope_bounds = canvas.calculate_display_bounds(
        SimpleNamespace(width=narrow_width, height=760)
    )

    assert circuit_bounds[0] + circuit_bounds[2] <= narrow_width
    assert scope_bounds[0] + scope_bounds[2] <= narrow_width


def test_circuit_3d_wire_height_separates_and_stays_bounded():
    """Test if 3D wires get distinct, non-overlapping, bounded heights."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    # A single wire sits at the base height with nothing to clear.
    assert canvas.circuit_3d_wire_height(0, 1) == canvas.circuit_3d_wire_base
    assert canvas.circuit_3d_wire_top(0) == canvas.circuit_3d_wire_base

    # A few wires spread to the upper gap clamp (14.0) so they read clearly.
    assert canvas.circuit_3d_wire_height(1, 2) == (
        canvas.circuit_3d_wire_base + 14.0
    )

    # Many wires hit the lower gap clamp: the gap never shrinks below the
    # wire thickness (4.5), so wires that cross on the floor still pass over
    # one another rather than overlapping.
    count = 30
    heights = [canvas.circuit_3d_wire_height(i, count) for i in range(count)]
    gaps = [heights[i + 1] - heights[i] for i in range(count - 1)]
    assert heights == sorted(heights)
    assert len(set(heights)) == count
    assert min(gaps) == 4.5
    assert max(gaps) <= 14.0
    assert canvas.circuit_3d_wire_top(count) == heights[-1]


def test_circuit_3d_zoom_keeps_cursor_point_fixed():
    """Test if zooming the 3D circuit pins the cursor's world point."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.Refresh = lambda: None
    view_x, view_y, view_width, view_height = 20, 30, 400, 300
    old_distance = 500.0
    canvas.circuit_geometry = {
        "mode": "3d",
        "viewport": (view_x, view_y, view_width, view_height),
        "camera_distance": old_distance,
        "fov_y": 40.0,
    }
    cursor_x = view_x + 0.75 * view_width
    cursor_y = view_y + 0.20 * view_height
    old_zoom = canvas.circuit_3d_zoom

    canvas.zoom_circuit_3d_at(1.12, cursor_x, cursor_y)

    new_zoom = canvas.circuit_3d_zoom
    assert new_zoom > old_zoom
    new_distance = (
        old_distance * max(old_zoom, 0.2) / max(new_zoom, 0.2)
    )
    tan_y = math.tan(math.radians(20.0))
    tan_x = tan_y * (view_width / view_height)
    ndc_x = 2.0 * (cursor_x - view_x) / view_width - 1.0
    ndc_y = 2.0 * (cursor_y - view_y) / view_height - 1.0
    # The rotated world point under the cursor is fixed; re-projecting it
    # after the zoom must land on the same normalised screen position.
    rotated_x = ndc_x * old_distance * tan_x
    rotated_y = ndc_y * old_distance * tan_y
    reprojected_x = (rotated_x + canvas.circuit_3d_pan_x) / (
        new_distance * tan_x
    )
    reprojected_y = (rotated_y + canvas.circuit_3d_pan_y) / (
        new_distance * tan_y
    )
    assert abs(reprojected_x - ndc_x) < 1e-6
    assert abs(reprojected_y - ndc_y) < 1e-6


def test_circuit_3d_zoom_at_centre_leaves_pan_unchanged():
    """Test if zooming with the cursor centred does not shift the pan."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.Refresh = lambda: None
    canvas.circuit_geometry = {
        "mode": "3d",
        "viewport": (0, 0, 400, 300),
        "camera_distance": 500.0,
        "fov_y": 40.0,
    }

    canvas.zoom_circuit_3d_at(1.12, 200, 150)

    assert canvas.circuit_3d_pan_x == 0.0
    assert canvas.circuit_3d_pan_y == 0.0
    assert canvas.circuit_3d_zoom > 1.0


def test_set_circuit_3d_scroll_maps_fraction_to_pan():
    """Test if scrollbar fractions pan the 3D camera across its range."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.circuit_geometry = {
        "mode": "3d", "max_pan_x": 100.0, "max_pan_y": 80.0,
    }

    # Vertical: fraction 0 frames the top, 1 the bottom, 0.5 the centre.
    canvas.set_circuit_3d_scroll("vertical", 0.0)
    assert canvas.circuit_3d_pan_y == -80.0
    canvas.set_circuit_3d_scroll("vertical", 1.0)
    assert canvas.circuit_3d_pan_y == 80.0
    canvas.set_circuit_3d_scroll("vertical", 0.5)
    assert canvas.circuit_3d_pan_y == 0.0

    # Horizontal: fraction 0 frames the left, 1 the right.
    canvas.set_circuit_3d_scroll("horizontal", 0.0)
    assert canvas.circuit_3d_pan_x == 100.0
    canvas.set_circuit_3d_scroll("horizontal", 1.0)
    assert canvas.circuit_3d_pan_x == -100.0

    # Out-of-range fractions are clamped, never flinging the camera away.
    canvas.set_circuit_3d_scroll("vertical", 5.0)
    assert canvas.circuit_3d_pan_y == 80.0


def test_circuit_3d_scrollbar_drag_pans_camera():
    """Test if dragging the 3D scrollbar thumb moves the camera pan."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.draw_rectangle = lambda *args, **kwargs: None
    view_bounds = (10, 40, 400, 300)
    canvas.circuit_geometry = {
        "mode": "3d",
        "max_pan_x": 100.0, "max_pan_y": 80.0,
        "content_x": 600.0, "content_y": 500.0,
        "visible_x": 300.0, "visible_y": 250.0,
    }
    canvas.draw_circuit_scrollbars_3d(view_bounds)

    track = canvas.circuit_geometry["vertical_track"]
    thumb = canvas.circuit_geometry["vertical_thumb"]
    track_y, thumb_height = track[1], thumb[3]
    usable = max(track[3] - thumb_height, 1)
    canvas.circuit_drag_mode = "vertical"
    canvas.circuit_drag_offset = 0

    # Thumb dragged to the top of the track frames the top of the scene.
    canvas.update_circuit_scroll_drag(track[0], track_y + usable)
    assert canvas.circuit_3d_pan_y == -80.0
    # Thumb dragged to the bottom frames the bottom of the scene.
    canvas.update_circuit_scroll_drag(track[0], track_y)
    assert canvas.circuit_3d_pan_y == 80.0


def test_prefer_x11_backend_only_when_x_display_available():
    """Test if the GTK backend default applies only on Linux with X."""
    import display_backend

    env = {"DISPLAY": ":0"}
    assert display_backend.prefer_x11_backend(env, "linux") == "x11"
    assert env["GDK_BACKEND"] == "x11"

    # An explicit user choice is never overridden.
    env = {"DISPLAY": ":0", "GDK_BACKEND": "wayland"}
    assert display_backend.prefer_x11_backend(env, "linux") == "wayland"

    # Pure-Wayland sessions (no X server) keep their native backend.
    env = {"WAYLAND_DISPLAY": "wayland-0"}
    assert display_backend.prefer_x11_backend(env, "linux") is None
    assert "GDK_BACKEND" not in env

    # Other platforms are untouched.
    env = {"DISPLAY": ":0"}
    assert display_backend.prefer_x11_backend(env, "win32") is None
    assert "GDK_BACKEND" not in env


def test_axis_gizmo_axes_track_camera_rotation():
    """Test if the axis indicator directions follow the 3D camera."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    # Identity camera: X right, Y up, Z toward the viewer (drawn last).
    axes = {label: (dx, dy, depth) for label, dx, dy, depth
            in canvas.axis_gizmo_axes(0.0, 0.0)}
    assert axes["X"][0] > 0.99 and abs(axes["X"][1]) < 1e-9
    assert axes["Y"][1] > 0.99 and abs(axes["Y"][0]) < 1e-9
    assert axes["Z"][2] > 0.99
    assert canvas.axis_gizmo_axes(0.0, 0.0)[-1][0] == "Z"

    # Yaw the camera 90 degrees: X swings toward the viewer, Z to the left.
    axes = {label: (dx, dy, depth) for label, dx, dy, depth
            in canvas.axis_gizmo_axes(0.0, -90.0)}
    assert axes["X"][2] > 0.99
    assert axes["Z"][0] < -0.99
    # Y is unaffected by yaw alone.
    assert axes["Y"][1] > 0.99


def test_project_3d_trace_point_matches_camera_centre():
    """Test if the trace projection puts the scene centre mid-viewport."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    camera = {
        "viewport": (40, 30, 400, 300),
        "distance": 500.0,
        "aspect": 400 / 300,
        "rotate_x": 28.0,
        "rotate_y": -34.0,
        "pan_x": 0.0,
        "pan_y": 0.0,
    }

    centre = canvas.project_3d_trace_point(0.0, 0.0, 0.0, camera)

    assert centre is not None
    assert abs(centre[0] - (40 + 200)) < 1e-6
    assert abs(centre[1] - (30 + 150)) < 1e-6

    # A point on the +X axis lands right of centre under a level camera.
    camera["rotate_x"] = 0.0
    camera["rotate_y"] = 0.0
    right = canvas.project_3d_trace_point(50.0, 0.0, 0.0, camera)
    assert right[0] > 240 and abs(right[1] - 180) < 1e-6
    # Points behind the camera are rejected rather than mirrored.
    assert canvas.project_3d_trace_point(0.0, 0.0, 600.0, camera) is None


def test_build_3d_scope_row_hits_supports_hover_picking():
    """Test if 3D scope rows project to pickable named segments."""
    devices = FakeDevices(
        [fake_device("A"), fake_device("B"), fake_device("C")],
        {"A": "SIG_A", "B": "SIG_B", "C": "SIG_C"},
    )
    canvas = make_canvas(devices)
    canvas.trace_3d_pan_x = 0.0
    canvas.trace_3d_pan_y = 0.0
    canvas.trace_3d_rotate_x = 28.0
    canvas.trace_3d_rotate_y = -34.0
    monitor_items = [
        (("A", None), []), (("B", None), []), (("C", None), []),
    ]

    rows = canvas.build_3d_scope_row_hits(
        (0, 0, 480, 360), monitor_items, cycle_span=180.0, row_span=44.0,
        row_pitch=22.0, camera_distance=420.0, aspect=480 / 360
    )

    assert [row["name"] for row in rows] == ["SIG_A", "SIG_B", "SIG_C"]
    canvas.scope_geometry = {"rows_3d": rows}
    for row in rows:
        mid_x = (row["start"][0] + row["end"][0]) / 2
        mid_y = (row["start"][1] + row["end"][1]) / 2
        assert canvas.pick_3d_scope_row(mid_x, mid_y) == row["name"]
    # Far from every row nothing is picked.
    assert canvas.pick_3d_scope_row(-500.0, -500.0) is None


def test_point_segment_distance_handles_interior_and_endpoints():
    """Test if point-to-segment distance clamps to the segment ends."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    assert canvas.point_segment_distance(50, 10, 0, 10, 100, 10) == 0.0
    assert canvas.point_segment_distance(50, 16, 0, 10, 100, 10) == 6.0
    # Beyond an endpoint the distance is measured to that endpoint.
    assert canvas.point_segment_distance(103, 14, 0, 10, 100, 10) == 5.0
    # Degenerate zero-length segments behave like a point.
    assert canvas.point_segment_distance(3, 4, 0, 0, 0, 0) == 5.0
