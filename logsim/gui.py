"""Implement the graphical user interface for the Logic Simulator.

The GUI mirrors the required command-line operations: run, continue, set a
switch, add a monitor, and remove a monitor.  Signal traces are drawn in an
OpenGL canvas and can be panned or zoomed with the mouse.
"""

import math
import os
import shutil
import sys
import zlib

import display_backend  # noqa: F401  (sets GDK_BACKEND before wx loads)
import wx
import wx.glcanvas as wxcanvas
from OpenGL import GL, GLU, GLUT

from language import (
    DEFAULT_LANGUAGE,
    choose_language,
    initialise_wx_locale,
    load_language_names,
    load_translations,
    translate,
)
from names import Names
from devices import Devices
from network import Network
from monitors import Monitors
from scanner import Scanner
from parse import Parser, parse_network_with_diagnostics
from gui_controller import GuiController


def show_parse_error_dialog(parent, path, diagnostics, language_code=None):
    """Show parser diagnostics in the GUI as well as the terminal."""
    translations = load_translations()
    if language_code not in translations:
        language_code = choose_language(translations, wx)

    def t(key):
        """Return translated text for the parser dialog."""
        return translate(translations, language_code, key)

    message = t("parse_error_intro") + "\n" + str(path)
    diagnostics = diagnostics.strip()
    if diagnostics:
        message += "\n\n" + diagnostics
    else:
        message += "\n\n" + t("parse_error_empty")

    wx.MessageBox(
        message,
        t("parse_error_title"),
        wx.OK | wx.ICON_ERROR,
        parent,
    )


