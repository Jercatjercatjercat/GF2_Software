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

    canvas._draw_rectangle = lambda *args: None
    canvas._draw_scope_header = lambda *args: None
    canvas.render_text = lambda *args: rendered_text.append(args)
    canvas._draw_scope_grid = lambda *args: calls.setdefault("grid", args)
    canvas._draw_scope_scrollbars = (
        lambda *args: calls.setdefault("scrollbars", args)
    )
    canvas._draw_empty_scope_rows = (
        lambda *args: calls.setdefault("empty_rows", args)
    )
    canvas._draw_scope_axis = lambda *args: calls.setdefault("axis", args)

    canvas._draw_oscilloscope((0, 0, 800, 360), monitor_items)

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

    canvas._draw_rectangle = lambda *args: None
    canvas._draw_scope_header = lambda *args: None
    canvas.render_text = lambda *args: None
    canvas._draw_scope_grid = lambda *args: None
    canvas._draw_scope_scrollbars = (
        lambda *args: calls.setdefault("scrollbars", args)
    )
    canvas._draw_empty_scope_rows = (
        lambda *args: calls.setdefault("empty_rows", args)
    )
    canvas._draw_scope_axis = lambda *args: None

    canvas._draw_oscilloscope((0, 0, 640, 260), monitor_items)

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

    canvas._trace_colour_for_monitor = trace_colour
    canvas.render_text = lambda text, *args: labels.append(text)
    canvas._draw_signal_level_scale = (
        lambda *args: level_rows.append(args)
    )
    canvas._draw_digital_signal = lambda *args: traces.append(args)

    canvas._draw_empty_scope_rows(
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

    index_a = canvas._signal_colour_index("A", None)
    index_b = canvas._signal_colour_index("B", None)
    index_c = canvas._signal_colour_index("C", None)

    # Each signal gets a distinct index fixed by device declaration order.
    assert [index_a, index_b, index_c] == [0, 1, 2]
    # Querying again (e.g. after monitors change) returns the same indices.
    assert canvas._signal_colour_index("B", None) == index_b
    assert canvas._signal_colour_index("C", None) == index_c


def test_trace_colour_for_monitor_handles_accessibility_modes():
    """Test if trace colours honour clock, QBAR, and colour-blind rules."""
    devices = FakeDevices(
        [
            fake_device("CLK", device_kind=FakeDevices.CLOCK),
            fake_device("DFF"),
        ]
    )
    canvas = make_canvas(devices)

    assert canvas._trace_colour_for_monitor("CLK", None, 0) == (
        0.20, 0.55, 0.25
    )
    assert canvas._trace_colour_for_monitor("DFF", devices.QBAR_ID, 1) == (
        0.48, 0.30, 0.68
    )

    canvas.colour_blind_mode = True

    assert canvas._trace_colour_for_monitor("CLK", None, 4) == (
        canvas.colour_blind_trace_colours[1]
    )


def test_visible_signal_window_pads_short_3d_traces():
    """Test if 3D trace windows keep every visible cycle aligned."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    window = canvas._visible_signal_window(
        [devices.LOW, devices.HIGH], first_cycle=1, cycle_count=4
    )

    assert window == [
        devices.HIGH, devices.BLANK, devices.BLANK, devices.BLANK
    ]
    assert canvas._visible_signal_window(
        [devices.HIGH], 0, 3, use_blank=True
    ) == [devices.BLANK, devices.BLANK, devices.BLANK]


def test_signal_height_3d_maps_digital_levels():
    """Test if 3D traces raise high/rising levels above low/falling."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    assert canvas._signal_height_3d(devices.HIGH) > (
        canvas._signal_height_3d(devices.LOW)
    )
    assert canvas._signal_height_3d(devices.RISING) == (
        canvas._signal_height_3d(devices.HIGH)
    )
    assert canvas._signal_height_3d(devices.FALLING) == (
        canvas._signal_height_3d(devices.LOW)
    )
    assert canvas._signal_height_3d(devices.BLANK) is None


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

    assert simple_canvas._circuit_content_size(500, 300) == (500, 300)

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

    content_width, content_height = crowded_canvas._circuit_content_size(
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
    circuit_bounds, scope_bounds = canvas._calculate_display_bounds(
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
    circuit_bounds, scope_bounds = canvas._calculate_display_bounds(
        SimpleNamespace(width=narrow_width, height=760)
    )

    assert circuit_bounds[0] + circuit_bounds[2] <= narrow_width
    assert scope_bounds[0] + scope_bounds[2] <= narrow_width


def test_circuit_3d_wire_height_separates_and_stays_bounded():
    """Test if 3D wires get distinct, non-overlapping, bounded heights."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    # A single wire sits at the base height with nothing to clear.
    assert canvas._circuit_3d_wire_height(0, 1) == canvas.circuit_3d_wire_base
    assert canvas._circuit_3d_wire_top(0) == canvas.circuit_3d_wire_base

    # A few wires spread to the upper gap clamp (14.0) so they read clearly.
    assert canvas._circuit_3d_wire_height(1, 2) == (
        canvas.circuit_3d_wire_base + 14.0
    )

    # Many wires hit the lower gap clamp: the gap never shrinks below the
    # wire thickness (4.5), so wires that cross on the floor still pass over
    # one another rather than overlapping.
    count = 30
    heights = [canvas._circuit_3d_wire_height(i, count) for i in range(count)]
    gaps = [heights[i + 1] - heights[i] for i in range(count - 1)]
    assert heights == sorted(heights)
    assert len(set(heights)) == count
    assert min(gaps) == 4.5
    assert max(gaps) <= 14.0
    assert canvas._circuit_3d_wire_top(count) == heights[-1]


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

    canvas._zoom_circuit_3d_at(1.12, cursor_x, cursor_y)

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

    canvas._zoom_circuit_3d_at(1.12, 200, 150)

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
    canvas._set_circuit_3d_scroll("vertical", 0.0)
    assert canvas.circuit_3d_pan_y == -80.0
    canvas._set_circuit_3d_scroll("vertical", 1.0)
    assert canvas.circuit_3d_pan_y == 80.0
    canvas._set_circuit_3d_scroll("vertical", 0.5)
    assert canvas.circuit_3d_pan_y == 0.0

    # Horizontal: fraction 0 frames the left, 1 the right.
    canvas._set_circuit_3d_scroll("horizontal", 0.0)
    assert canvas.circuit_3d_pan_x == 100.0
    canvas._set_circuit_3d_scroll("horizontal", 1.0)
    assert canvas.circuit_3d_pan_x == -100.0

    # Out-of-range fractions are clamped, never flinging the camera away.
    canvas._set_circuit_3d_scroll("vertical", 5.0)
    assert canvas.circuit_3d_pan_y == 80.0


def test_circuit_3d_scrollbar_drag_pans_camera():
    """Test if dragging the 3D scrollbar thumb moves the camera pan."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas._draw_rectangle = lambda *args, **kwargs: None
    view_bounds = (10, 40, 400, 300)
    canvas.circuit_geometry = {
        "mode": "3d",
        "max_pan_x": 100.0, "max_pan_y": 80.0,
        "content_x": 600.0, "content_y": 500.0,
        "visible_x": 300.0, "visible_y": 250.0,
    }
    canvas._draw_circuit_scrollbars_3d(view_bounds)

    track = canvas.circuit_geometry["vertical_track"]
    thumb = canvas.circuit_geometry["vertical_thumb"]
    track_y, thumb_height = track[1], thumb[3]
    usable = max(track[3] - thumb_height, 1)
    canvas.circuit_drag_mode = "vertical"
    canvas.circuit_drag_offset = 0

    # Thumb dragged to the top of the track frames the top of the scene.
    canvas._update_circuit_scroll_drag(track[0], track_y + usable)
    assert canvas.circuit_3d_pan_y == -80.0
    # Thumb dragged to the bottom frames the bottom of the scene.
    canvas._update_circuit_scroll_drag(track[0], track_y)
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
            in canvas._axis_gizmo_axes(0.0, 0.0)}
    assert axes["X"][0] > 0.99 and abs(axes["X"][1]) < 1e-9
    assert axes["Y"][1] > 0.99 and abs(axes["Y"][0]) < 1e-9
    assert axes["Z"][2] > 0.99
    assert canvas._axis_gizmo_axes(0.0, 0.0)[-1][0] == "Z"

    # Yaw the camera 90 degrees: X swings toward the viewer, Z to the left.
    axes = {label: (dx, dy, depth) for label, dx, dy, depth
            in canvas._axis_gizmo_axes(0.0, -90.0)}
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

    centre = canvas._project_3d_trace_point(0.0, 0.0, 0.0, camera)

    assert centre is not None
    assert abs(centre[0] - (40 + 200)) < 1e-6
    assert abs(centre[1] - (30 + 150)) < 1e-6

    # A point on the +X axis lands right of centre under a level camera.
    camera["rotate_x"] = 0.0
    camera["rotate_y"] = 0.0
    right = canvas._project_3d_trace_point(50.0, 0.0, 0.0, camera)
    assert right[0] > 240 and abs(right[1] - 180) < 1e-6
    # Points behind the camera are rejected rather than mirrored.
    assert canvas._project_3d_trace_point(0.0, 0.0, 600.0, camera) is None


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

    rows = canvas._build_3d_scope_row_hits(
        (0, 0, 480, 360), monitor_items, cycle_span=180.0, row_span=44.0,
        row_pitch=22.0, camera_distance=420.0, aspect=480 / 360
    )

    assert [row["name"] for row in rows] == ["SIG_A", "SIG_B", "SIG_C"]
    canvas.scope_geometry = {"rows_3d": rows}
    for row in rows:
        mid_x = (row["start"][0] + row["end"][0]) / 2
        mid_y = (row["start"][1] + row["end"][1]) / 2
        assert canvas._pick_3d_scope_row(mid_x, mid_y) == row["name"]
    # Far from every row nothing is picked.
    assert canvas._pick_3d_scope_row(-500.0, -500.0) is None


def test_point_segment_distance_handles_interior_and_endpoints():
    """Test if point-to-segment distance clamps to the segment ends."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    assert canvas._point_segment_distance(50, 10, 0, 10, 100, 10) == 0.0
    assert canvas._point_segment_distance(50, 16, 0, 10, 100, 10) == 6.0
    # Beyond an endpoint the distance is measured to that endpoint.
    assert canvas._point_segment_distance(103, 14, 0, 10, 100, 10) == 5.0
    # Degenerate zero-length segments behave like a point.
    assert canvas._point_segment_distance(3, 4, 0, 0, 0, 0) == 5.0


def make_monitors(monitor_dict=None):
    """Create a minimal fake monitors object for canvas tests."""
    return SimpleNamespace(monitors_dictionary=monitor_dict or {})


def test_zoom_circuit_clamps_and_scales_scroll():
    """Test if circuit zoom stays bounded and rescales the scroll."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.Refresh = lambda: None
    canvas.circuit_zoom = 1.0
    canvas.circuit_scroll_x = 100
    canvas.circuit_scroll_y = 50

    canvas._zoom_circuit(2.0)

    assert canvas.circuit_zoom == 2.0
    # The scroll scales with the zoom so the view stays in place.
    assert canvas.circuit_scroll_x == 200
    assert canvas.circuit_scroll_y == 100

    canvas._zoom_circuit(100.0)
    assert canvas.circuit_zoom == 3.0
    canvas._zoom_circuit(0.0001)
    assert canvas.circuit_zoom == 0.1


def test_zoom_circuit_at_keeps_cursor_point_fixed():
    """Test if 2D circuit zoom pins the diagram point under the mouse."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.Refresh = lambda: None
    view = (20, 30, 400, 300)
    canvas.circuit_geometry = {"view": view}
    canvas.last_circuit_content = (1600, 1200)
    canvas.circuit_zoom = 1.0
    canvas.circuit_scroll_x = 300
    canvas.circuit_scroll_y = 200
    cursor_x, cursor_y = 220, 180

    view_x, view_y, view_width, view_height = view
    origin_x = view_x - canvas.circuit_scroll_x
    origin_y = view_y + view_height - 1200 + canvas.circuit_scroll_y
    base_x = (cursor_x - origin_x) / canvas.circuit_zoom
    base_y = (cursor_y - origin_y) / canvas.circuit_zoom

    canvas._zoom_circuit_at(1.25, cursor_x, cursor_y)

    new_zoom = canvas.circuit_zoom
    assert new_zoom == 1.25
    origin_x = view_x - canvas.circuit_scroll_x
    origin_y = (
        view_y + view_height - 1200 * new_zoom + canvas.circuit_scroll_y
    )
    assert abs((cursor_x - origin_x) / new_zoom - base_x) < 1e-9
    assert abs((cursor_y - origin_y) / new_zoom - base_y) < 1e-9


def test_fit_circuit_packs_content_and_resets_scroll():
    """Test if fitting the 2D circuit zooms out and recentres it."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.Refresh = lambda: None
    canvas.circuit_zoom = 2.5
    canvas.circuit_scroll_x = 120
    canvas.circuit_scroll_y = 60
    canvas.last_circuit_view = (400, 300)
    canvas.last_circuit_content = (1600, 600)

    canvas.fit_circuit()

    # The zoom fits the wider axis (400/1600) with a small margin.
    assert abs(canvas.circuit_zoom - 0.25 * 0.97) < 1e-9
    assert canvas.circuit_scroll_x == 0
    assert canvas.circuit_scroll_y == 0

    # In 3D mode the camera is reset instead of the 2D zoom.
    canvas.circuit_display_3d = True
    canvas.circuit_3d_zoom = 3.0
    canvas.circuit_3d_pan_x = 50.0
    canvas.fit_circuit()
    assert canvas.circuit_3d_zoom == 1.0
    assert canvas.circuit_3d_pan_x == 0.0


def test_fit_scope_packs_all_rows_and_cycles():
    """Test if fitting the scope shows every monitor row and cycle."""
    devices = FakeDevices([fake_device("A"), fake_device("B")])
    canvas = make_canvas(devices)
    canvas.Refresh = lambda: None
    canvas.monitors = make_monitors({
        ("A", None): [0, 1] * 50,
        ("B", None): [1, 0] * 50,
    })
    canvas.last_scope_plot_width = 500
    canvas.last_scope_plot_height = 60
    canvas.scope_first_cycle = 40
    canvas.scope_first_row = 1
    canvas.follow_latest_cycles = True

    canvas.fit_scope()

    assert canvas.scope_first_cycle == 0
    assert canvas.scope_first_row == 0
    assert canvas.follow_latest_cycles is False
    # 100 cycles in 500 px needs 5 px per cycle = zoom 5/28.
    assert abs(canvas.scope_cycle_zoom - 5 / 28) < 1e-9
    # The row zoom packs both rows into the 60 px plot.
    assert canvas.scope_row_zoom == 60 / (34 * 2)


def test_zoom_scope_clamps_and_stops_following():
    """Test if scope zooming clamps and stops auto-following cycles."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    canvas.Refresh = lambda: None
    canvas.scope_cycle_zoom = 1.0
    canvas.follow_latest_cycles = True

    canvas._zoom_scope(100.0)

    assert canvas.scope_cycle_zoom == 4.0
    assert canvas.follow_latest_cycles is False

    canvas.scope_row_zoom = 1.0
    canvas._zoom_scope_rows(0.0001)
    assert canvas.scope_row_zoom == 0.2


def test_scope_row_geometry_keeps_rows_readable():
    """Test if scope row maths respects floors, caps, and counts."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    # Zoomed out, more rows fit; never more than exist.
    canvas.scope_row_zoom = 1.0
    assert canvas._scope_visible_rows(340, 20) == 10
    canvas.scope_row_zoom = 0.2
    assert canvas._scope_visible_rows(340, 20) == 20
    assert canvas._scope_visible_rows(340, 3) == 3
    assert canvas._scope_visible_rows(5, 20) == 1

    # The row gap fills the plot but stays within readable bounds.
    assert canvas._scope_row_gap(300, 10) == 30
    assert canvas._scope_row_gap(300, 100) == canvas.min_row_band
    assert canvas._scope_row_gap(300, 1) == 88.0
    # The waveform half-height always fits inside the row band.
    assert canvas._scope_row_amplitude(30) == 12.6
    assert canvas._scope_row_amplitude(1) == 4.0
    assert canvas._scope_row_amplitude(500) == canvas.high_offset


def test_signal_y_maps_levels_and_rejects_blanks():
    """Test if signal levels map to trace heights, blanks to None."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    assert canvas._signal_y(devices.HIGH, 90, 70) == 90
    assert canvas._signal_y(devices.RISING, 90, 70) == 90
    assert canvas._signal_y(devices.LOW, 90, 70) == 70
    assert canvas._signal_y(devices.FALLING, 90, 70) == 70
    assert canvas._signal_y(devices.BLANK, 90, 70) is None


def test_calculate_device_layers_orders_by_dependency():
    """Test if devices are layered by input dependency depth."""
    source = fake_device("A")
    middle = fake_device("B", inputs={"I1": ("A", None)})
    sink = fake_device("C", inputs={"I1": ("B", None)})
    devices = FakeDevices([sink, source, middle])
    canvas = make_canvas(devices)

    layers = canvas._calculate_device_layers()

    assert layers == {"A": 0, "B": 1, "C": 2}


def test_calculate_device_layers_handles_feedback_loops():
    """Test if mutually dependent devices settle on a default layer."""
    first = fake_device("D", inputs={"I1": ("E", None)})
    second = fake_device("E", inputs={"I1": ("D", None)})
    devices = FakeDevices([first, second])
    canvas = make_canvas(devices)

    layers = canvas._calculate_device_layers()

    # The loop cannot be ordered, so both fall back to layer 1.
    assert layers == {"D": 1, "E": 1}


def test_build_device_positions_places_layers_in_columns():
    """Test if the layout puts each dependency layer in its own column."""
    source_a = fake_device("A")
    source_b = fake_device("B")
    gate = fake_device(
        "G", inputs={"I1": ("A", None), "I2": ("B", None)}
    )
    devices = FakeDevices([source_a, source_b, gate])
    canvas = make_canvas(devices)
    bounds = (0, 0, 1000, 600)

    positions = canvas._build_device_positions(bounds)

    assert set(positions) == {"A", "B", "G"}
    # Sources share a column; the gate sits in the next column right.
    assert positions["A"][0] == positions["B"][0]
    assert positions["G"][0] > positions["A"][0]
    for x_pos, y_pos, width, height in positions.values():
        assert x_pos >= 0 and y_pos >= 0
        assert x_pos + width <= 1000 and y_pos + height <= 600
    assert canvas.circuit_grid["max_layer"] == 1
    assert (
        canvas.circuit_grid["rows"]["A"] != canvas.circuit_grid["rows"]["B"]
    )


def test_wire_routing_gives_each_wire_its_own_lane():
    """Test if routed wires use distinct lanes and join the real pins."""
    source_a = fake_device("A")
    source_b = fake_device("B")
    gate = fake_device(
        "G", inputs={"I1": ("A", None), "I2": ("B", None)}
    )
    devices = FakeDevices([source_a, source_b, gate])
    canvas = make_canvas(devices)
    positions = canvas._build_device_positions((0, 0, 1000, 600))

    paths = canvas._circuit_wire_paths(positions, canvas.circuit_grid)

    assert len(paths) == 2
    lane_xs = set()
    for points, _signal in paths:
        # Each segment is orthogonal (no diagonals).
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            assert x1 == x2 or y1 == y2
        lane_xs.add(points[1][0])
        # The route starts at an output pin and ends at an input pin.
        assert points[0][0] in (
            positions["A"][0] + positions["A"][2],
            positions["B"][0] + positions["B"][2],
        )
        assert points[-1][0] == positions["G"][0]
    # The two wires occupy different vertical lanes in the channel.
    assert len(lane_xs) == 2


def test_circuit_3d_layout_centres_the_floor_plan():
    """Test if the 3D layout centres blocks and reports real spans."""
    left = fake_device("A")
    right = fake_device("G", inputs={"I1": ("A", None)})
    devices = FakeDevices([left, right])
    canvas = make_canvas(devices)
    positions = canvas._build_device_positions((0, 0, 1000, 600))

    layout = canvas._circuit_3d_layout(positions)

    block_a = layout["blocks"]["A"]
    block_g = layout["blocks"]["G"]
    # The two blocks are symmetric about the centred origin, and the
    # reported span is exactly the distance between their centres.
    assert abs(block_a[0] + block_g[0]) < 1e-9
    assert abs(layout["span_x"] - (block_g[0] - block_a[0])) < 1e-9
    # Half-width is the scaled block width (116 px blocks at 0.6 scale).
    assert abs(block_a[2] - 116 * 0.6 / 2) < 1e-9


def test_circuit_block_height_3d_tracks_output_level():
    """Test if 3D tower heights reflect the live output level."""
    high_device = fake_device("H")
    high_device.outputs = {None: FakeDevices.HIGH}
    low_device = fake_device("L")
    no_output = fake_device("N")
    no_output.outputs = {}
    devices = FakeDevices([high_device, low_device, no_output])
    canvas = make_canvas(devices)

    high = canvas._circuit_block_height_3d(high_device)
    low = canvas._circuit_block_height_3d(low_device)
    idle = canvas._circuit_block_height_3d(no_output)

    assert high > idle > low


def test_trace_3d_level_colour_dims_low_levels_only():
    """Test if low 3D blocks are dimmed without losing identity."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    colour = (0.2, 0.4, 0.8)

    assert canvas._trace_3d_level_colour(colour, devices.HIGH) == colour
    dimmed = canvas._trace_3d_level_colour(colour, devices.LOW)
    # Low blocks compress every channel toward a dim grey midpoint, so
    # the overall colour darkens while staying recognisable and valid.
    for channel, original in zip(dimmed, colour):
        assert abs(channel - (original * 0.55 + 0.12)) < 1e-9
        assert 0.0 <= channel <= 1.0
    assert sum(dimmed) < sum(colour)


def test_scope_label_and_cycle_helpers():
    """Test the label width, recorded cycles, and port ordering maths."""
    devices = FakeDevices(
        [fake_device("A")],
        {"A": "LONG_SIGNAL_NAME", "P1": "Z_OUT", "P2": "A_OUT"},
    )
    canvas = make_canvas(devices)
    items = [(("A", None), [0, 1, 0]), (("A", "P1"), [1])]

    assert canvas._max_recorded_cycles(items) == 3
    assert canvas._max_recorded_cycles([]) == 0
    # Long names widen the label margin beyond the minimum.
    width = canvas._calculate_scope_label_width(items)
    assert width == 28 + len("LONG_SIGNAL_NAME.Z_OUT") * 8
    # Ports sort by DISPLAY name (P2 -> "A_OUT" before P1 -> "Z_OUT"),
    # not by raw ID, with unnamed outputs first.
    assert canvas._port_sort_name(None) == ""
    assert canvas._sorted_port_ids({"P1": 1, None: 2, "P2": 3}) == [
        None, "P2", "P1"
    ]


def test_pdf_builder_produces_wellformed_documents(tmp_path):
    """Test if the PDF exporter writes a parseable one-page file."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    assert canvas._pdf_number(12.0) == "12"
    assert canvas._pdf_number(8.25) == "8.25"

    path = str(tmp_path / "scope.pdf")
    canvas._write_image_pdf(path, 4, 2, bytes(4 * 2 * 3))
    with open(path, "rb") as handle:
        data = handle.read()
    assert data.startswith(b"%PDF-1.4")
    assert data.rstrip().endswith(b"%%EOF")
    # Landscape page for a wide image, with the real pixel size.
    assert b"/MediaBox [0 0 842 595]" in data
    assert b"/Width 4 /Height 2" in data
    assert data.count(b"endobj") == 5


def test_update_3d_hover_drives_the_tooltip():
    """Test if hovering 3D rows sets and clears the canvas tooltip."""
    devices = FakeDevices([fake_device("A")], {"A": "SIG_A"})
    canvas = make_canvas(devices)
    tooltips = []
    canvas.SetToolTip = lambda name: tooltips.append(name)
    canvas.UnsetToolTip = lambda: tooltips.append(None)
    canvas.trace_display_3d = True
    canvas.scope_geometry = {
        "plot": (0, 0, 400, 300),
        "rows_3d": [
            {"name": "SIG_A", "start": (10, 50), "end": (390, 60)}
        ],
    }

    canvas._update_3d_hover(200, 55)
    assert canvas.hover_3d_name == "SIG_A"
    # Repeated hovering over the same row does not churn the tooltip.
    canvas._update_3d_hover(210, 56)
    canvas._update_3d_hover(200, 250)
    assert canvas.hover_3d_name is None
    assert tooltips == ["SIG_A", None]


def test_theme_colour_differs_between_light_and_dark():
    """Test if theme colours change with dark mode and stay valid."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)

    canvas.dark_mode = False
    light = canvas._theme_colour("canvas_bg")
    canvas.dark_mode = True
    dark = canvas._theme_colour("canvas_bg")

    assert light != dark
    for colour in (light, dark):
        assert len(colour) == 3
        assert all(0.0 <= channel <= 1.0 for channel in colour)


def test_estimate_circuit_height_grows_with_stacked_devices():
    """Test if the circuit height estimate grows with layer crowding."""
    small = FakeDevices([fake_device("A")])
    crowded = FakeDevices([
        fake_device("A"), fake_device("B"), fake_device("C"),
        fake_device("D"),
    ])

    short = make_canvas(small)._estimate_circuit_height()
    tall = make_canvas(crowded)._estimate_circuit_height()

    assert tall > short


def test_point_in_rect_handles_edges_and_missing_rects():
    """Test if rectangle hit-testing includes edges and rejects None."""
    devices = FakeDevices([fake_device("A")])
    canvas = make_canvas(devices)
    rect = (10, 20, 100, 50)

    assert canvas._point_in_rect(10, 20, rect)
    assert canvas._point_in_rect(110, 70, rect)
    assert not canvas._point_in_rect(9.9, 20, rect)
    assert not canvas._point_in_rect(10, 70.1, rect)
    assert not canvas._point_in_rect(50, 40, None)