class MyGLCanvas(wxcanvas.GLCanvas):
    """Draw monitor waveforms in an OpenGL canvas."""

    def __init__(self, parent, devices, monitors, translator=None):
        """Initialise canvas state and event bindings."""
        super().__init__(
            parent,
            -1,
            attribList=[
                wxcanvas.WX_GL_RGBA,
                wxcanvas.WX_GL_DOUBLEBUFFER,
                wxcanvas.WX_GL_DEPTH_SIZE,
                16,
                0,
            ],
        )
        GLUT.glutInit()
        self.init = False
        self.context = wxcanvas.GLContext(self)
        self.devices = devices
        self.monitors = monitors
        self.translator = translator

        self.pan_x = 0
        self.pan_y = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.zoom = 1.0
        self.circuit_scroll_x = 0
        self.circuit_scroll_y = 0
        self.circuit_zoom = 1.0
        self.scope_cycle_zoom = 1.0
        self.scope_row_zoom = 1.0
        self.circuit_drag_mode = None
        self.circuit_drag_offset = 0
        self.circuit_geometry = {}
        self.scope_first_cycle = 0
        self.scope_first_row = 0
        self.scope_drag_mode = None
        self.scope_drag_offset = 0
        self.scope_geometry = {}
        self.follow_latest_cycles = True
        self.view_mode = "split"
        self.last_scope_plot_width = 0
        self.dark_mode = False
        self.colour_blind_mode = False
        self.last_circuit_bounds = None
        self.last_scope_bounds = None
        self.trace_display_3d = False
        self.trace_3d_rotate_x = 28.0
        self.trace_3d_rotate_y = -34.0
        self.trace_3d_pan_x = 0.0
        self.trace_3d_pan_y = -4.0
        self.trace_3d_zoom = 1.0
        self.trace_3d_drag_active = False
        self.circuit_display_3d = False
        self.circuit_3d_rotate_x = 34.0
        self.circuit_3d_rotate_y = -40.0
        self.circuit_3d_pan_x = 0.0
        self.circuit_3d_pan_y = 0.0
        self.circuit_3d_zoom = 1.0
        self.circuit_3d_drag_active = False
        self.circuit_3d_wire_base = 10.0
        self.circuit_3d_wire_band = 56.0
        self.hover_3d_name = None

        self.left_margin = 150
        self.canvas_horizontal_padding = 36
        self.canvas_top_margin = 18
        self.scope_y = 20
        self.scope_gap = 8
        self.min_circuit_height = 220
        self.min_scope_height = 280
        self.min_view_width = 760
        self.default_cycle_width = 28
        self.cycle_width = self.default_cycle_width
        self.row_height = 34
        self.min_row_band = 11
        self.high_offset = 18
        self.low_offset = 4
        self.circuit_pin_spacing = 12
        self.circuit_margin_x = 36
        self.circuit_margin_top = 46
        self.circuit_margin_bottom = 24
        self.trace_colours = [
            (0.20, 0.23, 0.78),
            (0.16, 0.50, 0.26),
            (0.70, 0.22, 0.22),
            (0.57, 0.31, 0.70),
            (0.10, 0.55, 0.62),
            (0.72, 0.43, 0.12),
        ]
        self.colour_blind_trace_colours = [
            (0.00, 0.45, 0.70),
            (0.90, 0.62, 0.00),
            (0.00, 0.62, 0.45),
            (0.80, 0.47, 0.65),
            (0.34, 0.71, 0.91),
            (0.84, 0.37, 0.00),
            (0.94, 0.89, 0.26),
        ]

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.on_mouse)

    def set_translator(self, translator):
        """Set the function used for canvas UI text."""
        self.translator = translator
        self.Refresh()

    def text(self, key):
        """Return translated canvas text."""
        translator = getattr(self, "translator", None)
        if translator is None:
            return translate(load_translations(), DEFAULT_LANGUAGE, key)
        return translator(key)

    def reset_view(self):
        """Reset pan, zoom, and oscilloscope scroll to their defaults."""
        self.pan_x = 0
        self.pan_y = 0
        self.zoom = 1.0
        self.circuit_scroll_x = 0
        self.circuit_scroll_y = 0
        self.circuit_zoom = 1.0
        self.scope_cycle_zoom = 1.0
        self.scope_row_zoom = 1.0
        self.circuit_drag_mode = None
        self.scope_first_cycle = 0
        self.scope_first_row = 0
        self.scope_drag_mode = None
        self.follow_latest_cycles = False
        self.view_mode = "split"
        self.reset_3d_trace_view()
        self.reset_circuit_3d_view()
        self.init = False
        self.Refresh()

    def set_trace_display_3d(self, enabled):
        """Switch between conventional 2D and perspective 3D traces."""
        self.trace_display_3d = bool(enabled)
        self.trace_3d_drag_active = False
        self.init = False
        self.Refresh()

    def set_circuit_display_3d(self, enabled):
        """Switch the circuit overview between 2D and 3D perspective."""
        self.circuit_display_3d = bool(enabled)
        self.circuit_3d_drag_active = False
        self.init = False
        self.Refresh()

    def reset_circuit_3d_view(self):
        """Restore the 3D circuit camera to a readable default angle."""
        self.circuit_3d_rotate_x = 34.0
        self.circuit_3d_rotate_y = -40.0
        self.circuit_3d_pan_x = 0.0
        self.circuit_3d_pan_y = 0.0
        self.circuit_3d_zoom = 1.0
        self.circuit_3d_drag_active = False

    def set_view_mode(self, mode):
        """Show both views split, or maximise the circuit or oscilloscope."""
        if mode not in ("split", "circuit", "scope"):
            mode = "split"
        self.view_mode = mode
        self.init = False
        self.Refresh()

    def reset_3d_trace_view(self):
        """Restore the 3D trace camera to a readable default view."""
        self.trace_3d_rotate_x = 28.0
        self.trace_3d_rotate_y = -34.0
        self.trace_3d_pan_x = 0.0
        self.trace_3d_pan_y = -4.0
        self.trace_3d_zoom = 1.0
        self.trace_3d_drag_active = False

    def minimum_visual_size(self):
        """Return the minimum canvas size that keeps both views readable."""
        min_width = self.min_view_width + self.canvas_horizontal_padding
        min_height = (
            self.scope_y + self.min_scope_height + self.scope_gap
            + self.min_circuit_height + self.canvas_top_margin
        )
        return min_width, min_height

    def zoom_circuit(self, factor):
        """Zoom the circuit overview around its current scroll position."""
        old_zoom = self.circuit_zoom
        self.circuit_zoom = self.clamp(self.circuit_zoom * factor, 0.1, 3.0)
        if self.circuit_zoom != old_zoom:
            self.circuit_scroll_x *= self.circuit_zoom / old_zoom
            self.circuit_scroll_y *= self.circuit_zoom / old_zoom
        self.Refresh()

    def zoom_circuit_at(self, factor, cursor_x, cursor_y):
        """Zoom the circuit toward the cursor so it stays under the mouse."""
        view = self.circuit_geometry.get("view")
        content = getattr(self, "last_circuit_content", None)
        if not view or not content:
            self.zoom_circuit(factor)
            return
        old_zoom = self.circuit_zoom
        new_zoom = self.clamp(old_zoom * factor, 0.1, 3.0)
        if new_zoom == old_zoom:
            return
        view_x, view_y, view_width, view_height = view
        base_width, base_height = content
        origin_x = view_x - self.circuit_scroll_x
        origin_y = (
            view_y + view_height - base_height * old_zoom
            + self.circuit_scroll_y
        )
        base_x = (cursor_x - origin_x) / old_zoom
        base_y = (cursor_y - origin_y) / old_zoom

        self.circuit_zoom = new_zoom
        self.circuit_scroll_x = self.clamp(
            view_x + base_x * new_zoom - cursor_x,
            0, max(base_width * new_zoom - view_width, 0)
        )
        scroll_y = (
            cursor_y - view_y - view_height
            + (base_height - base_y) * new_zoom
        )
        self.circuit_scroll_y = self.clamp(
            scroll_y, 0, max(base_height * new_zoom - view_height, 0)
        )
        self.Refresh()

    def zoom_circuit_3d_at(self, factor, cursor_x, cursor_y):
        """Zoom the 3D circuit toward the cursor under the mouse."""
        old_zoom = self.circuit_3d_zoom
        new_zoom = self.clamp(old_zoom * factor, 0.3, 3.5)
        if new_zoom != old_zoom:
            shift_x, shift_y = self.circuit_3d_zoom_pan_shift(
                old_zoom, new_zoom, cursor_x, cursor_y
            )
            self.circuit_3d_pan_x += shift_x
            self.circuit_3d_pan_y += shift_y
            self.circuit_3d_zoom = new_zoom
        self.Refresh()

    def circuit_3d_zoom_pan_shift(self, old_zoom, new_zoom,
                                  cursor_x, cursor_y):
        """Return the pan shift that keeps the cursor point fixed when zooming.

        Zooming changes the camera distance, which would otherwise slide the
        world point under the mouse across the screen; this shift cancels that
        slide so the 3D circuit zooms toward the cursor exactly as the 2D
        overview does.
        """
        geometry = self.circuit_geometry
        viewport = geometry.get("viewport")
        old_distance = geometry.get("camera_distance")
        if not viewport or not old_distance:
            return 0.0, 0.0
        view_x, view_y, view_width, view_height = viewport
        if view_width <= 0 or view_height <= 0:
            return 0.0, 0.0
        new_distance = (
            old_distance * max(old_zoom, 0.2) / max(new_zoom, 0.2)
        )
        distance_delta = new_distance - old_distance
        tan_y = math.tan(math.radians(geometry.get("fov_y", 40.0) / 2.0))
        tan_x = tan_y * (view_width / max(view_height, 1))
        ndc_x = 2.0 * (cursor_x - view_x) / view_width - 1.0
        ndc_y = 2.0 * (cursor_y - view_y) / view_height - 1.0
        return (ndc_x * tan_x * distance_delta,
                ndc_y * tan_y * distance_delta)

    def fit_circuit(self):
        """Fit the whole circuit into the view (2D), or re-frame it (3D)."""
        if self.circuit_display_3d:
            self.reset_circuit_3d_view()
            self.Refresh()
            return
        view = getattr(self, "last_circuit_view", None)
        content = getattr(self, "last_circuit_content", None)
        if view and content and content[0] > 0 and content[1] > 0:
            self.circuit_zoom = self.clamp(
                min(view[0] / content[0], view[1] / content[1]) * 0.97,
                0.08, 1.0
            )
        else:
            self.circuit_zoom = 0.45
        self.circuit_scroll_x = 0
        self.circuit_scroll_y = 0
        self.Refresh()

    def zoom_scope(self, factor):
        """Zoom the oscilloscope time axis in or out."""
        self.scope_cycle_zoom = self.clamp(
            self.scope_cycle_zoom * factor, 0.1, 4.0
        )
        self.follow_latest_cycles = False
        if self.trace_display_3d:
            self.trace_3d_zoom = self.clamp(
                self.trace_3d_zoom * factor, 0.25, 4.0
            )
        self.Refresh()

    def zoom_scope_rows(self, factor):
        """Zoom the oscilloscope vertically to show fewer or more signals."""
        self.scope_row_zoom = self.clamp(
            self.scope_row_zoom * factor, 0.2, 3.0
        )
        self.Refresh()

    def fit_scope(self):
        """Frame the whole oscilloscope so all of it is visible at once."""
        self.scope_first_cycle = 0
        self.scope_first_row = 0
        self.follow_latest_cycles = False
        self.scope_row_zoom = self.fit_row_zoom()
        if self.trace_display_3d:
            # Hundreds of blocks are never legible in 3D, so reset to a
            # readable time window and re-frame the perspective camera.
            self.scope_cycle_zoom = 1.0
            self.reset_3d_trace_view()
            self.Refresh()
            return
        monitor_items = list(self.monitors.monitors_dictionary.items())
        max_cycles = self.max_recorded_cycles(monitor_items)
        plot_width = getattr(self, "last_scope_plot_width", 0)
        if max_cycles > 0 and plot_width > 0:
            target_cycle_width = plot_width / max_cycles
            self.scope_cycle_zoom = self.clamp(
                target_cycle_width / self.default_cycle_width, 0.02, 1.0
            )
        else:
            self.scope_cycle_zoom = 0.25
        self.Refresh()

    def fit_row_zoom(self):
        """Return the vertical zoom that fits every monitor row on screen."""
        total_rows = len(self.monitors.monitors_dictionary)
        plot_height = getattr(self, "last_scope_plot_height", 0)
        if total_rows <= 0 or plot_height <= 0:
            return 1.0
        return self.clamp(
            plot_height / (self.row_height * total_rows), 0.2, 1.0
        )

    def set_dark_mode(self, enabled):
        """Apply dark or light drawing colours to the canvas."""
        self.dark_mode = enabled
        self.init = False
        self.Refresh()

    def set_colour_blind_mode(self, enabled):
        """Apply colour-blind-safe signal colours to the canvas."""
        self.colour_blind_mode = enabled
        self.Refresh()

    def theme_colour(self, key):
        """Return an OpenGL colour from the current canvas theme."""
        light_colours = {
            "canvas_bg": (0.96, 0.97, 0.98),
            "grid": (0.90, 0.92, 0.94),
            "text": (0.02, 0.03, 0.04),
            "subtle_text": (0.34, 0.39, 0.47),
            "circuit_bg": (0.98, 0.98, 0.95),
            "circuit_border": (0.70, 0.70, 0.62),
            "device_border": (0.38, 0.42, 0.48),
            "switch_fill": (1.00, 0.96, 0.76),
            "clock_fill": (0.80, 0.94, 0.82),
            "dtype_fill": (0.83, 0.91, 1.00),
            "gate_fill": (0.95, 0.95, 1.00),
            "scope_bg": (0.78, 0.78, 0.78),
            "scope_border": (0.36, 0.36, 0.38),
            "scope_header": (0.70, 0.80, 0.91),
            "scope_header_border": (0.48, 0.48, 0.52),
            "scope_icon": (0.82, 0.90, 0.98),
            "scope_icon_border": (0.35, 0.48, 0.64),
            "grid_major": (0.70, 0.70, 0.74),
            "grid_minor": (0.86, 0.86, 0.88),
            "grid_row": (0.90, 0.90, 0.91),
            "level_mark": (0.82, 0.82, 0.84),
            "level_guide": (0.92, 0.92, 0.93),
            "scrollbar_track": (0.88, 0.88, 0.88),
            "scrollbar_step": (0.86, 0.86, 0.86),
            "scrollbar_border": (0.62, 0.62, 0.64),
            "scrollbar_thumb": (0.72, 0.72, 0.74),
            "scrollbar_arrow": (0.26, 0.26, 0.28),
            "axis": (0.22, 0.22, 0.24),
            "blank_signal": (0.70, 0.70, 0.70),
            "pin_border": (0.24, 0.24, 0.24),
        }
        dark_colours = {
            "canvas_bg": (0.08, 0.10, 0.13),
            "grid": (0.16, 0.19, 0.24),
            "text": (0.90, 0.93, 0.96),
            "subtle_text": (0.66, 0.72, 0.80),
            "circuit_bg": (0.13, 0.15, 0.18),
            "circuit_border": (0.34, 0.39, 0.46),
            "device_border": (0.55, 0.61, 0.70),
            "switch_fill": (0.30, 0.27, 0.12),
            "clock_fill": (0.12, 0.27, 0.18),
            "dtype_fill": (0.13, 0.22, 0.34),
            "gate_fill": (0.19, 0.20, 0.29),
            "scope_bg": (0.16, 0.18, 0.21),
            "scope_border": (0.43, 0.48, 0.56),
            "scope_header": (0.18, 0.28, 0.39),
            "scope_header_border": (0.42, 0.51, 0.62),
            "scope_icon": (0.20, 0.31, 0.43),
            "scope_icon_border": (0.55, 0.67, 0.82),
            "grid_major": (0.35, 0.40, 0.48),
            "grid_minor": (0.25, 0.29, 0.35),
            "grid_row": (0.23, 0.27, 0.32),
            "level_mark": (0.44, 0.49, 0.57),
            "level_guide": (0.28, 0.32, 0.38),
            "scrollbar_track": (0.24, 0.27, 0.32),
            "scrollbar_step": (0.20, 0.23, 0.28),
            "scrollbar_border": (0.46, 0.51, 0.58),
            "scrollbar_thumb": (0.46, 0.50, 0.58),
            "scrollbar_arrow": (0.82, 0.86, 0.90),
            "axis": (0.86, 0.89, 0.92),
            "blank_signal": (0.56, 0.60, 0.66),
            "pin_border": (0.78, 0.82, 0.88),
        }
        colours = dark_colours if self.dark_mode else light_colours
        return colours[key]

    def init_gl(self):
        """Configure the OpenGL projection for the current canvas size."""
        size = self.GetClientSize()
        self.SetCurrent(self.context)
        GL.glDrawBuffer(GL.GL_BACK)
        GL.glClearColor(*self.theme_colour("canvas_bg"), 0.0)
        self.configure_2d_projection(size)

    def configure_2d_projection(self, size):
        """Configure canvas-space orthographic drawing."""
        GL.glViewport(0, 0, size.width, size.height)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_LIGHTING)
        GL.glDisable(GL.GL_SCISSOR_TEST)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glOrtho(0, size.width, 0, size.height, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glTranslated(self.pan_x, self.pan_y, 0.0)
        GL.glScaled(self.zoom, self.zoom, self.zoom)

    def render(self, swap=True):
        """Draw the circuit overview and oscilloscope-style traces."""
        self.SetCurrent(self.context)
        if not self.init:
            self.init_gl()
            self.init = True

        size = self.GetClientSize()
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glLineWidth(1.0)

        monitor_items = list(self.monitors.monitors_dictionary.items())
        circuit_bounds, scope_bounds = self.calculate_display_bounds(size)

        self.draw_canvas_grid(size)
        if circuit_bounds is not None:
            self.last_circuit_bounds = circuit_bounds
            self.draw_circuit_overview(circuit_bounds)
        if scope_bounds is not None:
            if self.trace_display_3d:
                self.draw_3d_oscilloscope(scope_bounds, monitor_items)
            else:
                self.draw_oscilloscope(scope_bounds, monitor_items)
        self.finish_render(swap)

    def calculate_display_bounds(self, size):
        """Return circuit and oscilloscope bounds for the active view mode."""
        available_width = max(1, size.width - self.canvas_horizontal_padding)
        view_mode = getattr(self, "view_mode", "split")

        if view_mode == "circuit":
            return self.maximised_view_bounds(size, available_width), None
        if view_mode == "scope":
            return None, self.maximised_view_bounds(size, available_width)
        return self.split_view_bounds(size, available_width)

    def maximised_view_bounds(self, size, available_width):
        """Return bounds that fill the canvas for a single maximised view."""
        height = max(
            self.min_scope_height,
            size.height - self.canvas_top_margin - self.scope_y,
        )
        return (18, self.scope_y, available_width, height)

    def split_view_bounds(self, size, available_width):
        """Split the canvas so the oscilloscope fills the lower region.

        The circuit overview is kept only as tall as its contents need so
        the oscilloscope grows to use the remaining vertical space instead
        of sitting in a short strip at the bottom of the window.
        """
        available = (
            size.height - self.canvas_top_margin - self.scope_y
            - self.scope_gap
        )
        available = max(
            available, self.min_circuit_height + self.min_scope_height
        )
        desired_circuit_height = max(
            self.estimate_circuit_height(), self.min_circuit_height
        )
        circuit_cap = max(
            self.min_circuit_height,
            min(available - self.min_scope_height, int(available * 0.45)),
        )
        circuit_height = max(
            self.min_circuit_height,
            min(desired_circuit_height, circuit_cap),
        )
        scope_height = max(self.min_scope_height, available - circuit_height)

        scope_bounds = (18, self.scope_y, available_width, scope_height)
        circuit_y = self.scope_y + scope_height + self.scope_gap
        circuit_bounds = (18, circuit_y, available_width, circuit_height)
        return circuit_bounds, scope_bounds

    def finish_render(self, swap=True):
        """Flush drawing commands and optionally swap buffers."""
        GL.glFlush()
        if swap:
            self.SwapBuffers()

    def save_circuit_image(self, path):
        """Save the currently displayed circuit overview."""
        return self.save_region_image(path, self.last_circuit_bounds)

    def save_scope_image(self, path):
        """Save the currently displayed oscilloscope."""
        return self.save_region_image(path, self.last_scope_bounds)

    def save_region_image(self, path, bounds):
        """Save part of the canvas as a PNG image or one-page PDF."""
        self.render(swap=False)
        try:
            if bounds is None:
                return False

            x_pos, y_pos, width, height = bounds
            size = self.GetClientSize()
            x_pos = x_pos * self.zoom + self.pan_x
            y_pos = y_pos * self.zoom + self.pan_y
            width = width * self.zoom
            height = height * self.zoom
            x_pos = max(0, int(round(x_pos)))
            y_pos = max(0, int(round(y_pos)))
            width = min(int(round(width)), size.width - x_pos)
            height = min(int(round(height)), size.height - y_pos)
            if width <= 0 or height <= 0:
                return False

            GL.glReadBuffer(GL.GL_BACK)
            GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, 1)
            GL.glFinish()
            pixels = GL.glReadPixels(
                x_pos, y_pos, width, height, GL.GL_RGB, GL.GL_UNSIGNED_BYTE
            )
            row_length = width * 3
            pixel_data = bytes(pixels)
            image_data = b"".join(
                pixel_data[row * row_length:(row + 1) * row_length]
                for row in range(height - 1, -1, -1)
            )

            if path.lower().endswith(".pdf"):
                self.write_image_pdf(path, width, height, image_data)
                return True

            image = wx.Image(width, height)
            image.SetData(image_data)
            return image.SaveFile(path, wx.BITMAP_TYPE_PNG)
        finally:
            self.SwapBuffers()

    def write_image_pdf(self, path, image_width, image_height, image_data):
        """Write RGB image data to a one-page PDF."""
        if image_width >= image_height:
            page_width, page_height = 842, 595
        else:
            page_width, page_height = 595, 842

        margin = 36
        scale = min(
            (page_width - 2 * margin) / image_width,
            (page_height - 2 * margin) / image_height,
        )
        draw_width = image_width * scale
        draw_height = image_height * scale
        draw_x = (page_width - draw_width) / 2
        draw_y = (page_height - draw_height) / 2

        compressed_image = zlib.compress(image_data)
        content = (
            "q\n"
            + self.pdf_number(draw_width) + " 0 0 "
            + self.pdf_number(draw_height) + " "
            + self.pdf_number(draw_x) + " "
            + self.pdf_number(draw_y) + " cm\n"
            + "/Im0 Do\nQ\n"
        ).encode("ascii")

        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
                + str(page_width) + " " + str(page_height)
                + "] /Resources << /XObject << /Im0 4 0 R >> >> "
                + "/Contents 5 0 R >>"
            ).encode("ascii"),
            (
                "<< /Type /XObject /Subtype /Image /Width "
                + str(image_width) + " /Height " + str(image_height)
                + " /ColorSpace /DeviceRGB /BitsPerComponent 8 "
                + "/Filter /FlateDecode /Length "
                + str(len(compressed_image)) + " >>\nstream\n"
            ).encode("ascii") + compressed_image + b"\nendstream",
            (
                "<< /Length " + str(len(content)) + " >>\nstream\n"
            ).encode("ascii") + content + b"endstream",
        ]

        pdf_data = self.build_pdf(objects)
        with open(path, "wb") as pdf_file:
            pdf_file.write(pdf_data)

    def build_pdf(self, objects):
        """Build a minimal PDF from encoded object bodies."""
        pdf_data = b"%PDF-1.4\n"
        offsets = []
        for index, body in enumerate(objects, start=1):
            offsets.append(len(pdf_data))
            pdf_data += (
                str(index).encode("ascii") + b" 0 obj\n"
                + body + b"\nendobj\n"
            )

        xref_offset = len(pdf_data)
        pdf_data += (
            b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n"
            + b"0000000000 65535 f \n"
        )
        for offset in offsets:
            pdf_data += (
                str(offset).zfill(10).encode("ascii") + b" 00000 n \n"
            )
        pdf_data += (
            b"trailer\n<< /Size "
            + str(len(objects) + 1).encode("ascii")
            + b" /Root 1 0 R >>\nstartxref\n"
            + str(xref_offset).encode("ascii") + b"\n%%EOF\n"
        )
        return pdf_data

    def pdf_number(self, value):
        """Return a compact PDF numeric literal."""
        return ("%.2f" % value).rstrip("0").rstrip(".")

    def draw_canvas_grid(self, size):
        """Draw a faint simulator-style workspace grid."""
        self.set_colour(*self.theme_colour("grid"))
        GL.glBegin(GL.GL_LINES)
        for x_pos in range(0, size.width + 1, 24):
            GL.glVertex2f(x_pos, 0)
            GL.glVertex2f(x_pos, size.height)
        for y_pos in range(0, size.height + 1, 24):
            GL.glVertex2f(0, y_pos)
            GL.glVertex2f(size.width, y_pos)
        GL.glEnd()

    def draw_circuit_overview(self, bounds):
        """Draw a compact block diagram of the parsed circuit."""
        x_pos, y_pos, width, height = bounds
        self.draw_rectangle(
            bounds,
            self.theme_colour("circuit_bg"),
            self.theme_colour("circuit_border"),
        )
        self.render_text(
            self.text("circuit_overview"), x_pos + 10, y_pos + height - 20
        )

        view_bounds = (x_pos + 10, y_pos + 26, width - 32, height - 64)
        view_x, view_y, view_width, view_height = view_bounds
        if view_width <= 0 or view_height <= 0:
            return

        if self.circuit_display_3d:
            self.circuit_geometry = {"view": view_bounds, "mode": "3d"}
            self.draw_3d_circuit(view_bounds)
            self.draw_circuit_scrollbars(view_bounds)
            return

        base_content_width, base_content_height = self.circuit_content_size(
            view_width, view_height
        )
        self.last_circuit_view = (view_width, view_height)
        self.last_circuit_content = (base_content_width, base_content_height)
        circuit_zoom = getattr(self, "circuit_zoom", 1.0)
        content_width = base_content_width * circuit_zoom
        content_height = base_content_height * circuit_zoom
        max_scroll_x = max(content_width - view_width, 0)
        max_scroll_y = max(content_height - view_height, 0)
        self.circuit_scroll_x = self.clamp(
            self.circuit_scroll_x, 0, max_scroll_x
        )
        self.circuit_scroll_y = self.clamp(
            self.circuit_scroll_y, 0, max_scroll_y
        )
        content_origin_x = view_x - self.circuit_scroll_x
        content_origin_y = (
            view_y + view_height - content_height + self.circuit_scroll_y
        )
        self.circuit_geometry = {
            "view": view_bounds,
            "content_width": content_width,
            "content_height": content_height,
            "max_scroll_x": max_scroll_x,
            "max_scroll_y": max_scroll_y,
        }

        self.begin_scissor(view_bounds)
        GL.glPushMatrix()
        GL.glTranslated(content_origin_x, content_origin_y, 0.0)
        GL.glScaled(circuit_zoom, circuit_zoom, 1.0)
        positions = self.build_device_positions(
            (0, 0, base_content_width, base_content_height)
        )
        self.draw_connections(positions)

        for device in self.devices.devices_list:
            if device.device_id in positions:
                self.draw_device_node(device, positions[device.device_id])
        GL.glPopMatrix()
        self.end_scissor()
        self.draw_circuit_scrollbars(view_bounds)

    def draw_3d_circuit(self, view_bounds):
        """Render the circuit as 3D blocks whose height shows live state.

        Each device becomes a coloured tower (colour = device type, height =
        its current output level), and connections are drawn as raised wires
        across the floor.  The view can be rotated and zoomed with the mouse,
        which makes the data-flow depth and the live signal levels easy to
        read at a glance.
        """
        self.draw_rectangle(
            view_bounds,
            self.theme_colour("circuit_bg"),
            self.theme_colour("circuit_border"),
        )
        viewport = self.canvas_pixel_rect(view_bounds)
        if viewport is None:
            return
        content_width, content_height = self.circuit_content_size(
            view_bounds[2], view_bounds[3]
        )
        positions = self.build_device_positions(
            (0, 0, content_width, content_height)
        )
        if not positions:
            return

        layout = self.circuit_3d_layout(positions)
        grid = getattr(self, "circuit_grid", None)
        wire_paths = self.circuit_wire_paths(positions, grid) if grid else []
        size = self.GetClientSize()
        x_pos, y_pos, width, height = viewport
        wire_top = self.circuit_3d_wire_top(len(wire_paths))
        camera_distance, far_plane = self.fit_3d_camera_distance(
            width, height, layout["span_x"], layout["span_z"], 40.0,
            self.circuit_3d_rotate_x, self.circuit_3d_rotate_y,
            self.circuit_3d_zoom, half_height=max(32.0, wire_top + 8.0),
            fov_y=40.0
        )
        self.store_circuit_3d_geometry(
            (x_pos, y_pos, width, height), camera_distance, layout
        )
        try:
            GL.glViewport(x_pos, y_pos, width, height)
            GL.glEnable(GL.GL_SCISSOR_TEST)
            GL.glScissor(x_pos, y_pos, width, height)
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glDepthFunc(GL.GL_LEQUAL)
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glLoadIdentity()
            GLU.gluPerspective(40.0, width / max(height, 1), 1.0, far_plane)
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glLoadIdentity()
            GL.glTranslatef(
                self.circuit_3d_pan_x, -10.0 + self.circuit_3d_pan_y,
                -camera_distance,
            )
            GL.glRotatef(self.circuit_3d_rotate_x, 1.0, 0.0, 0.0)
            GL.glRotatef(self.circuit_3d_rotate_y, 0.0, 1.0, 0.0)
            self.configure_3d_lighting()
            self.draw_3d_circuit_floor(layout)
            self.draw_3d_circuit_wires(layout, wire_paths)
            self.draw_3d_circuit_blocks(layout)
            self.draw_3d_circuit_pins(layout, positions)
        finally:
            GL.glLineWidth(1.0)
            self.configure_2d_projection(size)
        self.draw_3d_axis_gizmo(
            view_bounds[0] + 40, view_bounds[1] + 42, 24,
            self.circuit_3d_rotate_x, self.circuit_3d_rotate_y
        )

    def store_circuit_3d_geometry(self, viewport, camera_distance, layout):
        """Record 3D camera framing for zoom-to-cursor and the scrollbars."""
        view_x, view_y, view_width, view_height = viewport
        fov_y = 40.0
        tan_y = math.tan(math.radians(fov_y / 2.0))
        tan_x = tan_y * (view_width / max(view_height, 1))
        visible_x = 2.0 * camera_distance * tan_x
        visible_y = 2.0 * camera_distance * tan_y
        pan_extent_x = max(layout["span_x"], 1.0)
        pan_extent_y = max(layout["span_z"], 60.0)
        self.circuit_geometry.update({
            "mode": "3d",
            "viewport": viewport,
            "camera_distance": camera_distance,
            "fov_y": fov_y,
            "visible_x": visible_x,
            "visible_y": visible_y,
            "content_x": pan_extent_x + visible_x,
            "content_y": pan_extent_y + visible_y,
            "max_pan_x": pan_extent_x / 2.0,
            "max_pan_y": pan_extent_y / 2.0,
        })

    def circuit_3d_layout(self, positions):
        """Return centred 3D coordinates for the blocks and their wires."""
        centres = {}
        for device_id, (px, py, pw, ph) in positions.items():
            centres[device_id] = (px + pw / 2, py + ph / 2, pw)
        xs = [centre[0] for centre in centres.values()]
        zs = [centre[1] for centre in centres.values()]
        mid_x = (min(xs) + max(xs)) / 2
        mid_z = (min(zs) + max(zs)) / 2
        scale = 0.6

        blocks = {}
        for device_id, (cxp, cyp, pw) in centres.items():
            blocks[device_id] = (
                (cxp - mid_x) * scale,
                -(cyp - mid_z) * scale,
                max(pw * scale / 2, 16.0),
            )
        return {
            "blocks": blocks,
            "mid_x": mid_x,
            "mid_z": mid_z,
            "scale": scale,
            "span_x": max((max(xs) - min(xs)) * scale, 1.0),
            "span_z": max((max(zs) - min(zs)) * scale, 1.0),
        }

    def circuit_block_height_3d(self, device):
        """Return a 3D tower height that reflects the device output level."""
        output_ids = self.sorted_port_ids(device.outputs)
        if output_ids:
            signal = device.outputs.get(output_ids[0])
            if signal in (self.devices.HIGH, self.devices.RISING):
                return 62.0
            if signal in (self.devices.LOW, self.devices.FALLING):
                return 18.0
        return 34.0

    def draw_3d_circuit_floor(self, layout):
        """Draw the floor plane and grid beneath the 3D circuit blocks."""
        half_x = layout["span_x"] / 2 + 50
        half_z = layout["span_z"] / 2 + 50
        GL.glDisable(GL.GL_LIGHTING)
        self.set_colour(*self.theme_colour("grid_minor"))
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(-half_x, -0.4, half_z)
        GL.glVertex3f(half_x, -0.4, half_z)
        GL.glVertex3f(half_x, -0.4, -half_z)
        GL.glVertex3f(-half_x, -0.4, -half_z)
        GL.glEnd()

        self.set_colour(*self.theme_colour("grid_row"))
        GL.glLineWidth(1.0)
        GL.glBegin(GL.GL_LINES)
        line_x = -half_x
        while line_x <= half_x:
            GL.glVertex3f(line_x, 0.0, -half_z)
            GL.glVertex3f(line_x, 0.0, half_z)
            line_x += 60.0
        line_z = -half_z
        while line_z <= half_z:
            GL.glVertex3f(-half_x, 0.0, line_z)
            GL.glVertex3f(half_x, 0.0, line_z)
            line_z += 60.0
        GL.glEnd()

    def draw_3d_circuit_wires(self, layout, paths):
        """Draw the orthogonal 2D routes as raised conduits on the 3D floor.

        Reusing the 2D router gives the 3D wires the same per-wire lanes and
        the same distinct input-pin connections, and lifting each wire to its
        own height means wires that would cross on the floor pass cleanly over
        one another in 3D instead of overlapping.
        """
        if not paths:
            return
        mid_x = layout["mid_x"]
        mid_z = layout["mid_z"]
        scale = layout["scale"]
        pin_y = 4.5
        count = len(paths)
        for index, (points, signal) in enumerate(paths):
            self.set_colour(*self.signal_colour(signal))
            floor = [
                ((point_x - mid_x) * scale, -(point_y - mid_z) * scale)
                for point_x, point_y in points
            ]
            height = self.circuit_3d_wire_height(index, count)
            route = [(floor[0][0], pin_y, floor[0][1])]
            route += [(fx, height, fz) for fx, fz in floor]
            route.append((floor[-1][0], pin_y, floor[-1][1]))
            for start, end in zip(route, route[1:]):
                self.draw_3d_wire_segment(start, end)

    def circuit_3d_wire_height(self, index, count):
        """Return the lifted height for one of ``count`` 3D wires.

        Spreading the wires evenly across a bounded height band keeps a clear
        gap between them, so wires that cross on the floor pass over each
        other in 3D rather than overlapping; the gap never drops below the
        wire thickness so the separation always holds.
        """
        if count <= 1:
            return self.circuit_3d_wire_base
        step = self.clamp(self.circuit_3d_wire_band / (count - 1), 4.5, 14.0)
        return self.circuit_3d_wire_base + index * step

    def circuit_3d_wire_top(self, count):
        """Return the height of the highest 3D wire, for camera framing."""
        if count <= 0:
            return self.circuit_3d_wire_base
        return self.circuit_3d_wire_height(count - 1, count)

    def draw_3d_wire_segment(self, start, end):
        """Draw one axis-aligned wire segment as a thin solid bar in 3D."""
        half = 1.3
        x_lo, x_hi = sorted((start[0], end[0]))
        y_lo, y_hi = sorted((start[1], end[1]))
        z_lo, z_hi = sorted((start[2], end[2]))
        self.draw_3d_box(x_lo - half, x_hi + half, y_lo - half, y_hi + half,
                         z_lo - half, z_hi + half)

    def draw_3d_box(self, x_lo, x_hi, y_lo, y_hi, z_lo, z_hi):
        """Draw a lit axis-aligned box spanning the given extents."""
        GL.glEnable(GL.GL_LIGHTING)
        GL.glBegin(GL.GL_QUADS)
        GL.glNormal3f(0.0, -1.0, 0.0)
        GL.glVertex3f(x_lo, y_lo, z_lo)
        GL.glVertex3f(x_hi, y_lo, z_lo)
        GL.glVertex3f(x_hi, y_lo, z_hi)
        GL.glVertex3f(x_lo, y_lo, z_hi)
        GL.glNormal3f(0.0, 1.0, 0.0)
        GL.glVertex3f(x_lo, y_hi, z_hi)
        GL.glVertex3f(x_hi, y_hi, z_hi)
        GL.glVertex3f(x_hi, y_hi, z_lo)
        GL.glVertex3f(x_lo, y_hi, z_lo)
        GL.glNormal3f(-1.0, 0.0, 0.0)
        GL.glVertex3f(x_lo, y_lo, z_hi)
        GL.glVertex3f(x_lo, y_hi, z_hi)
        GL.glVertex3f(x_lo, y_hi, z_lo)
        GL.glVertex3f(x_lo, y_lo, z_lo)
        GL.glNormal3f(1.0, 0.0, 0.0)
        GL.glVertex3f(x_hi, y_lo, z_lo)
        GL.glVertex3f(x_hi, y_hi, z_lo)
        GL.glVertex3f(x_hi, y_hi, z_hi)
        GL.glVertex3f(x_hi, y_lo, z_hi)
        GL.glNormal3f(0.0, 0.0, -1.0)
        GL.glVertex3f(x_lo, y_lo, z_lo)
        GL.glVertex3f(x_lo, y_hi, z_lo)
        GL.glVertex3f(x_hi, y_hi, z_lo)
        GL.glVertex3f(x_hi, y_lo, z_lo)
        GL.glNormal3f(0.0, 0.0, 1.0)
        GL.glVertex3f(x_hi, y_lo, z_hi)
        GL.glVertex3f(x_hi, y_hi, z_hi)
        GL.glVertex3f(x_lo, y_hi, z_hi)
        GL.glVertex3f(x_lo, y_lo, z_hi)
        GL.glEnd()

    def draw_3d_circuit_pins(self, layout, positions):
        """Draw spheres at every input and output pin, as in the 2D view."""
        mid_x = layout["mid_x"]
        mid_z = layout["mid_z"]
        scale = layout["scale"]
        pin_y = 4.5
        quadric = GLU.gluNewQuadric()
        GL.glEnable(GL.GL_LIGHTING)
        for device in self.devices.devices_list:
            position = positions.get(device.device_id)
            if position is None:
                continue
            for input_id in self.sorted_port_ids(device.inputs):
                pin_x, pin_z = self.input_pin(position, device, input_id)
                self.set_colour(0.97, 0.97, 0.99)
                self.draw_3d_sphere(quadric, (pin_x - mid_x) * scale, pin_y,
                                    -(pin_z - mid_z) * scale, 3.0)
            for output_id in self.sorted_port_ids(device.outputs):
                pin_x, pin_z = self.output_pin(position, device, output_id)
                signal = device.outputs.get(output_id)
                self.set_colour(*self.signal_colour(signal))
                self.draw_3d_sphere(quadric, (pin_x - mid_x) * scale, pin_y,
                                    -(pin_z - mid_z) * scale, 4.2)
        GLU.gluDeleteQuadric(quadric)

    def draw_3d_sphere(self, quadric, x_pos, y_pos, z_pos, radius):
        """Draw a lit sphere of the current colour at a 3D point."""
        GL.glPushMatrix()
        GL.glTranslatef(x_pos, y_pos, z_pos)
        GLU.gluSphere(quadric, radius, 12, 8)
        GL.glPopMatrix()

    def draw_3d_circuit_blocks(self, layout):
        """Draw each device as a coloured 3D block sized by its signal."""
        half_depth = 16.0
        for device in self.devices.devices_list:
            block = layout["blocks"].get(device.device_id)
            if block is None:
                continue
            block_x, block_z, half_width = block
            height = self.circuit_block_height_3d(device)
            self.set_colour(*self.device_fill_colour(device))
            self.draw_3d_cuboid(block_x, block_z, half_width, half_depth,
                                height)
            self.draw_3d_circuit_label(device, block_x, block_z, half_width,
                                       half_depth, height)

    def draw_3d_circuit_label(self, device, block_x, block_z, half_width,
                              half_depth, height):
        """Draw a device name laid flat on top of its 3D block."""
        name = str(self.devices.names.get_name_string(device.device_id))
        font = GLUT.GLUT_STROKE_ROMAN
        width_units = sum(
            GLUT.glutStrokeWidth(font, ord(character)) for character in name
        ) or 1.0
        scale = min((half_width * 2 - 6) / width_units, 0.13)
        GL.glDisable(GL.GL_LIGHTING)
        self.set_colour(*self.theme_colour("text"))
        GL.glPushMatrix()
        GL.glTranslatef(block_x - half_width + 4, height + 0.5,
                        block_z + half_depth - 4)
        GL.glRotatef(-90.0, 1.0, 0.0, 0.0)
        GL.glScalef(scale, scale, scale)
        GL.glLineWidth(1.0)
        for character in name:
            GLUT.glutStrokeCharacter(font, ord(character))
        GL.glPopMatrix()

    def circuit_metrics(self):
        """Return shared sizing for circuit layout and routing.

        Devices share a single set of rows across every column so the gaps
        between rows form clear horizontal routing corridors, and uniform
        column pitches leave clear vertical channels between columns.
        """
        layers = self.calculate_device_layers()
        groups = {}
        for device in self.devices.devices_list:
            groups.setdefault(layers.get(device.device_id, 1), []).append(
                device
            )
        max_layer = max(groups) if groups else 0
        total_rows = max((len(group) for group in groups.values()), default=1)
        longest_name = max(
            (len(str(self.devices.names.get_name_string(device.device_id)))
             for device in self.devices.devices_list),
            default=4,
        )
        max_pins = max(
            (max(len(device.inputs), len(device.outputs), 1)
             for device in self.devices.devices_list),
            default=1,
        )
        return {
            "layers": layers,
            "groups": groups,
            "max_layer": max_layer,
            "total_rows": total_rows,
            "block_width": min(190, max(116, longest_name * 8 + 26)),
            "band_height": max(50, max_pins * self.circuit_pin_spacing + 20),
        }

    def device_block_height(self, device):
        """Return the drawn height of a device, sized for its pin count."""
        pins = max(len(device.inputs), len(device.outputs), 1)
        return max(46, pins * self.circuit_pin_spacing + 16)

    def build_device_positions(self, bounds):
        """Return a grid layout with devices aligned to shared rows."""
        x_pos, y_pos, width, height = bounds
        metrics = self.circuit_metrics()
        block_width = metrics["block_width"]
        band_height = metrics["band_height"]
        max_layer = metrics["max_layer"]
        total_rows = metrics["total_rows"]

        if max_layer > 0:
            col_pitch = (width - 2 * self.circuit_margin_x - block_width)
            col_pitch = max(col_pitch / max_layer, block_width + 90)
        else:
            col_pitch = 0
        if total_rows > 1:
            row_pitch = (
                height - self.circuit_margin_top - self.circuit_margin_bottom
                - band_height
            )
            row_pitch = max(row_pitch / (total_rows - 1), band_height + 26)
        else:
            row_pitch = 0

        left = x_pos + self.circuit_margin_x
        top = y_pos + height - self.circuit_margin_top - band_height
        positions = {}
        rows = {}
        for layer in sorted(metrics["groups"]):
            group = metrics["groups"][layer]
            start_row = (total_rows - len(group)) // 2
            col_left = left + layer * col_pitch
            for index, device in enumerate(group):
                row = start_row + index
                band_bottom = top - row * row_pitch
                device_height = self.device_block_height(device)
                node_y = band_bottom + (band_height - device_height) / 2
                positions[device.device_id] = (
                    col_left, node_y, block_width, device_height
                )
                rows[device.device_id] = row

        self.circuit_grid = {
            "left": left, "top": top, "col_pitch": col_pitch,
            "row_pitch": row_pitch, "block_width": block_width,
            "band_height": band_height, "max_layer": max_layer,
            "total_rows": total_rows, "layers": metrics["layers"],
            "rows": rows,
        }
        return positions

    def circuit_content_size(self, view_width, view_height):
        """Return virtual circuit dimensions that keep routing room."""
        metrics = self.circuit_metrics()
        max_layer = metrics["max_layer"]
        total_rows = metrics["total_rows"]
        min_col_gap = 90
        min_row_gap = 26

        natural_width = (
            2 * self.circuit_margin_x
            + (max_layer + 1) * metrics["block_width"]
            + max_layer * min_col_gap
        )
        natural_height = (
            self.circuit_margin_top + self.circuit_margin_bottom
            + total_rows * metrics["band_height"]
            + max(0, total_rows - 1) * min_row_gap
        )
        return (
            max(view_width, natural_width),
            max(view_height, natural_height),
        )

    def draw_circuit_scrollbars(self, view_bounds):
        """Draw scrollbars for oversized circuit diagrams."""
        if self.circuit_geometry.get("mode") == "3d":
            self.draw_circuit_scrollbars_3d(view_bounds)
            return
        view_x, view_y, view_width, view_height = view_bounds
        content_width = self.circuit_geometry.get("content_width", view_width)
        content_height = self.circuit_geometry.get(
            "content_height", view_height
        )
        max_scroll_x = self.circuit_geometry.get("max_scroll_x", 0)
        max_scroll_y = self.circuit_geometry.get("max_scroll_y", 0)

        if max_scroll_y > 0:
            track = (view_x + view_width + 6, view_y, 10, view_height)
            thumb_height = max(28, view_height * view_height / content_height)
            usable = max(view_height - thumb_height, 1)
            fraction = self.circuit_scroll_y / max_scroll_y
            thumb_y = view_y + (1 - fraction) * usable
            thumb = (track[0] + 1, thumb_y, 8, thumb_height)
            self.draw_rectangle(
                track,
                self.theme_colour("scrollbar_track"),
                self.theme_colour("scrollbar_border"),
            )
            self.draw_rectangle(
                thumb,
                self.theme_colour("scrollbar_thumb"),
                self.theme_colour("scrollbar_border"),
            )
            self.circuit_geometry["vertical_track"] = track
            self.circuit_geometry["vertical_thumb"] = thumb
        else:
            self.circuit_geometry["vertical_track"] = None
            self.circuit_geometry["vertical_thumb"] = None

        if max_scroll_x > 0:
            track = (view_x, view_y - 16, view_width, 11)
            thumb_width = max(44, view_width * view_width / content_width)
            usable = max(view_width - thumb_width, 1)
            fraction = self.circuit_scroll_x / max_scroll_x
            thumb_x = view_x + fraction * usable
            thumb = (thumb_x, track[1] + 1, thumb_width, 9)
            self.draw_rectangle(
                track,
                self.theme_colour("scrollbar_track"),
                self.theme_colour("scrollbar_border"),
            )
            self.draw_rectangle(
                thumb,
                self.theme_colour("scrollbar_thumb"),
                self.theme_colour("scrollbar_border"),
            )
            self.circuit_geometry["horizontal_track"] = track
            self.circuit_geometry["horizontal_thumb"] = thumb
        else:
            self.circuit_geometry["horizontal_track"] = None
            self.circuit_geometry["horizontal_thumb"] = None

    def draw_circuit_scrollbars_3d(self, view_bounds):
        """Draw scrollbars that pan the rotatable 3D circuit camera.

        The 3D view has no fixed content rectangle, so the bars instead move
        the camera within a bounded pan range: the thumb size reflects how
        much of the scene is on screen and its position reflects the current
        pan, giving the same "drag to move around" handle as the 2D view.
        """
        view_x, view_y, view_width, view_height = view_bounds
        geometry = self.circuit_geometry
        max_pan_x = geometry.get("max_pan_x", 0)
        max_pan_y = geometry.get("max_pan_y", 0)

        if max_pan_y > 0:
            content_y = max(geometry.get("content_y", view_height), 1)
            visible_y = geometry.get("visible_y", view_height)
            track = (view_x + view_width + 6, view_y, 10, view_height)
            thumb_height = self.clamp(
                view_height * visible_y / content_y, 28, view_height
            )
            usable = max(view_height - thumb_height, 1)
            fraction = self.clamp(
                (self.circuit_3d_pan_y + max_pan_y) / (2 * max_pan_y), 0, 1
            )
            thumb_y = view_y + (1 - fraction) * usable
            thumb = (track[0] + 1, thumb_y, 8, thumb_height)
            self.draw_rectangle(
                track,
                self.theme_colour("scrollbar_track"),
                self.theme_colour("scrollbar_border"),
            )
            self.draw_rectangle(
                thumb,
                self.theme_colour("scrollbar_thumb"),
                self.theme_colour("scrollbar_border"),
            )
            geometry["vertical_track"] = track
            geometry["vertical_thumb"] = thumb
        else:
            geometry["vertical_track"] = None
            geometry["vertical_thumb"] = None

        if max_pan_x > 0:
            content_x = max(geometry.get("content_x", view_width), 1)
            visible_x = geometry.get("visible_x", view_width)
            track = (view_x, view_y - 16, view_width, 11)
            thumb_width = self.clamp(
                view_width * visible_x / content_x, 44, view_width
            )
            usable = max(view_width - thumb_width, 1)
            fraction = self.clamp(
                (max_pan_x - self.circuit_3d_pan_x) / (2 * max_pan_x), 0, 1
            )
            thumb_x = view_x + fraction * usable
            thumb = (thumb_x, track[1] + 1, thumb_width, 9)
            self.draw_rectangle(
                track,
                self.theme_colour("scrollbar_track"),
                self.theme_colour("scrollbar_border"),
            )
            self.draw_rectangle(
                thumb,
                self.theme_colour("scrollbar_thumb"),
                self.theme_colour("scrollbar_border"),
            )
            geometry["horizontal_track"] = track
            geometry["horizontal_thumb"] = thumb
        else:
            geometry["horizontal_track"] = None
            geometry["horizontal_thumb"] = None

    def set_circuit_3d_scroll(self, axis, fraction):
        """Pan the 3D circuit camera from a scrollbar fraction in [0, 1].

        ``fraction`` 0 frames the top/left of the scene and 1 the
        bottom/right, matching the 2D scrollbar convention and the
        drag-to-pan direction.
        """
        fraction = self.clamp(fraction, 0.0, 1.0)
        if axis == "vertical":
            max_pan = self.circuit_geometry.get("max_pan_y", 0.0)
            self.circuit_3d_pan_y = (fraction * 2.0 - 1.0) * max_pan
        else:
            max_pan = self.circuit_geometry.get("max_pan_x", 0.0)
            self.circuit_3d_pan_x = (1.0 - fraction * 2.0) * max_pan

    def estimate_circuit_height(self):
        """Return enough circuit height to avoid stacked device overlap."""
        layers = self.calculate_device_layers()
        layer_counts = {}
        for device in self.devices.devices_list:
            layer = layers.get(device.device_id, 1)
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        max_devices_in_layer = max(layer_counts.values(), default=1)
        block_height = 34
        row_gap = 8
        vertical_padding = 56
        return (
            vertical_padding
            + max_devices_in_layer * block_height
            + max(0, max_devices_in_layer - 1) * row_gap
        )

    def calculate_device_layers(self):
        """Group devices by dependency depth for circuit drawing."""
        layers = {}
        for device in self.devices.devices_list:
            if not device.inputs:
                layers[device.device_id] = 0

        for _ in self.devices.devices_list:
            changed = False
            for device in self.devices.devices_list:
                if device.device_id in layers:
                    continue

                source_layers = []
                waiting_for_source = False
                for connected_output in device.inputs.values():
                    if connected_output is None:
                        continue
                    source_device_id, _ = connected_output
                    if source_device_id == device.device_id:
                        continue
                    if source_device_id not in layers:
                        waiting_for_source = True
                        break
                    source_layers.append(layers[source_device_id])

                if not waiting_for_source and source_layers:
                    layers[device.device_id] = max(source_layers) + 1
                    changed = True

            if not changed:
                break

        for device in self.devices.devices_list:
            if device.device_id not in layers:
                layers[device.device_id] = 1

        return layers

    def draw_connections(self, positions):
        """Route wires through clear channels and corridors between devices.

        Wires only travel vertically inside the gaps between columns and
        horizontally inside the gaps between rows, so no wire is ever drawn
        across a device block.  Each wire is given its own lane in a channel
        and its own track in a corridor so they never sit on top of one
        another.
        """
        grid = getattr(self, "circuit_grid", None)
        if not grid:
            return
        for points, signal in self.circuit_wire_paths(positions, grid):
            self.draw_wire_path(points, signal)

    def circuit_wire_paths(self, positions, grid):
        """Return ``(points, signal)`` for every routed wire.

        The same clean orthogonal routes drive both the 2D diagram and the
        3D circuit floor, so the 3D wires inherit the channel/corridor lanes
        and connect to the same distinct input pins.
        """
        wires = self.collect_circuit_wires(positions, grid)
        self.assign_wire_lanes(wires)
        return [
            (self.route_circuit_wire(wire, grid), wire["signal"])
            for wire in wires
        ]

    def collect_circuit_wires(self, positions, grid):
        """Return a routed-wire description for every connected input."""
        wires = []
        for target in self.devices.devices_list:
            if target.device_id not in positions:
                continue
            for input_id in self.sorted_port_ids(target.inputs):
                connected = target.inputs[input_id]
                if connected is None:
                    continue
                source_id, output_id = connected
                if source_id not in positions:
                    continue
                source = self.devices.get_device(source_id)
                wires.append({
                    "start": self.output_pin(
                        positions[source_id], source, output_id
                    ),
                    "end": self.input_pin(
                        positions[target.device_id], target, input_id
                    ),
                    "source_layer": grid["layers"].get(source_id, 0),
                    "target_layer": grid["layers"].get(target.device_id, 0),
                    "source_row": grid["rows"].get(source_id, 0),
                    "target_row": grid["rows"].get(target.device_id, 0),
                    "signal": source.outputs.get(output_id),
                })
        return wires

    def assign_wire_lanes(self, wires):
        """Give every wire unique channel lanes and corridor tracks."""
        channels = {}
        corridors = {}
        highway = []
        for wire in wires:
            wire["channel_index"] = {}
            source_layer = wire["source_layer"]
            target_layer = wire["target_layer"]
            if target_layer == source_layer + 1:
                wire["route"] = "adjacent"
                wire["main_channel"] = source_layer
                channels.setdefault(source_layer, []).append(wire)
            elif target_layer > source_layer:
                wire["route"] = "span"
                wire["out_channel"] = source_layer
                wire["in_channel"] = target_layer - 1
                channels.setdefault(source_layer, []).append(wire)
                channels.setdefault(target_layer - 1, []).append(wire)
                side = ("below" if wire["target_row"] >= wire["source_row"]
                        else "above")
                wire["corridor_key"] = (side, wire["source_row"])
                corridors.setdefault(wire["corridor_key"], []).append(wire)
            else:
                wire["route"] = "feedback"
                wire["out_channel"] = source_layer
                wire["in_channel"] = max(target_layer - 1, 0)
                channels.setdefault(source_layer, []).append(wire)
                channels.setdefault(max(target_layer - 1, 0), []).append(wire)
                highway.append(wire)

        for channel, channel_wires in channels.items():
            for lane, wire in enumerate(channel_wires):
                wire["channel_index"][channel] = (lane, len(channel_wires))
        for corridor_wires in corridors.values():
            for track, wire in enumerate(corridor_wires):
                wire["corridor_track"] = (track, len(corridor_wires))
        for track, wire in enumerate(highway):
            wire["highway_track"] = (track, len(highway))

    def circuit_channel_x(self, grid, channel, wire):
        """Return the x of a wire's vertical lane within a channel."""
        lane, count = wire["channel_index"][channel]
        channel_left = (
            grid["left"] + channel * grid["col_pitch"] + grid["block_width"]
        )
        channel_width = grid["col_pitch"] - grid["block_width"]
        return channel_left + (lane + 1) * channel_width / (count + 1)

    def circuit_corridor_y(self, grid, wire):
        """Return the y of a wire's horizontal track within a corridor."""
        side, row = wire["corridor_key"]
        track, count = wire["corridor_track"]
        corridor_height = max(grid["row_pitch"] - grid["band_height"], 30)
        band_bottom = grid["top"] - row * grid["row_pitch"]
        offset = (track + 1) * corridor_height / (count + 1)
        if side == "below":
            return band_bottom - offset
        return band_bottom + grid["band_height"] + offset

    def route_circuit_wire(self, wire, grid):
        """Return the orthogonal point list for one routed wire."""
        x_start, y_start = wire["start"]
        x_end, y_end = wire["end"]
        if wire["route"] == "adjacent":
            lane_x = self.circuit_channel_x(grid, wire["main_channel"], wire)
            return [(x_start, y_start), (lane_x, y_start),
                    (lane_x, y_end), (x_end, y_end)]

        out_x = self.circuit_channel_x(grid, wire["out_channel"], wire)
        in_x = self.circuit_channel_x(grid, wire["in_channel"], wire)
        if wire["route"] == "span":
            corridor_y = self.circuit_corridor_y(grid, wire)
        else:
            track, _ = wire["highway_track"]
            corridor_y = grid["top"] + grid["band_height"] + 10 + track * 8
        return [(x_start, y_start), (out_x, y_start), (out_x, corridor_y),
                (in_x, corridor_y), (in_x, y_end), (x_end, y_end)]

    def draw_wire_path(self, points, signal):
        """Draw an orthogonal wire through the given points."""
        if len(points) < 2:
            return
        self.set_signal_colour(signal)
        GL.glLineWidth(1.6)
        GL.glBegin(GL.GL_LINE_STRIP)
        for x_pos, y_pos in points:
            GL.glVertex2f(x_pos, y_pos)
        GL.glEnd()
        GL.glLineWidth(1.0)

    def draw_device_node(self, device, bounds):
        """Draw one device as a labelled circuit block."""
        x_pos, y_pos, width, height = bounds
        kind = self.devices.names.get_name_string(device.device_kind)
        name = self.devices.names.get_name_string(device.device_id)
        fill_colour = self.device_fill_colour(device)

        self.draw_rectangle(
            bounds, fill_colour, self.theme_colour("device_border")
        )
        self.render_scaled_text(
            name, x_pos + 8, y_pos + height - 16, 13, width - 16
        )
        self.render_scaled_text(
            kind, x_pos + 8, y_pos + height - 33, 9, width - 16,
            self.theme_colour("subtle_text")
        )

        for input_id in self.sorted_port_ids(device.inputs):
            pin_x, pin_y = self.input_pin(bounds, device, input_id)
            self.draw_circle(pin_x, pin_y, 4.0, (0.98, 0.98, 0.98))

        for output_id in self.sorted_port_ids(device.outputs):
            pin_x, pin_y = self.output_pin(bounds, device, output_id)
            signal = device.outputs.get(output_id)
            self.draw_circle(pin_x, pin_y, 5.5, self.signal_colour(signal))

    def device_fill_colour(self, device):
        """Return a fill colour for a device type."""
        if device.device_kind == self.devices.SWITCH:
            return self.theme_colour("switch_fill")
        if device.device_kind == self.devices.CLOCK:
            return self.theme_colour("clock_fill")
        if device.device_kind == self.devices.D_TYPE:
            return self.theme_colour("dtype_fill")
        return self.theme_colour("gate_fill")

    def input_pin(self, bounds, device, input_id):
        """Return the position of an input pin."""
        x_pos, y_pos, _, height = bounds
        input_ids = self.sorted_port_ids(device.inputs)
        if input_id not in input_ids:
            return x_pos, y_pos + height / 2

        index = input_ids.index(input_id)
        count = len(input_ids)
        return x_pos, self.distributed_pin_y(y_pos, height, index, count)

    def output_pin(self, bounds, device, output_id):
        """Return the position of an output pin."""
        x_pos, y_pos, width, height = bounds
        output_ids = self.sorted_port_ids(device.outputs)
        if output_id not in output_ids:
            return x_pos + width, y_pos + height / 2

        index = output_ids.index(output_id)
        count = len(output_ids)
        return (
            x_pos + width,
            self.distributed_pin_y(y_pos, height, index, count),
        )

    def distributed_pin_y(self, y_pos, height, index, count):
        """Return a vertically distributed pin y coordinate."""
        if count <= 1:
            return y_pos + height / 2
        usable_height = height - 12
        return y_pos + height - 6 - index * usable_height / (count - 1)

    def draw_oscilloscope(self, bounds, monitor_items):
        """Draw monitor signals in a floating oscilloscope window."""
        self.scope_geometry.pop("rows_3d", None)
        x_pos, y_pos, width, height = bounds

        margin_x = 12 if width > 520 else 6
        scope_bounds = (
            x_pos + margin_x,
            y_pos + 2,
            width - 2 * margin_x,
            height - 4,
        )
        self.last_scope_bounds = scope_bounds
        scope_x, scope_y, scope_width, scope_height = scope_bounds

        self.draw_rectangle(
            scope_bounds,
            self.theme_colour("scope_bg"),
            self.theme_colour("scope_border"),
        )
        self.draw_scope_header(scope_bounds)

        if not monitor_items:
            self.render_text(
                self.text("no_monitors"),
                scope_x + 20,
                scope_y + scope_height - 78,
            )
            return

        label_width = self.calculate_scope_label_width(monitor_items)
        title_height = 28
        control_height = 8
        axis_height = 84
        scroll_width = 14

        plot_x = scope_x + label_width
        plot_y = scope_y + axis_height
        plot_width = scope_width - label_width - scroll_width - 20
        self.last_scope_plot_width = plot_width
        control_y = scope_y + scope_height - title_height - control_height
        plot_height = control_y - plot_y - 8
        self.last_scope_plot_height = plot_height

        scope_cycle_zoom = getattr(self, "scope_cycle_zoom", 1.0)
        zoomed_cycle_width = self.default_cycle_width * scope_cycle_zoom
        max_visible_cycles = max(10, int(plot_width // zoomed_cycle_width))
        max_cycles = self.max_recorded_cycles(monitor_items)
        if max_cycles == 0:
            cycle_count = min(10, max_visible_cycles)
            first_cycle = 0
            self.scope_first_cycle = 0
            self.cycle_width = plot_width / max(cycle_count, 1)

            total_rows = len(monitor_items)
            visible_rows = self.scope_visible_rows(plot_height, total_rows)
            max_first_row = max(total_rows - visible_rows, 0)
            self.scope_first_row = self.clamp(
                self.scope_first_row, 0, max_first_row
            )
            visible_monitor_items = monitor_items[
                self.scope_first_row:self.scope_first_row + visible_rows
            ]

            self.render_text(
                self.text("press_run"),
                scope_x + 20,
                scope_y + scope_height - 50,
                self.theme_colour("subtle_text"),
            )
            self.draw_scope_grid(
                plot_x, plot_y, plot_width, plot_height, cycle_count
            )
            self.draw_scope_scrollbars(
                scope_bounds, plot_x, plot_y, plot_width, plot_height,
                first_cycle, cycle_count, cycle_count, self.scope_first_row,
                total_rows, visible_rows
            )
            self.draw_empty_scope_rows(
                scope_x, plot_x, plot_y, plot_height, visible_monitor_items,
                cycle_count, self.scope_first_row
            )
            self.draw_scope_axis(
                plot_x, plot_y, cycle_count, first_cycle, cycle_count
            )
            return

        cycle_count = min(max(max_cycles, 10), max_visible_cycles)
        max_first_cycle = max(max_cycles - cycle_count, 0)
        if self.follow_latest_cycles:
            self.scope_first_cycle = max_first_cycle
        else:
            self.scope_first_cycle = self.clamp(
                self.scope_first_cycle, 0, max_first_cycle
            )
        first_cycle = self.scope_first_cycle
        self.cycle_width = plot_width / max(cycle_count, 1)

        total_rows = len(monitor_items)
        visible_rows = self.scope_visible_rows(plot_height, total_rows)
        max_first_row = max(total_rows - visible_rows, 0)
        self.scope_first_row = self.clamp(
            self.scope_first_row, 0, max_first_row
        )
        visible_monitor_items = monitor_items[
            self.scope_first_row:self.scope_first_row + visible_rows
        ]

        self.draw_scope_grid(
            plot_x, plot_y, plot_width, plot_height, cycle_count
        )
        self.draw_scope_scrollbars(
            scope_bounds, plot_x, plot_y, plot_width, plot_height,
            first_cycle, max_cycles, cycle_count, self.scope_first_row,
            total_rows, visible_rows
        )
        self.draw_scope_rows(
            scope_x, plot_x, plot_y, plot_height, visible_monitor_items,
            first_cycle, cycle_count, self.scope_first_row
        )
        self.draw_scope_axis(
            plot_x, plot_y, cycle_count, first_cycle, max_cycles
        )

    def draw_3d_oscilloscope(self, bounds, monitor_items):
        """Draw monitor signals as useful over-elaborate 3D traces."""
        x_pos, y_pos, width, height = bounds

        margin_x = 12 if width > 520 else 6
        scope_bounds = (
            x_pos + margin_x,
            y_pos + 2,
            width - 2 * margin_x,
            height - 4,
        )
        self.last_scope_bounds = scope_bounds
        scope_x, scope_y, scope_width, scope_height = scope_bounds

        self.draw_rectangle(
            scope_bounds,
            self.theme_colour("scope_bg"),
            self.theme_colour("scope_border"),
        )
        self.draw_scope_header(scope_bounds, self.text("oscilloscope_3d"))

        if not monitor_items:
            self.scope_geometry = {}
            self.render_text(
                self.text("no_monitors"),
                scope_x + 20,
                scope_y + scope_height - 78,
            )
            return

        label_width = self.calculate_scope_label_width(monitor_items)
        title_height = 28
        control_height = 8
        axis_height = 84
        scroll_width = 14

        plot_x = scope_x + label_width
        plot_y = scope_y + axis_height
        plot_width = scope_width - label_width - scroll_width - 20
        self.last_scope_plot_width = plot_width
        control_y = scope_y + scope_height - title_height - control_height
        plot_height = control_y - plot_y - 8
        self.last_scope_plot_height = plot_height
        if plot_width <= 0 or plot_height <= 0:
            return

        scope_cycle_zoom = getattr(self, "scope_cycle_zoom", 1.0)
        zoomed_cycle_width = self.default_cycle_width * scope_cycle_zoom
        max_visible_cycles = max(10, int(plot_width // zoomed_cycle_width))
        max_cycles = self.max_recorded_cycles(monitor_items)

        if max_cycles == 0:
            cycle_count = min(10, max_visible_cycles)
            first_cycle = 0
            self.scope_first_cycle = 0
            self.cycle_width = plot_width / max(cycle_count, 1)
            total_rows = len(monitor_items)
            visible_rows = self.scope_visible_rows(plot_height, total_rows)
            max_first_row = max(total_rows - visible_rows, 0)
            self.scope_first_row = self.clamp(
                self.scope_first_row, 0, max_first_row
            )
            visible_monitor_items = monitor_items[
                self.scope_first_row:self.scope_first_row + visible_rows
            ]

            self.render_text(
                self.text("press_run"),
                scope_x + 20,
                scope_y + scope_height - 50,
                self.theme_colour("subtle_text"),
            )
            self.draw_3d_trace_view(
                plot_x, plot_y, plot_width, plot_height,
                visible_monitor_items, first_cycle, cycle_count,
                self.scope_first_row, use_blank=True
            )
            self.draw_3d_scope_labels(
                scope_x, plot_x, plot_y, plot_height,
                visible_monitor_items, self.scope_first_row
            )
            self.draw_scope_scrollbars(
                scope_bounds, plot_x, plot_y, plot_width, plot_height,
                first_cycle, cycle_count, cycle_count, self.scope_first_row,
                total_rows, visible_rows
            )
            self.draw_scope_axis(
                plot_x, plot_y, cycle_count, first_cycle, cycle_count
            )
            return

        cycle_count = min(max(max_cycles, 10), max_visible_cycles)
        max_first_cycle = max(max_cycles - cycle_count, 0)
        if self.follow_latest_cycles:
            self.scope_first_cycle = max_first_cycle
        else:
            self.scope_first_cycle = self.clamp(
                self.scope_first_cycle, 0, max_first_cycle
            )
        first_cycle = self.scope_first_cycle
        self.cycle_width = plot_width / max(cycle_count, 1)

        total_rows = len(monitor_items)
        visible_rows = self.scope_visible_rows(plot_height, total_rows)
        max_first_row = max(total_rows - visible_rows, 0)
        self.scope_first_row = self.clamp(
            self.scope_first_row, 0, max_first_row
        )
        visible_monitor_items = monitor_items[
            self.scope_first_row:self.scope_first_row + visible_rows
        ]

        self.draw_3d_trace_view(
            plot_x, plot_y, plot_width, plot_height, visible_monitor_items,
            first_cycle, cycle_count, self.scope_first_row
        )
        self.draw_3d_scope_labels(
            scope_x, plot_x, plot_y, plot_height, visible_monitor_items,
            self.scope_first_row
        )
        self.draw_scope_scrollbars(
            scope_bounds, plot_x, plot_y, plot_width, plot_height,
            first_cycle, max_cycles, cycle_count, self.scope_first_row,
            total_rows, visible_rows
        )
        self.draw_scope_axis(
            plot_x, plot_y, cycle_count, first_cycle, max_cycles
        )

    def draw_3d_scope_labels(self, label_x, plot_x, plot_y, plot_height,
                             monitor_items, first_row):
        """Draw readable row labels beside the 3D plot."""
        row_gap = self.scope_row_gap(plot_height, len(monitor_items))
        for index, monitor_item in enumerate(monitor_items):
            (device_id, output_id), _ = monitor_item
            name = self.devices.get_signal_name(device_id, output_id)
            row_mid = plot_y + plot_height - 18 - index * row_gap
            colour = self.trace_colour_for_monitor(
                device_id, output_id,
                self.signal_colour_index(device_id, output_id)
            )
            self.render_text(name, label_x + 14, row_mid - 5, colour)
            self.render_text(
                "1", plot_x - 18, row_mid + 6,
                self.theme_colour("subtle_text")
            )
            self.render_text(
                "0", plot_x - 18, row_mid - 11,
                self.theme_colour("subtle_text")
            )

    def fit_3d_camera_distance(self, width, height, span_x, span_z, depth,
                               rotate_x_deg, rotate_y_deg, zoom,
                               half_height=9.0, fov_y=35.0):
        """Return a camera distance and far plane that frame the whole scene.

        The rotated bounding box of the scene is projected onto the horizontal
        and vertical fields of view, so the whole 3D model is framed snugly at
        the current viewing angle without any part being clipped off the edges
        of the panel.
        """
        half_fov_y = math.radians(fov_y / 2.0)
        tan_y = math.tan(half_fov_y)
        tan_x = tan_y * (width / max(height, 1))

        half_width = span_x / 2.0
        half_depth = span_z / 2.0 + depth
        rotate_x = math.radians(rotate_x_deg)
        rotate_y = math.radians(rotate_y_deg)

        max_x = max_y = max_z = 0.0
        for sign_x in (-1.0, 1.0):
            for sign_y in (-1.0, 1.0):
                for sign_z in (-1.0, 1.0):
                    corner = self.rotate_scene_corner(
                        sign_x * half_width, sign_y * half_height,
                        sign_z * half_depth, rotate_x, rotate_y
                    )
                    max_x = max(max_x, abs(corner[0]))
                    max_y = max(max_y, abs(corner[1]))
                    max_z = max(max_z, abs(corner[2]))

        fit_distance = max(max_x / tan_x, max_y / tan_y) + max_z
        fit_distance = max(fit_distance, 120.0)
        camera_distance = fit_distance * 1.12 / max(zoom, 0.2)
        far_plane = camera_distance + max_z + 200.0
        return camera_distance, far_plane

    def rotate_scene_corner(self, x_pos, y_pos, z_pos, rotate_x, rotate_y):
        """Rotate a scene corner the way the 3D trace camera will view it."""
        cos_y = math.cos(rotate_y)
        sin_y = math.sin(rotate_y)
        x_rot = x_pos * cos_y + z_pos * sin_y
        z_rot = -x_pos * sin_y + z_pos * cos_y
        cos_x = math.cos(rotate_x)
        sin_x = math.sin(rotate_x)
        y_rot = y_pos * cos_x - z_rot * sin_x
        z_final = y_pos * sin_x + z_rot * cos_x
        return x_rot, y_rot, z_final

    def axis_gizmo_axes(self, rotate_x_deg, rotate_y_deg):
        """Return screen directions for the X/Y/Z axes at a camera angle.

        Each entry is ``(label, dx, dy, depth)`` where ``(dx, dy)`` is the
        on-screen direction of that model axis (so the indicator rotates
        exactly with the scene) and ``depth`` increases toward the viewer.
        Entries are sorted farthest first so nearer arrows draw on top.
        """
        rotate_x = math.radians(rotate_x_deg)
        rotate_y = math.radians(rotate_y_deg)
        axes = []
        for label, axis in (
            ("X", (1.0, 0.0, 0.0)),
            ("Y", (0.0, 1.0, 0.0)),
            ("Z", (0.0, 0.0, 1.0)),
        ):
            dx, dy, depth = self.rotate_scene_corner(
                axis[0], axis[1], axis[2], rotate_x, rotate_y
            )
            axes.append((label, dx, dy, depth))
        axes.sort(key=lambda entry: entry[3])
        return axes

    def draw_3d_axis_gizmo(self, centre_x, centre_y, radius,
                           rotate_x_deg, rotate_y_deg):
        """Draw a small rotating X/Y/Z axis indicator for a 3D view."""
        colours = {
            "X": (0.78, 0.16, 0.16),
            "Y": (0.18, 0.30, 0.86),
            "Z": (0.20, 0.62, 0.28),
        }
        for label, dx, dy, _ in self.axis_gizmo_axes(
            rotate_x_deg, rotate_y_deg
        ):
            tip_x = centre_x + dx * radius
            tip_y = centre_y + dy * radius
            length = math.hypot(tip_x - centre_x, tip_y - centre_y)
            self.set_colour(*colours[label])
            GL.glLineWidth(2.4)
            GL.glBegin(GL.GL_LINES)
            GL.glVertex2f(centre_x, centre_y)
            GL.glVertex2f(tip_x, tip_y)
            GL.glEnd()
            if length > 1e-6:
                unit_x = (tip_x - centre_x) / length
                unit_y = (tip_y - centre_y) / length
            else:
                # Axis points at the viewer: keep a readable stub label.
                unit_x, unit_y = 0.0, 1.0
            GL.glBegin(GL.GL_TRIANGLES)
            GL.glVertex2f(tip_x + unit_x * 7, tip_y + unit_y * 7)
            GL.glVertex2f(tip_x - unit_y * 3.2, tip_y + unit_x * 3.2)
            GL.glVertex2f(tip_x + unit_y * 3.2, tip_y - unit_x * 3.2)
            GL.glEnd()
            self.render_text(
                label, tip_x + unit_x * 12 - 3, tip_y + unit_y * 12 - 5,
                colours[label]
            )
        GL.glLineWidth(1.0)
        self.draw_circle(
            centre_x, centre_y, 2.4, self.theme_colour("text")
        )

    def draw_3d_trace_view(self, plot_x, plot_y, plot_width, plot_height,
                           monitor_items, first_cycle, cycle_count,
                           first_row, use_blank=False):
        """Render the visible monitor window in a perspective sub-viewport."""
        self.draw_rectangle(
            (plot_x, plot_y, plot_width, plot_height),
            self.theme_colour("scope_bg"),
            self.theme_colour("grid_minor"),
        )

        viewport = self.canvas_pixel_rect(
            (plot_x, plot_y, plot_width, plot_height)
        )
        if viewport is None:
            return

        size = self.GetClientSize()
        x_pos, y_pos, width, height = viewport
        row_count = max(len(monitor_items), 1)
        cycle_pitch = 18.0
        row_pitch = 22.0
        row_depth = 8.5
        cycle_span = cycle_count * cycle_pitch
        row_span = max(row_count - 1, 0) * row_pitch
        camera_distance, far_plane = self.fit_3d_camera_distance(
            width, height, cycle_span, row_span, row_depth,
            self.trace_3d_rotate_x, self.trace_3d_rotate_y, self.trace_3d_zoom
        )
        aspect = width / max(height, 1)
        self.scope_geometry["rows_3d"] = self.build_3d_scope_row_hits(
            viewport, monitor_items, cycle_span, row_span, row_pitch,
            camera_distance, aspect
        )

        try:
            GL.glViewport(x_pos, y_pos, width, height)
            GL.glEnable(GL.GL_SCISSOR_TEST)
            GL.glScissor(x_pos, y_pos, width, height)
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glDepthFunc(GL.GL_LEQUAL)

            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glLoadIdentity()
            GLU.gluPerspective(35.0, aspect, 1.0, far_plane)

            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glLoadIdentity()
            GL.glTranslatef(
                self.trace_3d_pan_x, self.trace_3d_pan_y,
                -camera_distance
            )
            GL.glRotatef(self.trace_3d_rotate_x, 1.0, 0.0, 0.0)
            GL.glRotatef(self.trace_3d_rotate_y, 0.0, 1.0, 0.0)
            GL.glTranslatef(-cycle_span / 2, -9.0, row_span / 2)

            self.configure_3d_lighting()
            self.draw_3d_floor(
                cycle_count, row_count, cycle_pitch, row_pitch, first_cycle
            )

            for index, monitor_item in enumerate(monitor_items):
                (device_id, output_id), signal_list = monitor_item
                z_pos = -index * row_pitch
                colour = self.trace_colour_for_monitor(
                    device_id, output_id,
                    self.signal_colour_index(device_id, output_id)
                )
                visible_signals = self.visible_signal_window(
                    signal_list, first_cycle, cycle_count, use_blank
                )
                previous_signal = None
                if not use_blank and 0 < first_cycle <= len(signal_list):
                    previous_signal = signal_list[first_cycle - 1]
                self.draw_3d_monitor_row(
                    visible_signals, previous_signal, z_pos, colour,
                    cycle_pitch, row_depth
                )
        finally:
            GL.glLineWidth(1.0)
            self.configure_2d_projection(size)
        self.draw_3d_axis_gizmo(
            plot_x + 40, plot_y + 42, 24,
            self.trace_3d_rotate_x, self.trace_3d_rotate_y
        )

    def build_3d_scope_row_hits(self, viewport, monitor_items, cycle_span,
                                row_span, row_pitch, camera_distance,
                                aspect):
        """Return projected screen segments for each visible 3D scope row.

        Each entry carries the signal name and the on-screen endpoints of
        that monitor row's centre line, so hovering the mouse over a 3D
        trace can identify which signal it belongs to.
        """
        camera = {
            "viewport": viewport,
            "distance": camera_distance,
            "aspect": aspect,
            "rotate_x": self.trace_3d_rotate_x,
            "rotate_y": self.trace_3d_rotate_y,
            "pan_x": self.trace_3d_pan_x,
            "pan_y": self.trace_3d_pan_y,
        }
        rows = []
        for index, monitor_item in enumerate(monitor_items):
            (device_id, output_id), _ = monitor_item
            name = self.devices.get_signal_name(device_id, output_id)
            z_pos = -index * row_pitch + row_span / 2
            start = self.project_3d_trace_point(
                -cycle_span / 2, 0.0, z_pos, camera
            )
            end = self.project_3d_trace_point(
                cycle_span / 2, 0.0, z_pos, camera
            )
            if start is not None and end is not None:
                rows.append({"name": name, "start": start, "end": end})
        return rows

    def project_3d_trace_point(self, x_pos, y_pos, z_pos, camera):
        """Project a 3D trace-scene point to canvas coordinates.

        Mirrors the GL camera exactly (rotate, pan, perspective) so the
        result lands where the point is actually drawn; returns ``None``
        for points at or behind the camera plane.
        """
        view_x, view_y, view_width, view_height = camera["viewport"]
        rotated = self.rotate_scene_corner(
            x_pos, y_pos, z_pos,
            math.radians(camera["rotate_x"]),
            math.radians(camera["rotate_y"]),
        )
        eye_x = rotated[0] + camera["pan_x"]
        eye_y = rotated[1] + camera["pan_y"]
        eye_z = rotated[2] - camera["distance"]
        if eye_z >= -1.0:
            return None
        tan_y = math.tan(math.radians(camera.get("fov_y", 35.0) / 2.0))
        tan_x = tan_y * camera["aspect"]
        ndc_x = eye_x / (-eye_z * tan_x)
        ndc_y = eye_y / (-eye_z * tan_y)
        pixel_x = view_x + (ndc_x + 1.0) / 2.0 * view_width
        pixel_y = view_y + (ndc_y + 1.0) / 2.0 * view_height
        return (
            (pixel_x - self.pan_x) / self.zoom,
            (pixel_y - self.pan_y) / self.zoom,
        )

    def pick_3d_scope_row(self, x_pos, y_pos, max_distance=14.0):
        """Return the signal name of the 3D scope row under the cursor."""
        best_name = None
        best_distance = max_distance
        for row in self.scope_geometry.get("rows_3d") or []:
            distance = self.point_segment_distance(
                x_pos, y_pos,
                row["start"][0], row["start"][1],
                row["end"][0], row["end"][1],
            )
            if distance < best_distance:
                best_distance = distance
                best_name = row["name"]
        return best_name

    def point_segment_distance(self, px, py, ax, ay, bx, by):
        """Return the distance from a point to a 2D line segment."""
        dx = bx - ax
        dy = by - ay
        length_sq = dx * dx + dy * dy
        if length_sq <= 0.0:
            return math.hypot(px - ax, py - ay)
        t = self.clamp(((px - ax) * dx + (py - ay) * dy) / length_sq, 0, 1)
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    def update_3d_hover(self, x_pos, y_pos):
        """Show the hovered 3D trace's signal name as a tooltip."""
        name = None
        if self.trace_display_3d and self.point_in_rect(
            x_pos, y_pos, self.scope_geometry.get("plot")
        ):
            name = self.pick_3d_scope_row(x_pos, y_pos)
        if name != self.hover_3d_name:
            self.hover_3d_name = name
            if name:
                self.SetToolTip(name)
            else:
                self.UnsetToolTip()

    def configure_3d_lighting(self):
        """Configure simple lighting for raised signal blocks."""
        GL.glEnable(GL.GL_COLOR_MATERIAL)
        GL.glEnable(GL.GL_LIGHTING)
        GL.glEnable(GL.GL_LIGHT0)
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_AMBIENT, [0.28, 0.28, 0.28, 1.0])
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_DIFFUSE, [0.78, 0.78, 0.78, 1.0])
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_POSITION, [0.0, 80.0, 120.0, 0.0])
        GL.glColorMaterial(GL.GL_FRONT, GL.GL_AMBIENT_AND_DIFFUSE)

    def draw_3d_floor(self, cycle_count, row_count, cycle_pitch, row_pitch,
                      first_cycle):
        """Draw a floor grid that preserves time and monitor-row context."""
        x_end = cycle_count * cycle_pitch
        z_top = row_pitch * 0.55
        z_bottom = -(row_count - 1) * row_pitch - row_pitch * 0.55

        GL.glDisable(GL.GL_LIGHTING)
        self.set_colour(*self.theme_colour("grid_minor"))
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex3f(0.0, -0.15, z_top)
        GL.glVertex3f(x_end, -0.15, z_top)
        GL.glVertex3f(x_end, -0.15, z_bottom)
        GL.glVertex3f(0.0, -0.15, z_bottom)
        GL.glEnd()

        GL.glLineWidth(1.0)
        GL.glBegin(GL.GL_LINES)
        for cycle in range(cycle_count + 1):
            if (first_cycle + cycle) % 5 == 0:
                self.set_colour(*self.theme_colour("grid_major"))
            else:
                self.set_colour(*self.theme_colour("grid_row"))
            x_pos = cycle * cycle_pitch
            GL.glVertex3f(x_pos, 0.0, z_top)
            GL.glVertex3f(x_pos, 0.0, z_bottom)

        for row in range(row_count):
            z_pos = -row * row_pitch
            self.set_colour(*self.theme_colour("level_guide"))
            GL.glVertex3f(0.0, 0.0, z_pos)
            GL.glVertex3f(x_end, 0.0, z_pos)
        GL.glEnd()

    def draw_3d_monitor_row(self, signals, previous_signal, z_pos, colour,
                            cycle_pitch, row_depth):
        """Draw one monitor row as level-height blocks through time."""
        previous_height = self.signal_height_3d(previous_signal)
        for index, signal in enumerate(signals):
            x_start = index * cycle_pitch
            x_center = x_start + cycle_pitch / 2
            height = self.signal_height_3d(signal)
            if height is None:
                self.draw_3d_blank_segment(
                    x_start, x_start + cycle_pitch, z_pos
                )
                previous_height = None
                continue

            if previous_height is not None and previous_height != height:
                self.draw_3d_edge_wall(
                    x_start, z_pos, row_depth / 2,
                    max(previous_height, height),
                    colour
                )

            self.set_colour(*self.trace_3d_level_colour(colour, signal))
            self.draw_3d_cuboid(
                x_center, z_pos, cycle_pitch * 0.44, row_depth / 2, height
            )
            previous_height = height

    def visible_signal_window(self, signal_list, first_cycle, cycle_count,
                              use_blank=False):
        """Return a fixed-length visible signal slice for trace rendering."""
        if use_blank:
            return [self.devices.BLANK] * cycle_count

        visible_signals = list(signal_list[first_cycle:first_cycle
                                           + cycle_count])
        missing_cycles = cycle_count - len(visible_signals)
        if missing_cycles > 0:
            visible_signals.extend([self.devices.BLANK] * missing_cycles)
        return visible_signals

    def signal_height_3d(self, signal):
        """Map a simulator signal to a 3D height, or None for blanks."""
        if signal in [self.devices.HIGH, self.devices.RISING]:
            return 18.0
        if signal in [self.devices.LOW, self.devices.FALLING]:
            return 5.0
        return None

    def trace_3d_level_colour(self, colour, signal):
        """Dim low-level blocks while keeping the monitor colour identity."""
        if signal in [self.devices.HIGH, self.devices.RISING]:
            return colour
        return tuple(self.clamp(component * 0.55 + 0.12, 0.0, 1.0)
                     for component in colour)

    def draw_3d_blank_segment(self, x_start, x_end, z_pos):
        """Draw a dashed mid-level marker for cycles without recorded data."""
        GL.glDisable(GL.GL_LIGHTING)
        self.set_colour(*self.theme_colour("blank_signal"))
        dash = 5.0
        x_pos = x_start + 1.0
        GL.glBegin(GL.GL_LINES)
        while x_pos < x_end:
            GL.glVertex3f(x_pos, 8.5, z_pos)
            GL.glVertex3f(min(x_pos + dash, x_end - 1.0), 8.5, z_pos)
            x_pos += dash * 2
        GL.glEnd()

    def draw_3d_edge_wall(self, x_pos, z_pos, half_depth, height, colour):
        """Draw a thin vertical transition marker between two levels."""
        self.set_colour(*colour)
        self.draw_3d_cuboid(x_pos, z_pos, 0.75, half_depth, height)

    def draw_3d_cuboid(self, x_pos, z_pos, half_width, half_depth, height):
        """Draw a raised rectangular signal block."""
        GL.glEnable(GL.GL_LIGHTING)
        GL.glBegin(GL.GL_QUADS)
        GL.glNormal3f(0.0, -1.0, 0.0)
        GL.glVertex3f(x_pos - half_width, 0.0, z_pos - half_depth)
        GL.glVertex3f(x_pos + half_width, 0.0, z_pos - half_depth)
        GL.glVertex3f(x_pos + half_width, 0.0, z_pos + half_depth)
        GL.glVertex3f(x_pos - half_width, 0.0, z_pos + half_depth)

        GL.glNormal3f(0.0, 1.0, 0.0)
        GL.glVertex3f(x_pos + half_width, height, z_pos - half_depth)
        GL.glVertex3f(x_pos - half_width, height, z_pos - half_depth)
        GL.glVertex3f(x_pos - half_width, height, z_pos + half_depth)
        GL.glVertex3f(x_pos + half_width, height, z_pos + half_depth)

        GL.glNormal3f(-1.0, 0.0, 0.0)
        GL.glVertex3f(x_pos - half_width, height, z_pos - half_depth)
        GL.glVertex3f(x_pos - half_width, 0.0, z_pos - half_depth)
        GL.glVertex3f(x_pos - half_width, 0.0, z_pos + half_depth)
        GL.glVertex3f(x_pos - half_width, height, z_pos + half_depth)

        GL.glNormal3f(1.0, 0.0, 0.0)
        GL.glVertex3f(x_pos + half_width, 0.0, z_pos - half_depth)
        GL.glVertex3f(x_pos + half_width, height, z_pos - half_depth)
        GL.glVertex3f(x_pos + half_width, height, z_pos + half_depth)
        GL.glVertex3f(x_pos + half_width, 0.0, z_pos + half_depth)

        GL.glNormal3f(0.0, 0.0, -1.0)
        GL.glVertex3f(x_pos - half_width, 0.0, z_pos - half_depth)
        GL.glVertex3f(x_pos - half_width, height, z_pos - half_depth)
        GL.glVertex3f(x_pos + half_width, height, z_pos - half_depth)
        GL.glVertex3f(x_pos + half_width, 0.0, z_pos - half_depth)

        GL.glNormal3f(0.0, 0.0, 1.0)
        GL.glVertex3f(x_pos - half_width, height, z_pos + half_depth)
        GL.glVertex3f(x_pos - half_width, 0.0, z_pos + half_depth)
        GL.glVertex3f(x_pos + half_width, 0.0, z_pos + half_depth)
        GL.glVertex3f(x_pos + half_width, height, z_pos + half_depth)
        GL.glEnd()

    def draw_scope_header(self, bounds, title=None):
        """Draw the oscilloscope title strip."""
        x_pos, y_pos, width, height = bounds
        header_bounds = (x_pos, y_pos + height - 28, width, 28)
        self.draw_rectangle(
            header_bounds,
            self.theme_colour("scope_header"),
            self.theme_colour("scope_header_border"),
        )
        if title is None:
            title = self.text("oscilloscope")
        self.render_text(title, x_pos + 30, y_pos + height - 18)
        self.draw_rectangle(
            (x_pos + 9, y_pos + height - 21, 12, 12),
            self.theme_colour("scope_icon"),
            self.theme_colour("scope_icon_border"),
        )

    def draw_scope_grid(self, plot_x, plot_y, width, height, cycle_count):
        """Draw oscilloscope grid lines."""
        GL.glBegin(GL.GL_LINES)
        for cycle in range(cycle_count + 1):
            if cycle % 5 == 0:
                self.set_colour(*self.theme_colour("grid_major"))
            else:
                self.set_colour(*self.theme_colour("grid_minor"))
            x_pos = plot_x + cycle * self.cycle_width
            GL.glVertex2f(x_pos, plot_y)
            GL.glVertex2f(x_pos, plot_y + height)

        for row in range(0, int(height), 24):
            self.set_colour(*self.theme_colour("grid_row"))
            GL.glVertex2f(plot_x, plot_y + row)
            GL.glVertex2f(plot_x + width, plot_y + row)
        GL.glEnd()

    def scope_visible_rows(self, plot_height, total_rows):
        """Return how many monitor rows fit at the current vertical zoom.

        A smaller ``scope_row_zoom`` packs more signals into the plot so the
        whole monitor set can be seen at once; the per-row slot never drops
        below a readable floor, which also bounds how many rows are drawn.
        """
        zoom = getattr(self, "scope_row_zoom", 1.0)
        slot_height = max(self.row_height * zoom, self.min_row_band)
        visible = max(1, int(plot_height // slot_height))
        return min(visible, total_rows)

    def scope_row_gap(self, plot_height, count):
        """Return the spacing that spreads ``count`` rows over the plot.

        The visible rows always fill the plot height; the gap is floored so
        compressed rows stay legible and capped so a handful of monitors do
        not drift far apart.
        """
        gap = plot_height / max(count, 1)
        return self.clamp(gap, self.min_row_band, 88.0)

    def scope_row_amplitude(self, row_gap):
        """Return a waveform half-height that fits inside one row's band."""
        return self.clamp(row_gap * 0.42, 4.0, self.high_offset)

    def draw_scope_rows(self, label_x, plot_x, plot_y, plot_height,
                        monitor_items, first_cycle, cycle_count,
                        first_row):
        """Draw all monitored signal names and waveforms."""
        row_gap = self.scope_row_gap(plot_height, len(monitor_items))
        high_off = self.scope_row_amplitude(row_gap)
        low_off = self.low_offset * high_off / self.high_offset
        for index, monitor_item in enumerate(monitor_items):
            (device_id, output_id), signal_list = monitor_item
            name = self.devices.get_signal_name(device_id, output_id)
            row_mid = plot_y + plot_height - row_gap * 0.5 - index * row_gap
            row_base = row_mid - high_off / 2

            colour = self.trace_colour_for_monitor(
                device_id, output_id,
                self.signal_colour_index(device_id, output_id)
            )
            self.set_colour(*colour)
            self.render_text(name, label_x + 14, row_mid - 5, colour)
            self.draw_signal_level_scale(
                plot_x, plot_y, plot_height, row_base, row_gap,
                high_off, low_off
            )
            visible_signals = signal_list[
                first_cycle:first_cycle + cycle_count
            ]
            self.draw_digital_signal(
                plot_x, row_base, visible_signals, colour, high_off, low_off
            )

    def draw_signal_level_scale(self, plot_x, plot_y, plot_height, row_base,
                                row_gap, high_off, low_off):
        """Draw 1/0 scale labels and guide lines for one waveform row."""
        high_y = row_base + high_off
        low_y = row_base + low_off

        self.set_colour(*self.theme_colour("level_mark"))
        GL.glBegin(GL.GL_LINES)
        GL.glVertex2f(plot_x, high_y)
        GL.glVertex2f(plot_x + 8, high_y)
        GL.glVertex2f(plot_x, low_y)
        GL.glVertex2f(plot_x + 8, low_y)
        GL.glEnd()

        if row_gap >= 18:
            self.render_text("1", plot_x - 18, high_y - 4,
                             self.theme_colour("subtle_text"))
            self.render_text("0", plot_x - 18, low_y - 4,
                             self.theme_colour("subtle_text"))

        if row_gap >= 26:
            self.set_colour(*self.theme_colour("level_guide"))
            GL.glBegin(GL.GL_LINES)
            GL.glVertex2f(plot_x, high_y)
            GL.glVertex2f(plot_x + 40, high_y)
            GL.glVertex2f(plot_x, low_y)
            GL.glVertex2f(plot_x + 40, low_y)
            GL.glEnd()

    def draw_empty_scope_rows(self, label_x, plot_x, plot_y, plot_height,
                              monitor_items, cycle_count, first_row):
        """Draw aligned monitor rows before any signal data is recorded."""
        row_gap = self.scope_row_gap(plot_height, len(monitor_items))
        high_off = self.scope_row_amplitude(row_gap)
        low_off = self.low_offset * high_off / self.high_offset
        blank_signals = [self.devices.BLANK] * cycle_count
        for index, monitor_item in enumerate(monitor_items):
            (device_id, output_id), _ = monitor_item
            name = self.devices.get_signal_name(device_id, output_id)
            row_mid = plot_y + plot_height - row_gap * 0.5 - index * row_gap
            row_base = row_mid - high_off / 2

            colour = self.trace_colour_for_monitor(
                device_id, output_id,
                self.signal_colour_index(device_id, output_id)
            )
            self.render_text(name, label_x + 14, row_mid - 5, colour)
            self.draw_signal_level_scale(
                plot_x, plot_y, plot_height, row_base, row_gap,
                high_off, low_off
            )
            self.draw_digital_signal(
                plot_x, row_base, blank_signals, colour, high_off, low_off
            )

    def draw_digital_signal(self, plot_x, row_base, signal_list, colour,
                            high_off, low_off):
        """Draw one digital signal as a continuous square waveform."""
        high_y = row_base + high_off
        low_y = row_base + low_off
        previous_y = None

        for index, signal in enumerate(signal_list):
            x_start = plot_x + index * self.cycle_width
            x_end = x_start + self.cycle_width

            if signal == self.devices.BLANK:
                self.draw_blank_signal(x_start, x_end, row_base, high_off,
                                       low_off)
                previous_y = None
                continue

            current_y = self.signal_y(signal, high_y, low_y)
            if current_y is None:
                continue

            self.set_colour(*colour)
            GL.glLineWidth(2.0)
            GL.glBegin(GL.GL_LINE_STRIP)
            if previous_y is None:
                GL.glVertex2f(x_start, current_y)
            else:
                GL.glVertex2f(x_start, previous_y)
                if previous_y != current_y:
                    GL.glVertex2f(x_start, current_y)
            GL.glVertex2f(x_end, current_y)
            GL.glEnd()
            GL.glLineWidth(1.0)
            previous_y = current_y

    def signal_y(self, signal, high_y, low_y):
        """Map a simulator signal level to a stable y position."""
        if signal in [self.devices.HIGH, self.devices.RISING]:
            return high_y
        if signal in [self.devices.LOW, self.devices.FALLING]:
            return low_y
        return None

    def signal_colour_index(self, device_id, output_id):
        """Return a palette index fixed to the signal's identity.

        Indexing colours by the monitored signal rather than its current row
        keeps every trace the same colour as other monitors are added or
        removed.
        """
        order = self.signal_colour_order()
        return order.get((device_id, output_id), len(order))

    def signal_colour_order(self):
        """Return cached colour indices for every output in the circuit.

        The cache is keyed on the active devices object, so it is rebuilt
        automatically whenever a new definition file replaces the circuit.
        """
        cache = getattr(self, "_signal_colour_cache", None)
        if cache is None or cache[0] is not self.devices:
            order = {}
            for device in self.devices.devices_list:
                for output_id in self.sorted_port_ids(device.outputs):
                    order[(device.device_id, output_id)] = len(order)
            cache = (self.devices, order)
            self._signal_colour_cache = cache
        return cache[1]

    def trace_colour_for_monitor(self, device_id, output_id, index):
        """Return a trace colour, with clocks highlighted in green."""
        if self.colour_blind_mode:
            colours = self.colour_blind_trace_colours
            return colours[index % len(colours)]

        device = self.devices.get_device(device_id)
        if device is not None and device.device_kind == self.devices.CLOCK:
            return (0.20, 0.55, 0.25)
        if output_id == self.devices.QBAR_ID:
            return (0.48, 0.30, 0.68)
        return self.trace_colours[index % len(self.trace_colours)]

    def draw_blank_signal(self, x_start, x_end, row_base, high_off, low_off):
        """Draw a blank signal interval for monitors added mid-run."""
        mid_y = row_base + (high_off + low_off) / 2
        dash_width = 5
        self.set_colour(*self.theme_colour("blank_signal"))
        GL.glBegin(GL.GL_LINES)
        while x_start < x_end:
            GL.glVertex2f(x_start, mid_y)
            GL.glVertex2f(min(x_start + dash_width, x_end), mid_y)
            x_start += dash_width * 2
        GL.glEnd()

    def draw_scope_scrollbars(self, bounds, plot_x, plot_y, plot_width,
                              plot_height, first_cycle, max_cycles,
                              cycle_count, first_row, total_rows,
                              visible_rows):
        """Draw oscilloscope scrollbars and save their hit targets."""
        x_pos, y_pos, width, _ = bounds
        right_x = plot_x + plot_width + 6
        self.scope_geometry = {
            "plot": (plot_x, plot_y, plot_width, plot_height),
            "max_first_cycle": max(max_cycles - cycle_count, 0),
            "max_first_row": max(total_rows - visible_rows, 0),
            # Keep the 3D hover rows stored by draw_3d_trace_view earlier
            # in this same frame.
            "rows_3d": self.scope_geometry.get("rows_3d"),
        }

        vertical_track = (right_x, plot_y, 10, plot_height)
        self.draw_rectangle(
            vertical_track,
            self.theme_colour("scrollbar_track"),
            self.theme_colour("scrollbar_border"),
        )
        if total_rows > visible_rows:
            thumb_height = max(28, plot_height * visible_rows / total_rows)
            fraction = first_row / max(total_rows - visible_rows, 1)
            thumb_y = plot_y + (1 - fraction) * (plot_height - thumb_height)
        else:
            thumb_height = max(28, plot_height * 0.55)
            thumb_y = plot_y + (plot_height - thumb_height) / 2
        vertical_thumb = (right_x + 1, thumb_y, 8, thumb_height)
        self.draw_rectangle(
            vertical_thumb,
            self.theme_colour("scrollbar_thumb"),
            self.theme_colour("scrollbar_border"),
        )

        bar_y = y_pos + 34
        bar_x = plot_x
        bar_width = plot_width
        horizontal_track = (bar_x, bar_y, bar_width, 13)
        self.draw_rectangle(
            horizontal_track,
            self.theme_colour("scrollbar_track"),
            self.theme_colour("scrollbar_border"),
        )
        self.draw_rectangle(
            (bar_x - 12, bar_y, 12, 13),
            self.theme_colour("scrollbar_step"),
            self.theme_colour("scrollbar_border"),
        )
        self.draw_rectangle(
            (bar_x + bar_width, bar_y, 12, 13),
            self.theme_colour("scrollbar_step"),
            self.theme_colour("scrollbar_border"),
        )

        if max_cycles > cycle_count:
            fraction = first_cycle / max(max_cycles - cycle_count, 1)
            thumb_width = max(44, bar_width * cycle_count / max_cycles)
            thumb_x = bar_x + fraction * (bar_width - thumb_width)
        else:
            thumb_width = max(44, bar_width * 0.55)
            thumb_x = bar_x + (bar_width - thumb_width) / 2
        horizontal_thumb = (thumb_x, bar_y + 2, thumb_width, 9)
        self.draw_rectangle(
            horizontal_thumb,
            self.theme_colour("scrollbar_thumb"),
            self.theme_colour("scrollbar_border"),
        )
        self.scope_geometry.update({
            "vertical_track": vertical_track,
            "vertical_thumb": vertical_thumb,
            "horizontal_track": horizontal_track,
            "horizontal_thumb": horizontal_thumb,
        })
        self.render_text(
            "<", bar_x - 9, bar_y + 2,
            self.theme_colour("scrollbar_arrow")
        )
        self.render_text(">", bar_x + bar_width + 4, bar_y + 2,
                         self.theme_colour("scrollbar_arrow"))

    def draw_scope_axis(self, plot_x, plot_y, cycle_count, first_cycle,
                        max_cycles):
        """Draw cycle tick labels along the bottom of the scope."""
        self.set_colour(*self.theme_colour("axis"))
        GL.glBegin(GL.GL_LINES)
        GL.glVertex2f(plot_x, plot_y)
        GL.glVertex2f(plot_x + cycle_count * self.cycle_width, plot_y)
        GL.glEnd()

        for cycle in range(cycle_count + 1):
            if cycle % 5 != 0:
                continue
            x_pos = plot_x + cycle * self.cycle_width
            GL.glBegin(GL.GL_LINES)
            GL.glVertex2f(x_pos, plot_y)
            GL.glVertex2f(x_pos, plot_y - 6)
            GL.glEnd()
            self.render_text(str(first_cycle + cycle), x_pos - 5, plot_y - 20)

        last_cycle = max(first_cycle + cycle_count - 1, first_cycle)
        last_cycle = min(last_cycle, max(max_cycles - 1, 0))
        self.render_text(
            self.text("cycles_shown").format(
                first=first_cycle, last=last_cycle
            ),
            plot_x + 28, plot_y - 76, self.theme_colour("axis")
        )
        self.render_text(
            self.text("level"), plot_x - 38, plot_y - 76,
            self.theme_colour("subtle_text")
        )

    def max_recorded_cycles(self, monitor_items):
        """Return the longest recorded monitor trace."""
        max_cycles = 0
        for _, signal_list in monitor_items:
            max_cycles = max(max_cycles, len(signal_list))
        return max_cycles

    def calculate_scope_label_width(self, monitor_items):
        """Return enough left margin to fit monitor labels."""
        longest_name = 0
        for (device_id, output_id), _ in monitor_items:
            monitor_name = self.devices.get_signal_name(device_id, output_id)
            longest_name = max(longest_name, len(str(monitor_name)))
        return max(116, 28 + longest_name * 8)

    def sorted_port_ids(self, port_dictionary):
        """Return port IDs ordered by their display names."""
        return sorted(port_dictionary, key=self.port_sort_name)

    def port_sort_name(self, port_id):
        """Return a stable display name for sorting port IDs."""
        if port_id is None:
            return ""
        return str(self.devices.names.get_name_string(port_id))

    def canvas_pixel_rect(self, bounds):
        """Return transformed integer canvas pixels for a drawing rectangle."""
        x_pos, y_pos, width, height = bounds
        size = self.GetClientSize()
        x_pos = x_pos * self.zoom + self.pan_x
        y_pos = y_pos * self.zoom + self.pan_y
        width = width * self.zoom
        height = height * self.zoom

        left = max(0, int(round(x_pos)))
        bottom = max(0, int(round(y_pos)))
        right = min(size.width, int(round(x_pos + width)))
        top = min(size.height, int(round(y_pos + height)))
        if right <= left or top <= bottom:
            return None
        return left, bottom, right - left, top - bottom

    def begin_scissor(self, bounds):
        """Clip OpenGL drawing to a canvas-space rectangle."""
        rect = self.canvas_pixel_rect(bounds)
        if rect is None:
            return

        x_pos, y_pos, width, height = rect
        GL.glEnable(GL.GL_SCISSOR_TEST)
        GL.glScissor(x_pos, y_pos, width, height)

    def end_scissor(self):
        """Disable OpenGL clipping."""
        GL.glDisable(GL.GL_SCISSOR_TEST)

    def draw_rectangle(self, bounds, fill_colour, border_colour=None):
        """Draw a filled rectangle with an optional border."""
        x_pos, y_pos, width, height = bounds
        self.set_colour(*fill_colour)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex2f(x_pos, y_pos)
        GL.glVertex2f(x_pos + width, y_pos)
        GL.glVertex2f(x_pos + width, y_pos + height)
        GL.glVertex2f(x_pos, y_pos + height)
        GL.glEnd()

        if border_colour is not None:
            self.set_colour(*border_colour)
            GL.glBegin(GL.GL_LINE_LOOP)
            GL.glVertex2f(x_pos, y_pos)
            GL.glVertex2f(x_pos + width, y_pos)
            GL.glVertex2f(x_pos + width, y_pos + height)
            GL.glVertex2f(x_pos, y_pos + height)
            GL.glEnd()

    def draw_circle(self, x_pos, y_pos, radius, fill_colour):
        """Draw a filled circular marker."""
        self.set_colour(*fill_colour)
        GL.glBegin(GL.GL_TRIANGLE_FAN)
        GL.glVertex2f(x_pos, y_pos)
        for index in range(25):
            angle = 2 * 3.141592653589793 * index / 24
            GL.glVertex2f(
                x_pos + radius * math.cos(angle),
                y_pos + radius * math.sin(angle),
            )
        GL.glEnd()
        self.set_colour(*self.theme_colour("pin_border"))
        GL.glBegin(GL.GL_LINE_LOOP)
        for index in range(24):
            angle = 2 * 3.141592653589793 * index / 24
            GL.glVertex2f(
                x_pos + radius * math.cos(angle),
                y_pos + radius * math.sin(angle),
            )
        GL.glEnd()

    def set_signal_colour(self, signal):
        """Set colour for circuit wires according to signal level."""
        self.set_colour(*self.signal_colour(signal))

    def signal_colour(self, signal):
        """Return colour for a signal level."""
        if self.colour_blind_mode:
            if signal in [self.devices.HIGH, self.devices.RISING]:
                return (0.00, 0.45, 0.70)
            if signal in [self.devices.LOW, self.devices.FALLING]:
                return (0.90, 0.62, 0.00)

        if signal in [self.devices.HIGH, self.devices.RISING]:
            return (0.86, 0.08, 0.08)
        if signal in [self.devices.LOW, self.devices.FALLING]:
            if self.dark_mode:
                return (0.78, 0.82, 0.88)
            return (0.28, 0.28, 0.30)
        return (0.70, 0.70, 0.70)

    def on_paint(self, event):
        """Handle repaint requests."""
        wx.PaintDC(self)
        self.render()

    def on_size(self, event):
        """Reconfigure the OpenGL projection after resizing."""
        self.init = False
        event.Skip()

    def on_mouse(self, event):
        """Handle scrolling and 3D rotation inside the circuit and scope.

        The whole-canvas pan and zoom are intentionally disabled so the
        layout stays locked in place; only the circuit scrollbars, the
        oscilloscope scrollbars, and the 3D trace camera respond to the
        mouse.
        """
        size = self.GetClientSize()
        object_x = (event.GetX() - self.pan_x) / self.zoom
        object_y = (size.height - event.GetY() - self.pan_y) / self.zoom

        if event.ButtonDown():
            self.last_mouse_x = event.GetX()
            self.last_mouse_y = event.GetY()
            if self.start_circuit_3d_drag(object_x, object_y):
                return
            if self.start_circuit_scroll_drag(object_x, object_y):
                return
            if self.start_scope_scroll_drag(object_x, object_y):
                return
            if self.start_3d_trace_drag(object_x, object_y):
                return

        if event.Dragging() and self.circuit_3d_drag_active:
            self.update_circuit_3d_drag(event)
            self.Refresh()
            return

        if event.Dragging() and self.circuit_drag_mode is not None:
            self.update_circuit_scroll_drag(object_x, object_y)
            self.Refresh()
            return

        if event.Dragging() and self.scope_drag_mode is not None:
            self.update_scope_scroll_drag(object_x, object_y)
            self.Refresh()
            return

        if event.Dragging() and self.trace_3d_drag_active:
            self.update_3d_trace_drag(event)
            self.Refresh()
            return

        if event.ButtonUp():
            self.circuit_drag_mode = None
            self.scope_drag_mode = None
            self.trace_3d_drag_active = False
            self.circuit_3d_drag_active = False

        if event.Moving():
            self.update_3d_hover(object_x, object_y)

        wheel_rotation = event.GetWheelRotation()
        if wheel_rotation != 0 and self.wheel_circuit(
            object_x, object_y, wheel_rotation
        ):
            self.Refresh()
            return

        if wheel_rotation != 0 and self.zoom_3d_trace_view(
            object_x, object_y, wheel_rotation
        ):
            self.Refresh()
            return

        if wheel_rotation != 0 and self.wheel_scope(
            object_x, object_y, wheel_rotation
        ):
            self.Refresh()
            return

    def start_circuit_3d_drag(self, x_pos, y_pos):
        """Start rotating the 3D circuit view when it is clicked."""
        if not self.circuit_display_3d:
            return False
        if not self.point_in_rect(x_pos, y_pos,
                                  self.circuit_geometry.get("view")):
            return False

        self.circuit_3d_drag_active = True
        return True

    def update_circuit_3d_drag(self, event):
        """Rotate (or, with the right button, pan) the 3D circuit camera."""
        x_delta = event.GetX() - self.last_mouse_x
        y_delta = event.GetY() - self.last_mouse_y
        self.last_mouse_x = event.GetX()
        self.last_mouse_y = event.GetY()
        if event.RightIsDown():
            scale = 1.6 / max(self.circuit_3d_zoom, 0.3)
            self.circuit_3d_pan_x += x_delta * scale
            self.circuit_3d_pan_y -= y_delta * scale
            return
        self.circuit_3d_rotate_y += x_delta * 0.5
        self.circuit_3d_rotate_x = self.clamp(
            self.circuit_3d_rotate_x + y_delta * 0.5, 8.0, 82.0
        )

    def start_3d_trace_drag(self, x_pos, y_pos):
        """Start rotating or panning the 3D trace view when clicked."""
        if not self.trace_display_3d:
            return False
        if not self.point_in_rect(x_pos, y_pos,
                                  self.scope_geometry.get("plot")):
            return False

        self.trace_3d_drag_active = True
        return True

    def update_3d_trace_drag(self, event):
        """Rotate or pan the 3D trace camera during a mouse drag."""
        x_delta = event.GetX() - self.last_mouse_x
        y_delta = event.GetY() - self.last_mouse_y
        self.last_mouse_x = event.GetX()
        self.last_mouse_y = event.GetY()

        if event.RightIsDown():
            scale = 0.45 / max(self.trace_3d_zoom, 0.25)
            self.trace_3d_pan_x += x_delta * scale
            self.trace_3d_pan_y -= y_delta * scale
            return

        self.trace_3d_rotate_y += x_delta * 0.55
        self.trace_3d_rotate_x = self.clamp(
            self.trace_3d_rotate_x + y_delta * 0.55, -72.0, 72.0
        )

    def zoom_3d_trace_view(self, x_pos, y_pos, wheel_rotation):
        """Zoom the perspective trace camera when the wheel is over it."""
        if not self.trace_display_3d:
            return False
        if not self.point_in_rect(x_pos, y_pos,
                                  self.scope_geometry.get("plot")):
            return False

        if wx.GetKeyState(wx.WXK_SHIFT):
            return self.scroll_scope_rows(x_pos, y_pos, wheel_rotation)

        factor = 1.12 if wheel_rotation > 0 else 1 / 1.12
        self.trace_3d_zoom = self.clamp(
            self.trace_3d_zoom * factor, 0.35, 3.5
        )
        return True

    def start_circuit_scroll_drag(self, x_pos, y_pos):
        """Start dragging a circuit scrollbar if one was clicked."""
        vertical_track = self.circuit_geometry.get("vertical_track")
        vertical_thumb = self.circuit_geometry.get("vertical_thumb")
        horizontal_track = self.circuit_geometry.get("horizontal_track")
        horizontal_thumb = self.circuit_geometry.get("horizontal_thumb")

        if self.point_in_rect(x_pos, y_pos, vertical_thumb):
            self.circuit_drag_mode = "vertical"
            self.circuit_drag_offset = y_pos - vertical_thumb[1]
            return True

        if vertical_thumb and self.point_in_rect(x_pos, y_pos, vertical_track):
            self.circuit_drag_mode = "vertical"
            self.circuit_drag_offset = vertical_thumb[3] / 2
            self.update_circuit_scroll_drag(x_pos, y_pos)
            self.Refresh()
            return True

        if self.point_in_rect(x_pos, y_pos, horizontal_thumb):
            self.circuit_drag_mode = "horizontal"
            self.circuit_drag_offset = x_pos - horizontal_thumb[0]
            return True

        if horizontal_thumb and self.point_in_rect(
            x_pos, y_pos, horizontal_track
        ):
            self.circuit_drag_mode = "horizontal"
            self.circuit_drag_offset = horizontal_thumb[2] / 2
            self.update_circuit_scroll_drag(x_pos, y_pos)
            self.Refresh()
            return True

        return False

    def update_circuit_scroll_drag(self, x_pos, y_pos):
        """Update circuit scroll (2D) or camera pan (3D) during a drag."""
        is_3d = self.circuit_geometry.get("mode") == "3d"
        if self.circuit_drag_mode == "vertical":
            track = self.circuit_geometry.get("vertical_track")
            thumb = self.circuit_geometry.get("vertical_thumb")
            max_scroll_y = self.circuit_geometry.get("max_scroll_y", 0)
            if not track or not thumb or (not is_3d and max_scroll_y == 0):
                return

            _, track_y, _, track_height = track
            _, _, _, thumb_height = thumb
            usable = max(track_height - thumb_height, 1)
            thumb_y = self.clamp(
                y_pos - self.circuit_drag_offset, track_y, track_y + usable
            )
            fraction = 1 - ((thumb_y - track_y) / usable)
            if is_3d:
                self.set_circuit_3d_scroll("vertical", fraction)
            else:
                self.circuit_scroll_y = fraction * max_scroll_y

        if self.circuit_drag_mode == "horizontal":
            track = self.circuit_geometry.get("horizontal_track")
            thumb = self.circuit_geometry.get("horizontal_thumb")
            max_scroll_x = self.circuit_geometry.get("max_scroll_x", 0)
            if not track or not thumb or (not is_3d and max_scroll_x == 0):
                return

            track_x, _, track_width, _ = track
            _, _, thumb_width, _ = thumb
            usable = max(track_width - thumb_width, 1)
            thumb_x = self.clamp(
                x_pos - self.circuit_drag_offset, track_x, track_x + usable
            )
            fraction = (thumb_x - track_x) / usable
            if is_3d:
                self.set_circuit_3d_scroll("horizontal", fraction)
            else:
                self.circuit_scroll_x = fraction * max_scroll_x

    def wheel_circuit(self, x_pos, y_pos, wheel_rotation):
        """Zoom the circuit overview, or scroll it with Shift held."""
        if not self.point_in_rect(x_pos, y_pos,
                                  self.circuit_geometry.get("view")):
            return False
        if self.circuit_display_3d:
            factor = 1.12 if wheel_rotation > 0 else 1.0 / 1.12
            self.zoom_circuit_3d_at(factor, x_pos, y_pos)
            return True
        if wx.GetKeyState(wx.WXK_SHIFT):
            return self.scroll_circuit_view(x_pos, y_pos, wheel_rotation)
        factor = 1.1 if wheel_rotation > 0 else 1.0 / 1.1
        self.zoom_circuit_at(factor, x_pos, y_pos)
        return True

    def scroll_circuit_view(self, x_pos, y_pos, wheel_rotation):
        """Scroll the circuit overview when the wheel is over it."""
        view = self.circuit_geometry.get("view")
        if not self.point_in_rect(x_pos, y_pos, view):
            return False

        max_scroll_x = self.circuit_geometry.get("max_scroll_x", 0)
        max_scroll_y = self.circuit_geometry.get("max_scroll_y", 0)
        if max_scroll_x == 0 and max_scroll_y == 0:
            return False

        if wx.GetKeyState(wx.WXK_SHIFT) and max_scroll_x > 0:
            step = -48 if wheel_rotation > 0 else 48
            self.circuit_scroll_x = self.clamp(
                self.circuit_scroll_x + step, 0, max_scroll_x
            )
            return True

        if max_scroll_y > 0:
            step = -48 if wheel_rotation > 0 else 48
            self.circuit_scroll_y = self.clamp(
                self.circuit_scroll_y + step, 0, max_scroll_y
            )
            return True

        if max_scroll_x > 0:
            step = -48 if wheel_rotation > 0 else 48
            self.circuit_scroll_x = self.clamp(
                self.circuit_scroll_x + step, 0, max_scroll_x
            )
            return True

        return False

    def start_scope_scroll_drag(self, x_pos, y_pos):
        """Start dragging a scope scrollbar thumb if one was clicked."""
        vertical_track = self.scope_geometry.get("vertical_track")
        vertical_thumb = self.scope_geometry.get("vertical_thumb")
        horizontal_track = self.scope_geometry.get("horizontal_track")
        horizontal_thumb = self.scope_geometry.get("horizontal_thumb")

        if self.point_in_rect(x_pos, y_pos, vertical_thumb):
            self.scope_drag_mode = "vertical"
            self.scope_drag_offset = y_pos - vertical_thumb[1]
            return True

        if vertical_thumb and self.point_in_rect(x_pos, y_pos, vertical_track):
            self.scope_drag_mode = "vertical"
            self.scope_drag_offset = vertical_thumb[3] / 2
            self.update_scope_scroll_drag(x_pos, y_pos)
            self.Refresh()
            return True

        if self.point_in_rect(x_pos, y_pos, horizontal_thumb):
            self.scope_drag_mode = "horizontal"
            self.scope_drag_offset = x_pos - horizontal_thumb[0]
            self.follow_latest_cycles = False
            return True

        if horizontal_thumb and self.point_in_rect(
            x_pos, y_pos, horizontal_track
        ):
            self.scope_drag_mode = "horizontal"
            self.scope_drag_offset = horizontal_thumb[2] / 2
            self.follow_latest_cycles = False
            self.update_scope_scroll_drag(x_pos, y_pos)
            self.Refresh()
            return True

        return False

    def update_scope_scroll_drag(self, x_pos, y_pos):
        """Update the visible scope rows or cycles during a scrollbar drag."""
        if self.scope_drag_mode == "vertical":
            track = self.scope_geometry.get("vertical_track")
            thumb = self.scope_geometry.get("vertical_thumb")
            max_first_row = self.scope_geometry.get("max_first_row", 0)
            if not track or not thumb or max_first_row == 0:
                return

            _, track_y, _, track_height = track
            _, _, _, thumb_height = thumb
            usable = max(track_height - thumb_height, 1)
            thumb_y = self.clamp(
                y_pos - self.scope_drag_offset, track_y, track_y + usable
            )
            fraction = 1 - ((thumb_y - track_y) / usable)
            self.scope_first_row = int(round(fraction * max_first_row))

        if self.scope_drag_mode == "horizontal":
            track = self.scope_geometry.get("horizontal_track")
            thumb = self.scope_geometry.get("horizontal_thumb")
            max_first_cycle = self.scope_geometry.get("max_first_cycle", 0)
            self.follow_latest_cycles = False
            if not track or not thumb or max_first_cycle == 0:
                return

            track_x, _, track_width, _ = track
            _, _, thumb_width, _ = thumb
            usable = max(track_width - thumb_width, 1)
            thumb_x = self.clamp(
                x_pos - self.scope_drag_offset, track_x, track_x + usable
            )
            fraction = (thumb_x - track_x) / usable
            self.scope_first_cycle = int(round(fraction * max_first_cycle))

    def scroll_scope_rows(self, x_pos, y_pos, wheel_rotation):
        """Scroll signal rows when the mouse wheel is over the scope."""
        plot = self.scope_geometry.get("plot")
        max_first_row = self.scope_geometry.get("max_first_row", 0)
        if not self.point_in_rect(x_pos, y_pos, plot) or max_first_row == 0:
            return False

        step = -1 if wheel_rotation > 0 else 1
        self.scope_first_row = self.clamp(
            self.scope_first_row + step, 0, max_first_row
        )
        return True

    def wheel_scope(self, x_pos, y_pos, wheel_rotation):
        """Zoom 2D scope signals vertically, or the time axis with Shift.

        Plain wheel changes how many monitor rows share the height so the
        whole set of outputs can be brought into view at once; Shift+wheel
        zooms the time axis instead.
        """
        if self.trace_display_3d:
            return False
        if not self.point_in_rect(x_pos, y_pos,
                                  self.scope_geometry.get("plot")):
            return False
        factor = 1.12 if wheel_rotation > 0 else 1.0 / 1.12
        if wx.GetKeyState(wx.WXK_SHIFT):
            self.zoom_scope(factor)
        else:
            self.zoom_scope_rows(factor)
        return True

    def point_in_rect(self, x_pos, y_pos, rect):
        """Return True if a point lies within an OpenGL rectangle."""
        if rect is None:
            return False

        rect_x, rect_y, rect_width, rect_height = rect
        return (
            rect_x <= x_pos <= rect_x + rect_width
            and rect_y <= y_pos <= rect_y + rect_height
        )

    def clamp(self, value, minimum, maximum):
        """Clamp a number between two bounds."""
        return max(minimum, min(value, maximum))

    def render_text(self, text, x_pos, y_pos, colour=None):
        """Draw bitmap text at the given position."""
        if colour is None:
            colour = self.theme_colour("text")
        self.set_colour(*colour)
        GL.glRasterPos2f(x_pos, y_pos)
        font = GLUT.GLUT_BITMAP_HELVETICA_12

        for character in str(text):
            if character == "\n":
                y_pos = y_pos - 20
                GL.glRasterPos2f(x_pos, y_pos)
            else:
                GLUT.glutBitmapCharacter(font, ord(character))

    def render_scaled_text(self, text, x_pos, y_pos, pixel_height,
                           max_width=None, colour=None):
        """Draw vector text whose size scales with the current zoom.

        Unlike the bitmap labels, stroke text is real geometry, so circuit
        labels shrink and grow with the circuit zoom and stay inside their
        device blocks instead of overflowing when zoomed out.
        """
        text = str(text)
        if colour is None:
            colour = self.theme_colour("text")
        font = GLUT.GLUT_STROKE_ROMAN
        width_units = sum(
            GLUT.glutStrokeWidth(font, ord(character)) for character in text
        ) or 1.0
        scale = pixel_height / 119.05
        if max_width is not None and width_units * scale > max_width:
            scale = max_width / width_units
        self.set_colour(*colour)
        GL.glPushMatrix()
        GL.glTranslatef(x_pos, y_pos, 0.0)
        GL.glScalef(scale, scale, scale)
        GL.glLineWidth(1.1)
        for character in text:
            GLUT.glutStrokeCharacter(font, ord(character))
        GL.glLineWidth(1.0)
        GL.glPopMatrix()

    def set_colour(self, red, green, blue):
        """Set the OpenGL drawing colour."""
        GL.glColor3f(red, green, blue)


class Gui(wx.Frame):
    """Configure the main GUI window and widgets."""

    def __init__(self, title, path, names, devices, network, monitors,
                 initial_language=None):
        """Initialise widgets, controller, and layout."""
        self.translations = self.build_translations()
        self.language_names = self.build_language_names()
        if initial_language in self.translations:
            self.current_language = initial_language
        else:
            self.current_language = choose_language(self.translations, wx)
        self.wx_locale = initialise_wx_locale(wx, self.current_language)
        translated_title = self.t("window_title")
        if translated_title == "window_title":
            translated_title = title

        super().__init__(parent=None, title=translated_title,
                         size=(1300, 860))
        self.SetBackgroundColour(wx.Colour(245, 247, 250))

        self.path = path
        self.dark_mode = False
        self.colour_blind_mode = False
        self.controller = GuiController(names, devices, network, monitors)
        self.default_monitor_keys = []
        self.default_monitor_traces = {}
        self.auto_timer = wx.Timer(self)

        self.configure_menu()
        self.CreateStatusBar()
        self.canvas = MyGLCanvas(self, devices, monitors, translator=self.t)
        self.create_controls()
        self.configure_layout()
        self.bind_events()
        self.apply_theme()
        self.remember_default_monitors()
        self.refresh_choices()
        self.set_status(self.format_text("loaded_file", path=path))

        min_canvas_width, min_canvas_height = self.canvas.minimum_visual_size()
        self.SetSizeHints(min_canvas_width + 420, min_canvas_height + 170)

    def build_translations(self):
        """Return UI label translations keyed by language code."""
        return load_translations()

    def build_language_names(self):
        """Return display names for configured languages."""
        return load_language_names()

    def t(self, key):
        """Translate a UI label for the current language."""
        return translate(self.translations, self.current_language, key)

    def format_text(self, key, **values):
        """Translate a UI label and format named placeholders."""
        return self.t(key).format(**values)

    def dark_mode_label(self):
        """Return the mode toggle label for the current state."""
        if self.dark_mode:
            return self.t("light_mode")
        return self.t("dark_mode")

    def colour_blind_mode_label(self):
        """Return the colour-mode toggle label for the current state."""
        if self.colour_blind_mode:
            return self.t("standard_colours")
        return self.t("colour_blind_mode")

    def gui_theme(self):
        """Return wx colours for the current interface theme."""
        if self.dark_mode:
            return {
                "background": wx.Colour(28, 32, 38),
                "panel": wx.Colour(34, 39, 46),
                "control": wx.Colour(43, 49, 58),
                "text": wx.Colour(231, 235, 240),
                "muted": wx.Colour(184, 193, 204),
                "log": wx.Colour(24, 28, 34),
            }
        return {
            "background": wx.Colour(245, 247, 250),
            "panel": wx.Colour(245, 247, 250),
            "control": wx.Colour(255, 255, 255),
            "text": wx.Colour(22, 26, 32),
            "muted": wx.Colour(80, 86, 96),
            "log": wx.Colour(250, 251, 253),
        }

    def apply_theme(self):
        """Apply light or dark colours to wx controls and the canvas."""
        theme = self.gui_theme()
        self.SetBackgroundColour(theme["background"])
        self.side_panel.SetBackgroundColour(theme["background"])
        self.canvas.set_dark_mode(self.dark_mode)
        self.canvas.set_colour_blind_mode(self.colour_blind_mode)

        text_controls = [
            self.cycles_label, self.speed_label,
            self.add_monitor_label, self.remove_monitor_label,
            self.fit_label,
            self.trace_display_label, self.maximise_label,
            self.switch_box, self.monitor_box,
            self.view_box,
            self.readings_box, self.log_box,
        ]
        buttons = [
            self.run_button, self.continue_button, self.step_button,
            self.auto_run_button, self.set_switch_button,
            self.add_monitor_button, self.remove_monitor_button,
            self.reset_view_button, self.circuit_fit_button,
            self.scope_fit_button, self.trace_display_button,
            self.circuit_3d_button,
            self.maximise_circuit_button, self.maximise_scope_button,
        ]
        fields = [
            self.cycles_spin, self.speed_slider, self.switch_choice,
            self.switch_value, self.add_monitor_choice,
            self.remove_monitor_choice, self.readings_list, self.log_text,
        ]

        for control in text_controls:
            control.SetForegroundColour(theme["text"])
            control.SetBackgroundColour(theme["background"])

        for control in buttons:
            control.SetForegroundColour(theme["text"])
            control.SetBackgroundColour(theme["control"])

        for control in fields:
            control.SetForegroundColour(theme["text"])
            control.SetBackgroundColour(theme["control"])

        self.log_text.SetBackgroundColour(theme["log"])
        self.Refresh()
        self.Layout()

    def configure_menu(self):
        """Create the File, Settings, and Help menus."""
        self.help_menu_id = wx.NewIdRef()
        self.export_circuit_menu_id = wx.NewIdRef()
        self.export_scope_menu_id = wx.NewIdRef()

        self.file_menu = wx.Menu()
        self.settings_menu = wx.Menu()
        self.help_menu = wx.Menu()
        self.menu_bar = wx.MenuBar()
        self.open_menu_item = self.file_menu.Append(
            wx.ID_OPEN, self.t("menu_open")
        )
        self.save_menu_item = self.file_menu.Append(
            wx.ID_SAVEAS, self.t("menu_save")
        )
        self.export_circuit_menu_item = self.file_menu.Append(
            self.export_circuit_menu_id, self.t("menu_export_circuit")
        )
        self.export_scope_menu_item = self.file_menu.Append(
            self.export_scope_menu_id, self.t("menu_export_scope")
        )
        self.file_menu.AppendSeparator()
        self.exit_menu_item = self.file_menu.Append(
            wx.ID_EXIT, self.t("menu_exit")
        )

        self.language_menu = wx.Menu()
        self.language_menu_codes = {}
        for language_code, language_name in self.language_names.items():
            item = self.language_menu.AppendRadioItem(
                wx.ID_ANY, language_name
            )
            if language_code == self.current_language:
                item.Check(True)
            self.language_menu_codes[item.GetId()] = language_code
        self.language_menu_item = self.settings_menu.AppendSubMenu(
            self.language_menu, self.t("language")
        )
        self.settings_menu.AppendSeparator()
        self.dark_mode_menu_item = self.settings_menu.AppendCheckItem(
            wx.ID_ANY, self.t("dark_mode")
        )
        self.colour_blind_menu_item = self.settings_menu.AppendCheckItem(
            wx.ID_ANY, self.t("colour_blind_mode")
        )

        self.help_menu_item = self.help_menu.Append(
            self.help_menu_id, self.t("menu_help_item")
        )
        self.about_menu_item = self.help_menu.Append(
            wx.ID_ABOUT, self.t("menu_about")
        )

        self.menu_bar.Append(self.file_menu, self.t("menu_file"))
        self.menu_bar.Append(self.settings_menu, self.t("settings"))
        self.menu_bar.Append(self.help_menu, self.t("menu_help"))
        self.SetMenuBar(self.menu_bar)

    def create_controls(self):
        """Create all sidebar controls."""
        self.cycles_label = wx.StaticText(self, wx.ID_ANY, self.t("cycles"))
        self.cycles_spin = wx.SpinCtrl(
            self, wx.ID_ANY, min=0, max=100000, initial=10
        )
        self.run_button = wx.Button(self, wx.ID_ANY, self.t("run"))
        self.continue_button = wx.Button(
            self, wx.ID_ANY, self.t("continue")
        )
        self.step_button = wx.Button(self, wx.ID_ANY, self.t("step"))
        self.auto_run_button = wx.ToggleButton(
            self, wx.ID_ANY, self.t("auto_run")
        )
        self.speed_label = wx.StaticText(
            self, wx.ID_ANY, self.t("auto_speed")
        )
        self.speed_slider = wx.Slider(
            self, wx.ID_ANY, value=5, minValue=1, maxValue=10
        )
        self.readings_list = wx.ListBox(self, wx.ID_ANY, size=(230, 160))
        self.log_entries = []
        self.log_text = wx.TextCtrl(
            self,
            wx.ID_ANY,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            size=(-1, 72),
        )
        self.log_text.SetFont(
            wx.Font(
                9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL
            )
        )
        self.log_text.SetBackgroundColour(wx.Colour(250, 251, 253))
        self.canvas.SetMinSize(self.canvas.minimum_visual_size())
        self.readings_list.SetMinSize((230, 100))
        self.log_text.SetMinSize((230, 120))

        self.switch_choice = wx.Choice(self, wx.ID_ANY)
        self.switch_value = wx.RadioBox(
            self,
            wx.ID_ANY,
            self.t("value"),
            choices=["0", "1"],
            majorDimension=2,
            style=wx.RA_SPECIFY_COLS,
        )
        self.set_switch_button = wx.Button(
            self, wx.ID_ANY, self.t("set_switch")
        )

        self.add_monitor_label = wx.StaticText(
            self, wx.ID_ANY, self.t("available_signals")
        )
        self.add_monitor_choice = wx.Choice(self, wx.ID_ANY)
        self.add_monitor_button = wx.Button(
            self, wx.ID_ANY, self.t("add_monitor")
        )

        self.remove_monitor_label = wx.StaticText(
            self, wx.ID_ANY, self.t("current_monitors")
        )
        self.remove_monitor_choice = wx.Choice(self, wx.ID_ANY)
        self.remove_monitor_button = wx.Button(
            self, wx.ID_ANY, self.t("remove_monitor")
        )

        self.reset_view_button = wx.Button(
            self, wx.ID_ANY, self.t("reset_view")
        )
        self.fit_label = wx.StaticText(self, wx.ID_ANY, self.t("fit"))
        self.circuit_fit_button = wx.Button(
            self, wx.ID_ANY, self.t("maximise_circuit")
        )
        self.scope_fit_button = wx.Button(
            self, wx.ID_ANY, self.t("maximise_scope")
        )
        self.trace_display_label = wx.StaticText(
            self, wx.ID_ANY, self.t("trace_display")
        )
        self.trace_display_button = wx.ToggleButton(
            self, wx.ID_ANY, self.t("trace_display_3d")
        )
        self.circuit_3d_button = wx.ToggleButton(
            self, wx.ID_ANY, self.t("circuit_3d")
        )
        self.maximise_label = wx.StaticText(
            self, wx.ID_ANY, self.t("maximise")
        )
        self.maximise_circuit_button = wx.ToggleButton(
            self, wx.ID_ANY, self.t("maximise_circuit")
        )
        self.maximise_scope_button = wx.ToggleButton(
            self, wx.ID_ANY, self.t("maximise_scope")
        )

    def configure_layout(self):
        """Arrange canvas and controls in sizers."""
        root_sizer = wx.BoxSizer(wx.VERTICAL)
        run_toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        display_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.VERTICAL)

        self.side_panel = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.side_panel.SetScrollRate(0, 12)
        self.side_panel.SetMinSize((288, 240))
        self.switch_box = wx.StaticBox(
            self.side_panel, label=self.t("switches")
        )
        self.monitor_box = wx.StaticBox(
            self.side_panel, label=self.t("monitors")
        )
        self.view_box = wx.StaticBox(self.side_panel, label=self.t("view"))
        self.readings_box = wx.StaticBox(
            self.side_panel, label=self.t("readings")
        )
        self.log_box = wx.StaticBox(self.side_panel, label=self.t("log"))
        self.reparent_side_panel_controls()
        self.match_control_widths(
            [self.add_monitor_button, self.remove_monitor_button]
        )
        switch_box = wx.StaticBoxSizer(self.switch_box, wx.VERTICAL)
        monitor_box = wx.StaticBoxSizer(self.monitor_box, wx.VERTICAL)
        view_box = wx.StaticBoxSizer(self.view_box, wx.VERTICAL)
        readings_box = wx.StaticBoxSizer(self.readings_box, wx.VERTICAL)
        log_box = wx.StaticBoxSizer(self.log_box, wx.VERTICAL)

        run_toolbar_sizer.Add(self.cycles_label, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        run_toolbar_sizer.Add(self.cycles_spin, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        run_toolbar_sizer.Add(self.run_button, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        run_toolbar_sizer.Add(self.continue_button, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        run_toolbar_sizer.Add(self.step_button, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        run_toolbar_sizer.Add(self.auto_run_button, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        run_toolbar_sizer.Add(self.speed_label, 0,
                              wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        run_toolbar_sizer.Add(
            self.speed_slider, 1,
            wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 10
        )

        switch_row = wx.BoxSizer(wx.HORIZONTAL)
        switch_row.Add(self.switch_choice, 1,
                       wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        switch_row.Add(self.switch_value, 0, wx.EXPAND)
        switch_box.Add(switch_row, 0, wx.EXPAND | wx.ALL, 6)
        switch_box.Add(self.set_switch_button, 0, wx.EXPAND | wx.ALL, 6)

        add_monitor_row = wx.BoxSizer(wx.HORIZONTAL)
        add_monitor_row.Add(self.add_monitor_choice, 1,
                            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        add_monitor_row.Add(self.add_monitor_button, 0,
                            wx.ALIGN_CENTER_VERTICAL)
        remove_monitor_row = wx.BoxSizer(wx.HORIZONTAL)
        remove_monitor_row.Add(self.remove_monitor_choice, 1,
                               wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        remove_monitor_row.Add(self.remove_monitor_button, 0,
                               wx.ALIGN_CENTER_VERTICAL)
        monitor_box.Add(self.add_monitor_label, 0,
                        wx.TOP | wx.LEFT | wx.RIGHT, 6)
        monitor_box.Add(add_monitor_row, 0, wx.EXPAND | wx.ALL, 6)
        monitor_box.Add(self.remove_monitor_label, 0,
                        wx.TOP | wx.LEFT | wx.RIGHT, 6)
        monitor_box.Add(remove_monitor_row, 0, wx.EXPAND | wx.ALL, 6)
        monitor_box.Add(self.reset_view_button, 0, wx.EXPAND | wx.ALL, 6)

        maximise_sizer = wx.BoxSizer(wx.HORIZONTAL)
        maximise_sizer.Add(self.maximise_circuit_button, 1,
                           wx.EXPAND | wx.RIGHT, 4)
        maximise_sizer.Add(self.maximise_scope_button, 1, wx.EXPAND)
        fit_sizer = wx.BoxSizer(wx.HORIZONTAL)
        fit_sizer.Add(self.circuit_fit_button, 1, wx.EXPAND | wx.RIGHT, 4)
        fit_sizer.Add(self.scope_fit_button, 1, wx.EXPAND)
        view_box.Add(self.maximise_label, 0, wx.TOP | wx.LEFT | wx.RIGHT, 6)
        view_box.Add(maximise_sizer, 0, wx.EXPAND | wx.ALL, 6)
        view_box.Add(self.fit_label, 0, wx.TOP | wx.LEFT | wx.RIGHT, 6)
        view_box.Add(fit_sizer, 0, wx.EXPAND | wx.ALL, 6)
        trace_3d_sizer = wx.BoxSizer(wx.HORIZONTAL)
        trace_3d_sizer.Add(self.circuit_3d_button, 1,
                           wx.EXPAND | wx.RIGHT, 4)
        trace_3d_sizer.Add(self.trace_display_button, 1, wx.EXPAND)
        view_box.Add(self.trace_display_label, 0,
                     wx.LEFT | wx.RIGHT, 6)
        view_box.Add(trace_3d_sizer, 0, wx.EXPAND | wx.ALL, 6)

        readings_box.Add(self.readings_list, 1, wx.EXPAND | wx.ALL, 6)
        log_box.Add(self.log_text, 1, wx.EXPAND | wx.ALL, 6)

        side_sizer.Add(switch_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(monitor_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(view_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(readings_box, 1, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(log_box, 1, wx.EXPAND | wx.ALL, 6)

        display_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 6)

        self.side_panel.SetSizer(side_sizer)

        main_sizer.Add(display_sizer, 1, wx.EXPAND)
        main_sizer.Add(self.side_panel, 0, wx.EXPAND | wx.ALL, 6)
        root_sizer.Add(run_toolbar_sizer, 0, wx.EXPAND | wx.ALL, 6)
        root_sizer.Add(main_sizer, 1, wx.EXPAND)
        self.SetSizer(root_sizer)

    def match_control_widths(self, controls):
        """Give related controls one shared width so rows line up."""
        for control in controls:
            control.SetMinSize((-1, -1))
        width = max(control.GetBestSize().width for control in controls)
        for control in controls:
            control.SetMinSize((width, -1))

    def reparent_side_panel_controls(self):
        """Make side-panel widgets children of their native group boxes."""
        for control in [
            self.switch_choice, self.switch_value,
            self.set_switch_button,
        ]:
            control.Reparent(self.switch_box)

        for control in [
            self.add_monitor_label, self.add_monitor_choice,
            self.add_monitor_button, self.remove_monitor_label,
            self.remove_monitor_choice, self.remove_monitor_button,
            self.reset_view_button,
        ]:
            control.Reparent(self.monitor_box)

        for control in [
            self.maximise_label, self.maximise_circuit_button,
            self.maximise_scope_button,
            self.fit_label, self.circuit_fit_button, self.scope_fit_button,
            self.trace_display_label, self.trace_display_button,
            self.circuit_3d_button,
        ]:
            control.Reparent(self.view_box)

        self.readings_list.Reparent(self.readings_box)
        self.log_text.Reparent(self.log_box)

    def bind_events(self):
        """Bind widget events to handlers."""
        self.Bind(wx.EVT_MENU, self.on_menu)
        self.Bind(wx.EVT_TIMER, self.on_auto_timer, self.auto_timer)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.run_button.Bind(wx.EVT_BUTTON, self.on_run_button)
        self.continue_button.Bind(wx.EVT_BUTTON, self.on_continue_button)
        self.step_button.Bind(wx.EVT_BUTTON, self.on_step_button)
        self.auto_run_button.Bind(wx.EVT_TOGGLEBUTTON,
                                  self.on_auto_run_button)
        self.speed_slider.Bind(wx.EVT_SLIDER, self.on_speed_slider)
        self.set_switch_button.Bind(wx.EVT_BUTTON, self.on_set_switch_button)
        self.add_monitor_button.Bind(wx.EVT_BUTTON, self.on_add_monitor_button)
        self.remove_monitor_button.Bind(
            wx.EVT_BUTTON, self.on_remove_monitor_button
        )
        self.reset_view_button.Bind(wx.EVT_BUTTON, self.on_reset_view_button)
        self.circuit_fit_button.Bind(
            wx.EVT_BUTTON, lambda event: self.on_circuit_fit()
        )
        self.scope_fit_button.Bind(
            wx.EVT_BUTTON, lambda event: self.on_scope_fit()
        )
        self.trace_display_button.Bind(
            wx.EVT_TOGGLEBUTTON, self.on_trace_display_button
        )
        self.circuit_3d_button.Bind(
            wx.EVT_TOGGLEBUTTON, self.on_circuit_3d_button
        )
        self.maximise_circuit_button.Bind(
            wx.EVT_TOGGLEBUTTON, self.on_maximise_circuit_button
        )
        self.maximise_scope_button.Bind(
            wx.EVT_TOGGLEBUTTON, self.on_maximise_scope_button
        )

    def on_circuit_fit(self):
        """Fit the whole circuit overview into the viewport."""
        self.canvas.fit_circuit()
        self.set_status(self.t("circuit_overview_fitted"))

    def on_scope_fit(self):
        """Fit every monitor row and cycle into the oscilloscope."""
        self.canvas.fit_scope()
        self.set_status(self.t("scope_fitted"))

    def on_trace_display_button(self, event):
        """Switch between the 2D and 3D signal trace displays."""
        enabled = self.trace_display_button.GetValue()
        self.canvas.set_trace_display_3d(enabled)
        if enabled:
            self.set_status(self.t("trace_display_3d_enabled"))
        else:
            self.set_status(self.t("trace_display_2d_enabled"))

    def on_circuit_3d_button(self, event):
        """Switch the circuit overview between 2D and 3D."""
        enabled = self.circuit_3d_button.GetValue()
        self.canvas.set_circuit_display_3d(enabled)
        if enabled:
            self.set_status(self.t("circuit_3d_enabled"))
        else:
            self.set_status(self.t("circuit_3d_disabled"))

    def on_maximise_circuit_button(self, event):
        """Maximise the circuit overview, or restore the split view."""
        if self.maximise_circuit_button.GetValue():
            self.maximise_scope_button.SetValue(False)
            self.apply_view_mode("circuit")
        else:
            self.apply_view_mode("split")

    def on_maximise_scope_button(self, event):
        """Maximise the oscilloscope, or restore the split view."""
        if self.maximise_scope_button.GetValue():
            self.maximise_circuit_button.SetValue(False)
            self.apply_view_mode("scope")
        else:
            self.apply_view_mode("split")

    def apply_view_mode(self, mode):
        """Switch the canvas layout and report the active view."""
        self.maximise_circuit_button.SetValue(mode == "circuit")
        self.maximise_scope_button.SetValue(mode == "scope")
        self.canvas.set_view_mode(mode)
        messages = {
            "split": "view_mode_split",
            "circuit": "view_mode_circuit",
            "scope": "view_mode_scope",
        }
        self.set_status(self.t(messages[mode]))

    def on_menu(self, event):
        """Handle menu events."""
        event_id = event.GetId()
        if event_id == wx.ID_EXIT:
            self.stop_auto_run()
            self.Close(True)
        elif event_id == wx.ID_OPEN:
            self.defer_menu_action(self.on_open_file)
        elif event_id == wx.ID_SAVEAS:
            self.defer_menu_action(self.on_save_file)
        elif event_id == int(self.export_circuit_menu_id):
            self.defer_menu_action(self.on_export_circuit)
        elif event_id == int(self.export_scope_menu_id):
            self.defer_menu_action(self.on_export_scope)
        elif event_id == int(self.help_menu_id):
            self.defer_menu_action(self.on_help)
        elif event_id == wx.ID_ABOUT:
            self.defer_menu_action(self.on_about)
        elif event_id == self.dark_mode_menu_item.GetId():
            self.on_dark_mode_button()
        elif event_id == self.colour_blind_menu_item.GetId():
            self.on_colour_blind_button()
        elif event_id in self.language_menu_codes:
            self.set_language(self.language_menu_codes[event_id])

    def defer_menu_action(self, action):
        """Run a dialog-opening menu action after the menu fully closes.

        Opening a dialog straight from the menu event races the menu
        teardown on slow compositors (WSLg renders over RDP): the dialog
        can map before the frame regains focus and end up stacked behind
        it.  A short delay lets the dismissal finish first.
        """
        wx.CallLater(120, action)

    def show_dialog_raised(self, dialog):
        """Show a modal dialog and keep it in front of the main frame.

        On WSLg desktops a freshly opened dialog can stack behind the
        main window until the user switches apps.  The keep-above window
        hint is honoured there where a plain raise is ignored as focus
        stealing, so apply it before showing; the raise timers (which
        fire inside the modal loop) remain as a fallback.
        """
        self.keep_dialog_above(dialog)
        raisers = [
            wx.CallLater(250, self.raise_window, dialog),
            wx.CallLater(700, self.raise_window, dialog),
        ]
        try:
            return dialog.ShowModal()
        finally:
            for raiser in raisers:
                raiser.Stop()

    def keep_dialog_above(self, dialog):
        """Ask the window manager to keep a dialog above other windows.

        WSLg translates the keep-above hint into a Windows topmost flag,
        which sidesteps its dialog-stacking bug.  Adding wxSTAY_ON_TOP
        through SetWindowStyleFlag makes wxWidgets apply the hint to the
        dialog's GTK window even for native dialogs, whose creation path
        ignores the flag.
        """
        if not sys.platform.startswith("linux"):
            return
        dialog.SetWindowStyleFlag(
            dialog.GetWindowStyleFlag() | wx.STAY_ON_TOP
        )

    def raise_window(self, window):
        """Bring a window to the front if it still exists.

        Re-applies the keep-above hint first: the generic message
        dialog only creates its real window inside ShowModal (with a
        fixed style), so a hint set beforehand is lost; by the time
        this timer fires the window exists and the change sticks.
        """
        if window:
            self.keep_dialog_above(window)
            window.Raise()

    def show_message_raised(self, message, caption, style):
        """Show a message dialog that recovers from stacking races.

        The generic (wx-drawn) message dialog is used because the native
        one only creates its window inside ShowModal, too late for the
        keep-above hint that stops WSLg hiding it behind the frame.
        """
        with wx.GenericMessageDialog(self, message, caption, style) as dlg:
            self.show_dialog_raised(dlg)

    def set_language(self, language_code):
        """Switch visible GUI labels to the selected language."""
        if language_code not in self.translations:
            return

        self.current_language = language_code
        for item_id, code in self.language_menu_codes.items():
            if code == language_code:
                self.language_menu.Check(item_id, True)
        self.canvas.set_translator(self.t)
        self.update_language_labels()
        self.set_status(self.t("language_changed"))

    def on_dark_mode_button(self):
        """Toggle between light and dark interface themes."""
        self.dark_mode = not self.dark_mode
        self.dark_mode_menu_item.Check(self.dark_mode)
        self.apply_theme()
        if self.dark_mode:
            self.set_status(self.t("dark_mode_enabled"))
        else:
            self.set_status(self.t("light_mode_enabled"))

    def on_colour_blind_button(self):
        """Toggle colour-blind-safe signal colours."""
        self.colour_blind_mode = not self.colour_blind_mode
        self.colour_blind_menu_item.Check(self.colour_blind_mode)
        self.apply_theme()
        if self.colour_blind_mode:
            self.set_status(self.t("colour_blind_enabled"))
        else:
            self.set_status(self.t("colour_blind_disabled"))

    def update_language_labels(self):
        """Apply the current language to visible menus and controls."""
        self.SetTitle(self.t("window_title"))
        self.menu_bar.SetMenuLabel(0, self.t("menu_file"))
        self.menu_bar.SetMenuLabel(1, self.t("settings"))
        self.menu_bar.SetMenuLabel(2, self.t("menu_help"))
        self.open_menu_item.SetItemLabel(self.t("menu_open"))
        self.save_menu_item.SetItemLabel(self.t("menu_save"))
        self.export_circuit_menu_item.SetItemLabel(
            self.t("menu_export_circuit")
        )
        self.export_scope_menu_item.SetItemLabel(
            self.t("menu_export_scope")
        )
        self.exit_menu_item.SetItemLabel(self.t("menu_exit"))
        self.language_menu_item.SetItemLabel(self.t("language"))
        self.dark_mode_menu_item.SetItemLabel(self.t("dark_mode"))
        self.colour_blind_menu_item.SetItemLabel(
            self.t("colour_blind_mode")
        )
        self.help_menu_item.SetItemLabel(self.t("menu_help_item"))
        self.about_menu_item.SetItemLabel(self.t("menu_about"))

        self.cycles_label.SetLabel(self.t("cycles"))
        self.run_button.SetLabel(self.t("run"))
        self.continue_button.SetLabel(self.t("continue"))
        self.step_button.SetLabel(self.t("step"))
        self.auto_run_button.SetLabel(self.t("auto_run"))
        self.speed_label.SetLabel(self.t("auto_speed"))

        self.switch_box.SetLabel(self.t("switches"))
        self.monitor_box.SetLabel(self.t("monitors"))
        self.view_box.SetLabel(self.t("view"))
        self.readings_box.SetLabel(self.t("readings"))
        self.log_box.SetLabel(self.t("log"))
        self.switch_value.SetLabel(self.t("value"))
        self.set_switch_button.SetLabel(self.t("set_switch"))
        self.add_monitor_label.SetLabel(self.t("available_signals"))
        self.add_monitor_button.SetLabel(self.t("add_monitor"))
        self.remove_monitor_label.SetLabel(self.t("current_monitors"))
        self.remove_monitor_button.SetLabel(self.t("remove_monitor"))
        self.reset_view_button.SetLabel(self.t("reset_view"))
        self.fit_label.SetLabel(self.t("fit"))
        self.circuit_fit_button.SetLabel(self.t("maximise_circuit"))
        self.scope_fit_button.SetLabel(self.t("maximise_scope"))
        self.trace_display_label.SetLabel(self.t("trace_display"))
        self.trace_display_button.SetLabel(self.t("trace_display_3d"))
        self.circuit_3d_button.SetLabel(self.t("circuit_3d"))
        self.maximise_label.SetLabel(self.t("maximise"))
        self.maximise_circuit_button.SetLabel(self.t("maximise_circuit"))
        self.maximise_scope_button.SetLabel(self.t("maximise_scope"))
        self.match_control_widths(
            [self.add_monitor_button, self.remove_monitor_button]
        )
        self.canvas.set_translator(self.t)
        self.apply_theme()
        self.Layout()

    def on_close(self, event):
        """Stop background timers before closing the window."""
        self.stop_auto_run()
        event.Skip()

    def on_run_button(self, event):
        """Run the simulation from a cold start."""
        self.stop_auto_run()
        self.clear_removed_default_traces()
        self.canvas.follow_latest_cycles = True
        success, message = self.controller.run_from_start(
            self.cycles_spin.GetValue()
        )
        self.after_action(success, message)

    def on_continue_button(self, event):
        """Continue a previous simulation."""
        self.stop_auto_run()
        self.canvas.follow_latest_cycles = True
        success, message = self.controller.continue_simulation(
            self.cycles_spin.GetValue()
        )
        self.after_action(success, message)

    def on_step_button(self, event):
        """Run exactly one simulation cycle."""
        self.stop_auto_run()
        success, message = self.controller.step_simulation()
        self.after_action(success, message)

    def on_auto_run_button(self, event):
        """Start or stop continuous simulation."""
        if self.auto_run_button.GetValue():
            self.canvas.follow_latest_cycles = True
            self.auto_timer.Start(self.get_auto_delay())
            self.set_status(self.t("auto_run_started"))
        else:
            self.stop_auto_run()
            self.set_status(self.t("auto_run_stopped"))

    def on_auto_timer(self, event):
        """Advance one cycle whenever the auto-run timer fires."""
        success, message = self.controller.step_simulation()
        self.refresh_choices()
        self.canvas.Refresh()
        if success:
            self.set_status(message)
        else:
            self.stop_auto_run()
            self.set_status(message, error=True)

    def on_speed_slider(self, event):
        """Update the auto-run timer interval."""
        if self.auto_timer.IsRunning():
            self.auto_timer.Start(self.get_auto_delay())

    def get_auto_delay(self):
        """Return timer delay in milliseconds from the speed slider."""
        speed = self.speed_slider.GetValue()
        return max(50, 1050 - speed * 100)

    def stop_auto_run(self):
        """Stop continuous running if it is active."""
        if self.auto_timer.IsRunning():
            self.auto_timer.Stop()
        if self.auto_run_button.GetValue():
            self.auto_run_button.SetValue(False)

    def on_set_switch_button(self, event):
        """Set the selected switch to the selected value."""
        switch_name = self.get_choice_value(self.switch_choice)
        if switch_name is None:
            self.after_action(False, self.t("no_switch_selected"))
            return

        success, message = self.controller.set_switch(
            switch_name, self.switch_value.GetStringSelection()
        )
        self.after_action(success, message)

    def on_add_monitor_button(self, event):
        """Add the selected signal as a monitor."""
        signal_name = self.get_choice_value(self.add_monitor_choice)
        if signal_name is None:
            self.after_action(False, self.t("no_available_signal_selected"))
            return

        success, message = self.controller.add_monitor(signal_name)
        self.after_action(success, message)

    def on_remove_monitor_button(self, event):
        """Remove the selected monitor."""
        signal_name = self.get_choice_value(self.remove_monitor_choice)
        if signal_name is None:
            self.after_action(False, self.t("no_current_monitor_selected"))
            return

        self.archive_default_monitor(signal_name)
        success, message = self.controller.remove_monitor(signal_name)
        self.after_action(success, message)

    def on_reset_view_button(self, event):
        """Restore the default monitor view and reset canvas pan and zoom."""
        self.restore_default_monitors()
        self.refresh_choices()
        self.canvas.reset_view()
        self.set_status(self.t("view_reset"))

    def on_open_file(self):
        """Load and parse a new definition file selected by the user."""
        with wx.FileDialog(
            self,
            self.t("open_dialog_title"),
            wildcard=self.t("definition_file_wildcard"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if self.show_dialog_raised(dialog) == wx.ID_CANCEL:
                return
            path = dialog.GetPath()

        self.load_definition_file(path)

    def on_save_file(self):
        """Save a copy of the currently loaded definition file."""
        default_dir = os.path.dirname(self.path)
        default_file = os.path.basename(self.path)

        with wx.FileDialog(
            self,
            self.t("save_dialog_title"),
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard=self.t("definition_file_wildcard"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if self.show_dialog_raised(dialog) == wx.ID_CANCEL:
                return
            save_path = dialog.GetPath()

        try:
            if os.path.abspath(save_path) != os.path.abspath(self.path):
                shutil.copyfile(self.path, save_path)
            self.set_status(self.format_text("saved_file", path=save_path))
        except OSError as error:
            self.show_message_raised(
                self.format_text("file_save_error_body", error=error),
                self.t("file_save_error_title"),
                wx.OK | wx.ICON_ERROR,
            )
            self.set_status(self.t("file_save_failed"), error=True)

    def on_export_circuit(self):
        """Export the current circuit overview to an image or PDF."""
        default_dir = os.path.dirname(self.path)
        base_name = os.path.splitext(os.path.basename(self.path))[0]
        export_path = self.choose_export_path(
            self.t("export_circuit_dialog_title"),
            default_dir,
            base_name + "_circuit.png",
        )
        if export_path is None:
            return

        try:
            if self.canvas.save_circuit_image(export_path):
                self.set_status(
                    self.format_text("exported_circuit", path=export_path)
                )
            else:
                self.set_status(self.t("export_circuit_failed"), error=True)
        except Exception as error:
            self.show_message_raised(
                self.format_text("circuit_export_error_body", error=error),
                self.t("circuit_export_error_title"),
                wx.OK | wx.ICON_ERROR,
            )
            self.set_status(self.t("export_circuit_failed"), error=True)

    def on_export_scope(self):
        """Export the current oscilloscope view to an image or PDF."""
        default_dir = os.path.dirname(self.path)
        base_name = os.path.splitext(os.path.basename(self.path))[0]
        export_path = self.choose_export_path(
            self.t("export_scope_dialog_title"),
            default_dir,
            base_name + "_oscilloscope.png",
        )
        if export_path is None:
            return

        try:
            if self.canvas.save_scope_image(export_path):
                self.set_status(
                    self.format_text("exported_scope", path=export_path)
                )
            else:
                self.set_status(self.t("export_scope_failed"), error=True)
        except Exception as error:
            self.show_message_raised(
                self.format_text("scope_export_error_body", error=error),
                self.t("scope_export_error_title"),
                wx.OK | wx.ICON_ERROR,
            )
            self.set_status(self.t("export_scope_failed"), error=True)

    def choose_export_path(self, title, default_dir, default_file):
        """Return a PNG or PDF path selected by the user."""
        with wx.FileDialog(
            self,
            title,
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard=self.t("export_file_wildcard"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if self.show_dialog_raised(dialog) == wx.ID_CANCEL:
                return None
            export_path = dialog.GetPath()
            filter_index = dialog.GetFilterIndex()

        _, extension = os.path.splitext(export_path)
        extension = extension.lower()
        if extension not in [".png", ".pdf"]:
            if filter_index == 1:
                export_path += ".pdf"
            else:
                export_path += ".png"

        return export_path

    def load_definition_file(self, path):
        """Replace the current simulator state with a parsed file."""
        self.stop_auto_run()
        names = Names()
        devices = Devices(names)
        network = Network(names, devices)
        monitors = Monitors(names, devices, network)
        scanner = Scanner(path, names)
        parser = Parser(names, devices, network, monitors, scanner)

        success, diagnostics = parse_network_with_diagnostics(parser)
        if not success:
            show_parse_error_dialog(self, path, diagnostics)
            return

        self.path = path
        self.controller = GuiController(names, devices, network, monitors)
        self.canvas.devices = devices
        self.canvas.monitors = monitors
        self.canvas.reset_view()
        self.remember_default_monitors()
        self.refresh_choices()
        self.set_status(self.format_text("loaded_file", path=path))

    def on_help(self):
        """Display a concise user guide."""
        self.show_message_raised(
            self.t("help_text"),
            self.t("help_title"),
            wx.OK | wx.ICON_INFORMATION,
        )

    def on_about(self):
        """Display application information."""
        self.show_message_raised(
            self.t("about_text"),
            self.t("about_title"),
            wx.OK | wx.ICON_INFORMATION,
        )

    def after_action(self, success, message):
        """Refresh state after a user action."""
        self.refresh_choices()
        self.canvas.Refresh()
        self.set_status(message, error=not success)

    def refresh_choices(self):
        """Refresh switch, monitor, and reading controls."""
        self.populate_choice(
            self.switch_choice, self.controller.list_switches()
        )
        self.populate_choice(
            self.add_monitor_choice,
            self.controller.list_unmonitored_signals(),
        )
        self.populate_choice(
            self.remove_monitor_choice,
            self.controller.list_monitored_signals(),
        )
        self.refresh_readings()

    def refresh_readings(self):
        """Refresh the live device output readings list."""
        self.readings_list.Clear()
        readings = self.controller.list_device_readings()
        if readings:
            self.readings_list.AppendItems(readings)

    def populate_choice(self, choice, values):
        """Populate a wx.Choice while preserving selection where possible."""
        old_selection = choice.GetStringSelection()
        choice.Clear()
        if values:
            choice.AppendItems(values)
            if old_selection in values:
                choice.SetStringSelection(old_selection)
            else:
                choice.SetSelection(0)

    def get_choice_value(self, choice):
        """Return the selected choice string, or None."""
        selection = choice.GetStringSelection()
        if selection == "":
            return None
        return selection

    def remember_default_monitors(self):
        """Remember the monitor points that were present when a file loaded."""
        monitor_items = self.controller.monitors.monitors_dictionary.items()
        self.default_monitor_keys = [key for key, _ in monitor_items]
        self.default_monitor_traces = {
            key: list(trace) for key, trace in monitor_items
        }

    def archive_default_monitor(self, signal_name):
        """Keep a removable default monitor trace available for Reset View."""
        signal_ids = self.controller.get_existing_signal_ids(signal_name)
        if signal_ids not in self.default_monitor_keys:
            return

        traces = self.controller.monitors.monitors_dictionary
        if signal_ids in traces:
            self.default_monitor_traces[signal_ids] = list(traces[signal_ids])

    def restore_default_monitors(self):
        """Restore the monitor set that was present when the file loaded."""
        if not self.default_monitor_keys:
            return

        traces = self.controller.monitors.monitors_dictionary
        restored_traces = []
        for key in self.default_monitor_keys:
            if key in traces:
                restored_trace = list(traces[key])
            else:
                restored_trace = list(self.default_monitor_traces.get(key, []))

            if len(restored_trace) < self.controller.cycles_completed:
                restored_trace.extend(
                    [self.controller.devices.BLANK]
                    * (self.controller.cycles_completed - len(restored_trace))
                )

            restored_traces.append((key, list(restored_trace)))

        traces.clear()
        for key, trace in restored_traces:
            traces[key] = trace

        self.default_monitor_traces = dict(restored_traces)

    def clear_removed_default_traces(self):
        """Clear archived traces for monitors absent before a new run."""
        traces = self.controller.monitors.monitors_dictionary
        for key in self.default_monitor_keys:
            if key not in traces:
                self.default_monitor_traces[key] = []

    def set_status(self, message, error=False):
        """Show a status message to the user."""
        prefix = self.t("error_prefix") + ": " if error else ""
        status_text = (
            prefix + message + "\n" + self.t("cycles_completed") + ": "
            + str(self.controller.cycles_completed)
        )
        self.SetStatusText(
            self.t("status_prefix") + ": "
            + status_text.replace("\n", "  |  ")
        )
        self.append_log(prefix + message)

    def append_log(self, message):
        """Append one message to the scrolling simulator log."""
        if not hasattr(self, "log_text"):
            return

        cycle_text = str(self.controller.cycles_completed)
        self.log_entries.append(
            "[" + cycle_text.rjust(4) + "] " + str(message)
        )
        if len(self.log_entries) > 300:
            self.log_entries = self.log_entries[-300:]

        self.log_text.ChangeValue("\n".join(self.log_entries))
        # Land on the START of the newest line: the view stays pinned to
        # the bottom but the horizontal scroll rests at the left, so each
        # new entry is read from its beginning.
        last_line_start = (
            self.log_text.GetLastPosition() - len(self.log_entries[-1])
        )
        self.log_text.SetInsertionPoint(max(last_line_start, 0))
        self.log_text.ShowPosition(max(last_line_start, 0))
