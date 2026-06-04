"""Implement the graphical user interface for the Logic Simulator.

The GUI mirrors the required command-line operations: run, continue, set a
switch, add a monitor, and remove a monitor.  Signal traces are drawn in an
OpenGL canvas and can be panned or zoomed with the mouse.
"""

import math
import os
import shutil
import zlib

import wx
import wx.glcanvas as wxcanvas
from OpenGL import GL, GLUT

from names import Names
from devices import Devices
from network import Network
from monitors import Monitors
from scanner import Scanner
from parse import Parser
from gui_controller import GuiController


class MyGLCanvas(wxcanvas.GLCanvas):
    """Draw monitor waveforms in an OpenGL canvas."""

    def __init__(self, parent, devices, monitors):
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

        self.pan_x = 0
        self.pan_y = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.zoom = 1.0
        self.circuit_scroll_x = 0
        self.circuit_scroll_y = 0
        self.circuit_drag_mode = None
        self.circuit_drag_offset = 0
        self.circuit_geometry = {}
        self.scope_first_cycle = 0
        self.scope_first_row = 0
        self.scope_drag_mode = None
        self.scope_drag_offset = 0
        self.scope_geometry = {}
        self.follow_latest_cycles = True
        self.dark_mode = False
        self.colour_blind_mode = False
        self.last_circuit_bounds = None
        self.last_scope_bounds = None

        self.left_margin = 150
        self.default_cycle_width = 28
        self.cycle_width = self.default_cycle_width
        self.row_height = 34
        self.high_offset = 18
        self.low_offset = 4
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

    def reset_view(self):
        """Reset pan, zoom, and oscilloscope scroll to their defaults."""
        self.pan_x = 0
        self.pan_y = 0
        self.zoom = 1.0
        self.circuit_scroll_x = 0
        self.circuit_scroll_y = 0
        self.circuit_drag_mode = None
        self.scope_first_cycle = 0
        self.scope_first_row = 0
        self.scope_drag_mode = None
        self.follow_latest_cycles = False
        self.init = False
        self.Refresh()

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
        GL.glViewport(0, 0, size.width, size.height)
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
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glLineWidth(1.0)

        monitor_items = list(self.monitors.monitors_dictionary.items())
        top_margin = 18
        scope_y = 20
        scope_gap = 8
        min_scope_height = 240
        desired_circuit_height = self.estimate_circuit_height()
        max_circuit_height = max(
            160,
            size.height - top_margin - scope_y - scope_gap
            - min_scope_height
        )
        circuit_height = min(desired_circuit_height, max_circuit_height)
        circuit_height = max(160, circuit_height)
        circuit_bounds = (
            18, size.height - circuit_height - top_margin,
            size.width - 36, circuit_height
        )
        scope_bounds = (
            18, scope_y, size.width - 36,
            circuit_bounds[1] - scope_y - scope_gap
        )

        if scope_bounds[3] < min_scope_height:
            scope_bounds = (
                18, scope_y, size.width - 36, min_scope_height
            )
            circuit_y = scope_y + min_scope_height + scope_gap
            circuit_height = max(
                120, size.height - circuit_y - top_margin
            )
            circuit_bounds = (
                18, circuit_y, size.width - 36, circuit_height
            )

        self.last_circuit_bounds = circuit_bounds
        self.draw_canvas_grid(size)
        self.draw_circuit_overview(circuit_bounds)
        self.draw_oscilloscope(scope_bounds, monitor_items)
        self.finish_render(swap)

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
        self.render_text("Circuit overview", x_pos + 10, y_pos + height - 20)

        view_bounds = (x_pos + 10, y_pos + 26, width - 32, height - 64)
        view_x, view_y, view_width, view_height = view_bounds
        if view_width <= 0 or view_height <= 0:
            return

        content_width, content_height = self.circuit_content_size(
            view_width, view_height
        )
        max_scroll_x = max(content_width - view_width, 0)
        max_scroll_y = max(content_height - view_height, 0)
        self.circuit_scroll_x = self.clamp(
            self.circuit_scroll_x, 0, max_scroll_x
        )
        self.circuit_scroll_y = self.clamp(
            self.circuit_scroll_y, 0, max_scroll_y
        )
        content_bounds = (
            view_x - self.circuit_scroll_x,
            view_y + view_height - content_height + self.circuit_scroll_y,
            content_width,
            content_height,
        )
        self.circuit_geometry = {
            "view": view_bounds,
            "content_width": content_width,
            "content_height": content_height,
            "max_scroll_x": max_scroll_x,
            "max_scroll_y": max_scroll_y,
        }

        self.begin_scissor(view_bounds)
        positions = self.build_device_positions(content_bounds)
        self.draw_connections(positions)

        for device in self.devices.devices_list:
            if device.device_id in positions:
                self.draw_device_node(device, positions[device.device_id])
        self.end_scissor()
        self.draw_circuit_scrollbars(view_bounds)

    def build_device_positions(self, bounds):
        """Return a simple layered layout for all devices."""
        x_pos, y_pos, width, height = bounds
        layers = self.calculate_device_layers()
        layer_groups = {}
        for device in self.devices.devices_list:
            layer = layers.get(device.device_id, 1)
            layer_groups.setdefault(layer, []).append(device)

        max_layer = max(layer_groups) if layer_groups else 0
        positions = {}
        longest_name = max(
            len(str(self.devices.names.get_name_string(device.device_id)))
            for device in self.devices.devices_list
        )
        block_width = min(180, max(112, longest_name * 8 + 24))
        block_height = 34
        usable_width = max(width - block_width - 90, 1)
        top_padding = 42
        bottom_padding = 14

        for layer, devices_in_layer in layer_groups.items():
            if max_layer == 0:
                node_x = x_pos + width / 2 - block_width / 2
            else:
                node_x = x_pos + 48 + layer * usable_width / max_layer

            count = len(devices_in_layer)
            available_height = max(
                height - top_padding - bottom_padding - block_height, 1
            )
            for index, device in enumerate(devices_in_layer):
                if count == 1:
                    node_y = y_pos + height / 2 - block_height / 2 - 4
                else:
                    gap = available_height / (count - 1)
                    node_y = (
                        y_pos + bottom_padding
                        + (count - 1 - index) * gap
                    )
                positions[device.device_id] = (
                    node_x, node_y, block_width, block_height
                )

        return positions

    def circuit_content_size(self, view_width, view_height):
        """Return virtual circuit dimensions for large diagrams."""
        layers = self.calculate_device_layers()
        layer_counts = {}
        for device in self.devices.devices_list:
            layer = layers.get(device.device_id, 1)
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        layer_count = max(layer_counts, default=0) + 1
        max_devices_in_layer = max(layer_counts.values(), default=1)
        complex_circuit = (
            len(self.devices.devices_list) > 12
            or layer_count > 5
            or max_devices_in_layer > 6
        )
        if not complex_circuit:
            return view_width, view_height

        longest_name = max(
            len(str(self.devices.names.get_name_string(device.device_id)))
            for device in self.devices.devices_list
        )
        block_width = min(180, max(112, longest_name * 8 + 24))
        block_height = 34
        layer_gap = 118
        row_gap = 18

        content_width = (
            40 + layer_count * block_width
            + max(0, layer_count - 1) * layer_gap
        )
        content_height = (
            42 + max_devices_in_layer * block_height
            + max(0, max_devices_in_layer - 1) * row_gap
        )
        return max(view_width, content_width), max(view_height, content_height)

    def draw_circuit_scrollbars(self, view_bounds):
        """Draw scrollbars for oversized circuit diagrams."""
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
        """Draw wires between connected device ports."""
        for target_device in self.devices.devices_list:
            if target_device.device_id not in positions:
                continue

            input_ids = self.sorted_port_ids(target_device.inputs)
            for input_index, input_id in enumerate(input_ids):
                connected_output = target_device.inputs[input_id]
                if connected_output is None:
                    continue

                source_device_id, output_id = connected_output
                if source_device_id not in positions:
                    continue

                source_device = self.devices.get_device(source_device_id)
                source_pos = positions[source_device_id]
                target_pos = positions[target_device.device_id]
                start = self.output_pin(source_pos, source_device, output_id)
                end = self.input_pin(target_pos, target_device, input_id)
                signal = source_device.outputs.get(output_id)
                self.draw_connection_line(start, end, signal, input_index)

    def draw_connection_line(self, start, end, signal, input_index):
        """Draw one routed circuit wire."""
        x_start, y_start = start
        x_end, y_end = end
        self.set_signal_colour(signal)
        GL.glLineWidth(1.4)
        GL.glBegin(GL.GL_LINE_STRIP)

        if x_end <= x_start:
            route_y = max(y_start, y_end) + 28 + 9 * (input_index % 3)
            GL.glVertex2f(x_start, y_start)
            GL.glVertex2f(x_start + 18, y_start)
            GL.glVertex2f(x_start + 18, route_y)
            GL.glVertex2f(x_end - 18, route_y)
            GL.glVertex2f(x_end - 18, y_end)
            GL.glVertex2f(x_end, y_end)
        else:
            mid_x = (x_start + x_end) / 2
            GL.glVertex2f(x_start, y_start)
            GL.glVertex2f(mid_x, y_start)
            GL.glVertex2f(mid_x, y_end)
            GL.glVertex2f(x_end, y_end)

        GL.glEnd()
        GL.glLineWidth(1.0)

    def draw_device_node(self, device, bounds):
        """Draw one device as a labelled circuit block."""
        x_pos, y_pos, width, height = bounds
        kind = self.devices.names.get_name_string(device.device_kind)
        name = self.devices.names.get_name_string(device.device_id)
        fill_colour = self.device_fill_colour(device)

        max_chars = max(6, int(width / 8) - 1)
        display_name = self.truncate_label(str(name), max_chars)
        display_kind = self.truncate_label(str(kind), max_chars)

        self.draw_rectangle(
            bounds, fill_colour, self.theme_colour("device_border")
        )
        self.render_text(display_name, x_pos + 8, y_pos + height - 14)
        self.render_text(
            display_kind, x_pos + 8, y_pos + 8,
            self.theme_colour("subtle_text")
        )

        for input_id in self.sorted_port_ids(device.inputs):
            pin_x, pin_y = self.input_pin(bounds, device, input_id)
            self.draw_circle(pin_x, pin_y, 3.2, (0.98, 0.98, 0.98))

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
                "No monitor points selected.",
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
        control_y = scope_y + scope_height - title_height - control_height
        plot_height = control_y - plot_y - 8

        max_visible_cycles = max(
            10, int(plot_width // self.default_cycle_width)
        )
        max_cycles = self.max_recorded_cycles(monitor_items)
        if max_cycles == 0:
            cycle_count = min(10, max_visible_cycles)
            first_cycle = 0
            self.scope_first_cycle = 0
            self.cycle_width = plot_width / max(cycle_count, 1)

            total_rows = len(monitor_items)
            visible_rows = min(
                total_rows, max(1, int(plot_height // self.row_height))
            )
            max_first_row = max(total_rows - visible_rows, 0)
            self.scope_first_row = self.clamp(
                self.scope_first_row, 0, max_first_row
            )
            visible_monitor_items = monitor_items[
                self.scope_first_row:self.scope_first_row + visible_rows
            ]

            self.render_text(
                "Press Run to record signal traces.",
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
        visible_rows = min(
            total_rows, max(1, int(plot_height // self.row_height))
        )
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

    def draw_scope_header(self, bounds):
        """Draw the oscilloscope title strip."""
        x_pos, y_pos, width, height = bounds
        header_bounds = (x_pos, y_pos + height - 28, width, 28)
        self.draw_rectangle(
            header_bounds,
            self.theme_colour("scope_header"),
            self.theme_colour("scope_header_border"),
        )
        self.render_text("Oscilloscope", x_pos + 30, y_pos + height - 18)
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

    def draw_scope_rows(self, label_x, plot_x, plot_y, plot_height,
                        monitor_items, first_cycle, cycle_count,
                        first_row):
        """Draw all monitored signal names and waveforms."""
        row_gap = min(44, plot_height / max(len(monitor_items), 1))
        for index, monitor_item in enumerate(monitor_items):
            (device_id, output_id), signal_list = monitor_item
            name = self.devices.get_signal_name(device_id, output_id)
            row_mid = plot_y + plot_height - 18 - index * row_gap
            row_base = row_mid - self.high_offset / 2

            colour_index = first_row + index
            colour = self.trace_colour_for_monitor(
                device_id, output_id, colour_index
            )
            self.set_colour(*colour)
            self.render_text(name, label_x + 14, row_mid - 5, colour)
            self.draw_signal_level_scale(
                plot_x, plot_y, plot_height, row_base, row_gap
            )
            visible_signals = signal_list[
                first_cycle:first_cycle + cycle_count
            ]
            self.draw_digital_signal(plot_x, row_base, visible_signals, colour)

    def draw_signal_level_scale(self, plot_x, plot_y, plot_height, row_base,
                                row_gap):
        """Draw 1/0 scale labels and guide lines for one waveform row."""
        high_y = row_base + self.high_offset
        low_y = row_base + self.low_offset

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
        row_gap = min(44, plot_height / max(len(monitor_items), 1))
        blank_signals = [self.devices.BLANK] * cycle_count
        for index, monitor_item in enumerate(monitor_items):
            (device_id, output_id), _ = monitor_item
            name = self.devices.get_signal_name(device_id, output_id)
            row_mid = plot_y + plot_height - 18 - index * row_gap
            row_base = row_mid - self.high_offset / 2

            colour_index = first_row + index
            colour = self.trace_colour_for_monitor(
                device_id, output_id, colour_index
            )
            self.render_text(name, label_x + 14, row_mid - 5, colour)
            self.draw_signal_level_scale(
                plot_x, plot_y, plot_height, row_base, row_gap
            )
            self.draw_digital_signal(plot_x, row_base, blank_signals, colour)

    def draw_digital_signal(self, plot_x, row_base, signal_list, colour):
        """Draw one digital signal as a continuous square waveform."""
        high_y = row_base + self.high_offset
        low_y = row_base + self.low_offset
        previous_y = None

        for index, signal in enumerate(signal_list):
            x_start = plot_x + index * self.cycle_width
            x_end = x_start + self.cycle_width

            if signal == self.devices.BLANK:
                self.draw_blank_signal(x_start, x_end, row_base)
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

    def draw_blank_signal(self, x_start, x_end, row_base):
        """Draw a blank signal interval for monitors added mid-run."""
        mid_y = row_base + (self.high_offset + self.low_offset) / 2
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
            "Cycles shown: " + str(first_cycle) + "-" + str(last_cycle),
            plot_x + 28, plot_y - 76, self.theme_colour("axis")
        )
        self.render_text(
            "Level", plot_x - 38, plot_y - 76,
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

    def truncate_label(self, label, max_chars):
        """Return a shortened label that fits compact graphics."""
        if label is None:
            return ""
        label = str(label)
        if len(label) <= max_chars:
            return label
        return label[:max_chars - 1] + "."

    def begin_scissor(self, bounds):
        """Clip OpenGL drawing to a canvas-space rectangle."""
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
            return

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
        """Handle panning and zooming with the mouse."""
        size = self.GetClientSize()
        object_x = (event.GetX() - self.pan_x) / self.zoom
        object_y = (size.height - event.GetY() - self.pan_y) / self.zoom
        old_zoom = self.zoom

        if event.ButtonDown():
            self.last_mouse_x = event.GetX()
            self.last_mouse_y = event.GetY()
            if self.start_circuit_scroll_drag(object_x, object_y):
                return
            if self.start_scope_scroll_drag(object_x, object_y):
                return

        if event.Dragging() and self.circuit_drag_mode is not None:
            self.update_circuit_scroll_drag(object_x, object_y)
            self.Refresh()
            return

        if event.Dragging() and self.scope_drag_mode is not None:
            self.update_scope_scroll_drag(object_x, object_y)
            self.Refresh()
            return

        if event.ButtonUp():
            self.circuit_drag_mode = None
            self.scope_drag_mode = None

        if event.Dragging():
            self.pan_x += event.GetX() - self.last_mouse_x
            self.pan_y -= event.GetY() - self.last_mouse_y
            self.last_mouse_x = event.GetX()
            self.last_mouse_y = event.GetY()
            self.init = False
            self.Refresh()

        wheel_rotation = event.GetWheelRotation()
        if wheel_rotation != 0 and self.scroll_circuit_view(
            object_x, object_y, wheel_rotation
        ):
            self.Refresh()
            return

        if wheel_rotation != 0 and self.scroll_scope_rows(
            object_x, object_y, wheel_rotation
        ):
            self.Refresh()
            return

        if wheel_rotation < 0:
            self.zoom *= 1.0 + (
                wheel_rotation / (20 * event.GetWheelDelta())
            )
            self.zoom = max(self.zoom, 0.2)
        elif wheel_rotation > 0:
            self.zoom /= 1.0 - (
                wheel_rotation / (20 * event.GetWheelDelta())
            )
            self.zoom = min(self.zoom, 5.0)

        if wheel_rotation != 0:
            self.pan_x -= (self.zoom - old_zoom) * object_x
            self.pan_y -= (self.zoom - old_zoom) * object_y
            self.init = False
            self.Refresh()

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
        """Update circuit viewport scroll while a scrollbar is dragged."""
        if self.circuit_drag_mode == "vertical":
            track = self.circuit_geometry.get("vertical_track")
            thumb = self.circuit_geometry.get("vertical_thumb")
            max_scroll_y = self.circuit_geometry.get("max_scroll_y", 0)
            if not track or not thumb or max_scroll_y == 0:
                return

            _, track_y, _, track_height = track
            _, _, _, thumb_height = thumb
            usable = max(track_height - thumb_height, 1)
            thumb_y = self.clamp(
                y_pos - self.circuit_drag_offset, track_y, track_y + usable
            )
            fraction = 1 - ((thumb_y - track_y) / usable)
            self.circuit_scroll_y = fraction * max_scroll_y

        if self.circuit_drag_mode == "horizontal":
            track = self.circuit_geometry.get("horizontal_track")
            thumb = self.circuit_geometry.get("horizontal_thumb")
            max_scroll_x = self.circuit_geometry.get("max_scroll_x", 0)
            if not track or not thumb or max_scroll_x == 0:
                return

            track_x, _, track_width, _ = track
            _, _, thumb_width, _ = thumb
            usable = max(track_width - thumb_width, 1)
            thumb_x = self.clamp(
                x_pos - self.circuit_drag_offset, track_x, track_x + usable
            )
            fraction = (thumb_x - track_x) / usable
            self.circuit_scroll_x = fraction * max_scroll_x

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

    def set_colour(self, red, green, blue):
        """Set the OpenGL drawing colour."""
        GL.glColor3f(red, green, blue)


class Gui(wx.Frame):
    """Configure the main GUI window and widgets."""

    def __init__(self, title, path, names, devices, network, monitors):
        """Initialise widgets, controller, and layout."""
        super().__init__(parent=None, title=title, size=(1000, 700))
        self.SetBackgroundColour(wx.Colour(245, 247, 250))

        self.path = path
        self.current_language = "en"
        self.translations = self.build_translations()
        self.dark_mode = False
        self.colour_blind_mode = False
        self.controller = GuiController(names, devices, network, monitors)
        self.default_monitor_keys = []
        self.default_monitor_traces = {}
        self.auto_timer = wx.Timer(self)

        self.configure_menu()
        self.CreateStatusBar()
        self.canvas = MyGLCanvas(self, devices, monitors)
        self.create_controls()
        self.configure_layout()
        self.bind_events()
        self.apply_theme()
        self.remember_default_monitors()
        self.refresh_choices()
        self.set_status("Loaded " + path)

        self.SetSizeHints(760, 520)

    def build_translations(self):
        """Return UI label translations keyed by language code."""
        return {
            "en": {
                "menu_file": "&File",
                "menu_help": "&Help",
                "menu_open": "&Open definition file...",
                "menu_save": "&Save definition as...",
                "menu_export_circuit": "&Export circuit...",
                "menu_export_scope": "&Export oscilloscope...",
                "menu_exit": "&Exit",
                "menu_help_item": "&Help",
                "menu_about": "&About",
                "cycles": "Cycles",
                "run": "Run",
                "continue": "Continue",
                "step": "Step",
                "auto_run": "Auto Run",
                "auto_speed": "Auto speed",
                "open_file": "Open File",
                "save_file": "Save File",
                "export_circuit": "Export Circuit",
                "export_scope": "Export Scope",
                "language": "Language",
                "dark_mode": "Dark Mode",
                "light_mode": "Light Mode",
                "colour_blind_mode": "Colour Blind",
                "standard_colours": "Standard Colours",
                "help": "Help",
                "switches": "Switches",
                "monitors": "Monitors",
                "readings": "Readings",
                "log": "Log",
                "switch": "Switch",
                "value": "Value",
                "set_switch": "Set Switch",
                "available_signals": "Available signals",
                "add_monitor": "Add Monitor",
                "current_monitors": "Current monitors",
                "remove_monitor": "Remove Monitor",
                "reset_view": "Reset View",
                "status_prefix": "Status",
                "language_changed": "Language changed.",
                "dark_mode_enabled": "Dark mode enabled.",
                "light_mode_enabled": "Light mode enabled.",
                "colour_blind_enabled": "Colour-blind mode enabled.",
                "colour_blind_disabled": "Standard colours enabled.",
                "help_title": "Interface Help",
                "about_title": "About Logsim",
                "about_text": (
                    "GF2 Logic Simulator\n"
                    "Graphical interface with circuit overview and "
                    "oscilloscope."
                ),
                "help_text": (
                    "Run: cold-starts the circuit and records N cycles.\n"
                    "Continue: records N more cycles without clearing "
                    "traces.\n"
                    "Step: advances by one cycle.\n"
                    "Auto Run: keeps stepping until you stop it.\n"
                    "Set Switch: changes the selected switch to 0 or 1.\n"
                    "Add/Remove Monitor: controls which outputs are shown.\n"
                    "Mouse drag pans the display; mouse wheel zooms it.\n"
                    "Over the oscilloscope, the mouse wheel scrolls signal "
                    "rows.\n"
                    "File > Open loads another definition file."
                ),
            },
            "fr": {
                "menu_file": "&Fichier",
                "menu_help": "&Aide",
                "menu_open": "&Ouvrir un fichier...",
                "menu_save": "&Enregistrer sous...",
                "menu_export_circuit": "&Exporter le circuit...",
                "menu_export_scope": "&Exporter oscilloscope...",
                "menu_exit": "&Quitter",
                "menu_help_item": "&Aide",
                "menu_about": "&A propos",
                "cycles": "Cycles",
                "run": "Lancer",
                "continue": "Continuer",
                "step": "Pas",
                "auto_run": "Auto",
                "auto_speed": "Vitesse auto",
                "open_file": "Ouvrir",
                "save_file": "Enregistrer",
                "export_circuit": "Exporter circuit",
                "export_scope": "Exporter scope",
                "language": "Langue",
                "dark_mode": "Mode sombre",
                "light_mode": "Mode clair",
                "colour_blind_mode": "Daltonien",
                "standard_colours": "Couleurs standard",
                "help": "Aide",
                "switches": "Interrupteurs",
                "monitors": "Moniteurs",
                "readings": "Lectures",
                "log": "Journal",
                "switch": "Interrupteur",
                "value": "Valeur",
                "set_switch": "Regler interrupteur",
                "available_signals": "Signaux disponibles",
                "add_monitor": "Ajouter moniteur",
                "current_monitors": "Moniteurs actuels",
                "remove_monitor": "Retirer moniteur",
                "reset_view": "Reinitialiser vue",
                "status_prefix": "Statut",
                "language_changed": "Langue modifiee.",
                "dark_mode_enabled": "Mode sombre active.",
                "light_mode_enabled": "Mode clair active.",
                "colour_blind_enabled": "Mode daltonien active.",
                "colour_blind_disabled": "Couleurs standard activees.",
                "help_title": "Aide interface",
                "about_title": "A propos de Logsim",
                "about_text": (
                    "Simulateur logique GF2\n"
                    "Interface graphique avec circuit et oscilloscope."
                ),
                "help_text": (
                    "Lancer: demarre le circuit et enregistre N cycles.\n"
                    "Continuer: ajoute N cycles sans effacer les traces.\n"
                    "Pas: avance d'un cycle.\n"
                    "Auto: avance jusqu'a l'arret.\n"
                    "Regler interrupteur: change un interrupteur a 0 ou 1.\n"
                    "Ajouter/Retirer moniteur: choisit les sorties visibles.\n"
                    "Glisser la souris deplace la vue; la molette zoome.\n"
                    "Sur l'oscilloscope, la molette fait defiler les lignes.\n"
                    "Fichier > Ouvrir charge un autre fichier."
                ),
            },
            "es": {
                "menu_file": "&Archivo",
                "menu_help": "A&yuda",
                "menu_open": "&Abrir archivo...",
                "menu_save": "&Guardar como...",
                "menu_export_circuit": "&Exportar circuito...",
                "menu_export_scope": "&Exportar osciloscopio...",
                "menu_exit": "&Salir",
                "menu_help_item": "A&yuda",
                "menu_about": "&Acerca de",
                "cycles": "Ciclos",
                "run": "Ejecutar",
                "continue": "Continuar",
                "step": "Paso",
                "auto_run": "Auto",
                "auto_speed": "Velocidad",
                "open_file": "Abrir",
                "save_file": "Guardar",
                "export_circuit": "Exportar circuito",
                "export_scope": "Exportar scope",
                "language": "Idioma",
                "dark_mode": "Modo oscuro",
                "light_mode": "Modo claro",
                "colour_blind_mode": "Daltonismo",
                "standard_colours": "Colores estandar",
                "help": "Ayuda",
                "switches": "Interruptores",
                "monitors": "Monitores",
                "readings": "Lecturas",
                "log": "Registro",
                "switch": "Interruptor",
                "value": "Valor",
                "set_switch": "Cambiar interruptor",
                "available_signals": "Senales disponibles",
                "add_monitor": "Agregar monitor",
                "current_monitors": "Monitores actuales",
                "remove_monitor": "Quitar monitor",
                "reset_view": "Reiniciar vista",
                "status_prefix": "Estado",
                "language_changed": "Idioma cambiado.",
                "dark_mode_enabled": "Modo oscuro activado.",
                "light_mode_enabled": "Modo claro activado.",
                "colour_blind_enabled": "Modo daltonismo activado.",
                "colour_blind_disabled": "Colores estandar activados.",
                "help_title": "Ayuda de interfaz",
                "about_title": "Acerca de Logsim",
                "about_text": (
                    "Simulador logico GF2\n"
                    "Interfaz grafica con circuito y osciloscopio."
                ),
                "help_text": (
                    "Ejecutar: inicia el circuito y graba N ciclos.\n"
                    "Continuar: graba N ciclos mas sin borrar trazas.\n"
                    "Paso: avanza un ciclo.\n"
                    "Auto: avanza hasta que lo detengas.\n"
                    "Cambiar interruptor: pone el interruptor en 0 o 1.\n"
                    "Agregar/Quitar monitor: controla las salidas visibles.\n"
                    "Arrastrar mueve la vista; la rueda hace zoom.\n"
                    "Sobre el osciloscopio, la rueda desplaza senales.\n"
                    "Archivo > Abrir carga otro archivo."
                ),
            },
            "de": {
                "menu_file": "&Datei",
                "menu_help": "&Hilfe",
                "menu_open": "&Datei offnen...",
                "menu_save": "&Speichern unter...",
                "menu_export_circuit": "&Schaltung exportieren...",
                "menu_export_scope": "&Oszilloskop exportieren...",
                "menu_exit": "&Beenden",
                "menu_help_item": "&Hilfe",
                "menu_about": "&Info",
                "cycles": "Zyklen",
                "run": "Start",
                "continue": "Weiter",
                "step": "Schritt",
                "auto_run": "Auto",
                "auto_speed": "Auto Tempo",
                "open_file": "Offnen",
                "save_file": "Speichern",
                "export_circuit": "Schaltung exportieren",
                "export_scope": "Scope exportieren",
                "language": "Sprache",
                "dark_mode": "Dunkelmodus",
                "light_mode": "Hellmodus",
                "colour_blind_mode": "Farbenblind",
                "standard_colours": "Standardfarben",
                "help": "Hilfe",
                "switches": "Schalter",
                "monitors": "Monitore",
                "readings": "Werte",
                "log": "Log",
                "switch": "Schalter",
                "value": "Wert",
                "set_switch": "Schalter setzen",
                "available_signals": "Verfugbare Signale",
                "add_monitor": "Monitor hinzufugen",
                "current_monitors": "Aktuelle Monitore",
                "remove_monitor": "Monitor entfernen",
                "reset_view": "Ansicht reset",
                "status_prefix": "Status",
                "language_changed": "Sprache geandert.",
                "dark_mode_enabled": "Dunkelmodus aktiviert.",
                "light_mode_enabled": "Hellmodus aktiviert.",
                "colour_blind_enabled": "Farbenblind-Modus aktiviert.",
                "colour_blind_disabled": "Standardfarben aktiviert.",
                "help_title": "Hilfe",
                "about_title": "Info zu Logsim",
                "about_text": (
                    "GF2 Logiksimulator\n"
                    "Grafische Oberflache mit Schaltung und Oszilloskop."
                ),
                "help_text": (
                    "Start: startet die Schaltung und speichert N Zyklen.\n"
                    "Weiter: speichert N weitere Zyklen ohne zu loschen.\n"
                    "Schritt: fuhrt einen Zyklus aus.\n"
                    "Auto: lauft weiter bis zum Stoppen.\n"
                    "Schalter setzen: setzt den Schalter auf 0 oder 1.\n"
                    "Monitor hinzufugen/entfernen: wahlt sichtbare Ausgange.\n"
                    "Mausziehen verschiebt die Ansicht; Mausrad zoomt.\n"
                    "Uber dem Oszilloskop scrollt das Mausrad Signalzeilen.\n"
                    "Datei > Offnen ladt eine andere Datei."
                ),
            },
        }

    def t(self, key):
        """Translate a UI label for the current language."""
        language = self.translations.get(self.current_language, {})
        return language.get(key, self.translations["en"].get(key, key))

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
        self.canvas.set_dark_mode(self.dark_mode)
        self.canvas.set_colour_blind_mode(self.colour_blind_mode)

        text_controls = [
            self.cycles_label, self.speed_label, self.switch_label,
            self.add_monitor_label, self.remove_monitor_label,
            self.switch_box, self.monitor_box, self.readings_box,
            self.log_box,
        ]
        buttons = [
            self.run_button, self.continue_button, self.step_button,
            self.auto_run_button, self.open_button, self.save_button,
            self.export_circuit_button, self.export_scope_button,
            self.language_button, self.dark_mode_button,
            self.colour_blind_button, self.help_button, self.set_switch_button,
            self.add_monitor_button, self.remove_monitor_button,
            self.reset_view_button,
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
        self.dark_mode_button.SetLabel(self.dark_mode_label())
        self.colour_blind_button.SetLabel(self.colour_blind_mode_label())
        self.Refresh()
        self.Layout()

    def configure_menu(self):
        """Create the File and Help menus."""
        self.help_menu_id = wx.NewIdRef()
        self.export_circuit_menu_id = wx.NewIdRef()
        self.export_scope_menu_id = wx.NewIdRef()

        self.file_menu = wx.Menu()
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

        self.help_menu_item = self.help_menu.Append(
            self.help_menu_id, self.t("menu_help_item")
        )
        self.about_menu_item = self.help_menu.Append(
            wx.ID_ABOUT, self.t("menu_about")
        )

        self.menu_bar.Append(self.file_menu, self.t("menu_file"))
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
        self.open_button = wx.Button(self, wx.ID_ANY, self.t("open_file"))
        self.save_button = wx.Button(self, wx.ID_ANY, self.t("save_file"))
        self.export_circuit_button = wx.Button(
            self, wx.ID_ANY, self.t("export_circuit")
        )
        self.export_scope_button = wx.Button(
            self, wx.ID_ANY, self.t("export_scope")
        )
        self.language_button = wx.Button(
            self, wx.ID_ANY, self.t("language")
        )
        self.dark_mode_button = wx.Button(
            self, wx.ID_ANY, self.dark_mode_label()
        )
        self.colour_blind_button = wx.Button(
            self, wx.ID_ANY, self.colour_blind_mode_label()
        )
        self.help_button = wx.Button(self, wx.ID_ANY, self.t("help"))
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

        self.switch_label = wx.StaticText(self, wx.ID_ANY, self.t("switch"))
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

    def configure_layout(self):
        """Arrange canvas and controls in sizers."""
        root_sizer = wx.BoxSizer(wx.VERTICAL)
        toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        display_sizer = wx.BoxSizer(wx.VERTICAL)
        side_sizer = wx.BoxSizer(wx.VERTICAL)

        self.switch_box = wx.StaticBox(self, label=self.t("switches"))
        self.monitor_box = wx.StaticBox(self, label=self.t("monitors"))
        self.readings_box = wx.StaticBox(self, label=self.t("readings"))
        self.log_box = wx.StaticBox(self, label=self.t("log"))
        switch_box = wx.StaticBoxSizer(self.switch_box, wx.VERTICAL)
        monitor_box = wx.StaticBoxSizer(self.monitor_box, wx.VERTICAL)
        readings_box = wx.StaticBoxSizer(self.readings_box, wx.VERTICAL)
        log_box = wx.StaticBoxSizer(self.log_box, wx.VERTICAL)

        toolbar_sizer.Add(self.cycles_label, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        toolbar_sizer.Add(self.cycles_spin, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        toolbar_sizer.Add(self.run_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        toolbar_sizer.Add(self.continue_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        toolbar_sizer.Add(self.step_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        toolbar_sizer.Add(self.auto_run_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        toolbar_sizer.Add(self.speed_label, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)
        toolbar_sizer.Add(self.speed_slider, 1,
                          wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 6)
        toolbar_sizer.AddStretchSpacer()
        toolbar_sizer.Add(self.open_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar_sizer.Add(self.save_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar_sizer.Add(self.export_circuit_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar_sizer.Add(self.export_scope_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar_sizer.Add(self.language_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar_sizer.Add(self.dark_mode_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar_sizer.Add(self.colour_blind_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar_sizer.Add(self.help_button, 0,
                          wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        switch_box.Add(self.switch_label, 0, wx.TOP | wx.LEFT | wx.RIGHT, 6)
        switch_box.Add(self.switch_choice, 0, wx.EXPAND | wx.ALL, 6)
        switch_box.Add(self.switch_value, 0, wx.EXPAND | wx.ALL, 6)
        switch_box.Add(self.set_switch_button, 0, wx.EXPAND | wx.ALL, 6)

        monitor_box.Add(self.add_monitor_label, 0,
                        wx.TOP | wx.LEFT | wx.RIGHT, 6)
        monitor_box.Add(self.add_monitor_choice, 0, wx.EXPAND | wx.ALL, 6)
        monitor_box.Add(self.add_monitor_button, 0, wx.EXPAND | wx.ALL, 6)
        monitor_box.Add(self.remove_monitor_label, 0,
                        wx.TOP | wx.LEFT | wx.RIGHT, 6)
        monitor_box.Add(self.remove_monitor_choice, 0,
                        wx.EXPAND | wx.ALL, 6)
        monitor_box.Add(self.remove_monitor_button, 0,
                        wx.EXPAND | wx.ALL, 6)
        monitor_box.Add(self.reset_view_button, 0, wx.EXPAND | wx.ALL, 6)
        readings_box.Add(self.readings_list, 1, wx.EXPAND | wx.ALL, 6)
        log_box.Add(self.log_text, 1, wx.EXPAND | wx.ALL, 6)

        side_sizer.Add(switch_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(monitor_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(readings_box, 1, wx.EXPAND | wx.ALL, 6)

        display_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 6)
        display_sizer.Add(
            log_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6
        )

        main_sizer.Add(display_sizer, 1, wx.EXPAND)
        main_sizer.Add(side_sizer, 0, wx.EXPAND | wx.ALL, 6)
        root_sizer.Add(toolbar_sizer, 0, wx.EXPAND | wx.ALL, 6)
        root_sizer.Add(main_sizer, 1, wx.EXPAND)
        self.SetSizer(root_sizer)

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
        self.open_button.Bind(wx.EVT_BUTTON, lambda event: self.on_open_file())
        self.save_button.Bind(wx.EVT_BUTTON, lambda event: self.on_save_file())
        self.export_circuit_button.Bind(
            wx.EVT_BUTTON, lambda event: self.on_export_circuit()
        )
        self.export_scope_button.Bind(
            wx.EVT_BUTTON, lambda event: self.on_export_scope()
        )
        self.language_button.Bind(
            wx.EVT_BUTTON, lambda event: self.on_language_button()
        )
        self.dark_mode_button.Bind(
            wx.EVT_BUTTON, lambda event: self.on_dark_mode_button()
        )
        self.colour_blind_button.Bind(
            wx.EVT_BUTTON, lambda event: self.on_colour_blind_button()
        )
        self.help_button.Bind(wx.EVT_BUTTON, lambda event: self.on_help())
        self.set_switch_button.Bind(wx.EVT_BUTTON, self.on_set_switch_button)
        self.add_monitor_button.Bind(wx.EVT_BUTTON, self.on_add_monitor_button)
        self.remove_monitor_button.Bind(
            wx.EVT_BUTTON, self.on_remove_monitor_button
        )
        self.reset_view_button.Bind(wx.EVT_BUTTON, self.on_reset_view_button)

    def on_menu(self, event):
        """Handle menu events."""
        event_id = event.GetId()
        if event_id == wx.ID_EXIT:
            self.stop_auto_run()
            self.Close(True)
        elif event_id == wx.ID_OPEN:
            self.on_open_file()
        elif event_id == wx.ID_SAVEAS:
            self.on_save_file()
        elif event_id == int(self.export_circuit_menu_id):
            self.on_export_circuit()
        elif event_id == int(self.export_scope_menu_id):
            self.on_export_scope()
        elif event_id == int(self.help_menu_id):
            self.on_help()
        elif event_id == wx.ID_ABOUT:
            self.on_about()

    def on_language_button(self):
        """Show the language selection menu."""
        language_menu = wx.Menu()
        language_names = [
            ("en", "English"),
            ("fr", "Francais"),
            ("es", "Espanol"),
            ("de", "Deutsch"),
        ]

        for language_code, language_name in language_names:
            item = language_menu.AppendRadioItem(
                wx.ID_ANY, language_name
            )
            if language_code == self.current_language:
                item.Check(True)
            self.Bind(
                wx.EVT_MENU,
                lambda event, code=language_code: self.set_language(code),
                id=item.GetId(),
            )

        self.language_button.PopupMenu(language_menu)
        language_menu.Destroy()

    def set_language(self, language_code):
        """Switch visible GUI labels to the selected language."""
        if language_code not in self.translations:
            return

        self.current_language = language_code
        self.update_language_labels()
        self.set_status(self.t("language_changed"))

    def on_dark_mode_button(self):
        """Toggle between light and dark interface themes."""
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        if self.dark_mode:
            self.set_status(self.t("dark_mode_enabled"))
        else:
            self.set_status(self.t("light_mode_enabled"))

    def on_colour_blind_button(self):
        """Toggle colour-blind-safe signal colours."""
        self.colour_blind_mode = not self.colour_blind_mode
        self.apply_theme()
        if self.colour_blind_mode:
            self.set_status(self.t("colour_blind_enabled"))
        else:
            self.set_status(self.t("colour_blind_disabled"))

    def update_language_labels(self):
        """Apply the current language to visible menus and controls."""
        self.menu_bar.SetMenuLabel(0, self.t("menu_file"))
        self.menu_bar.SetMenuLabel(1, self.t("menu_help"))
        self.open_menu_item.SetItemLabel(self.t("menu_open"))
        self.save_menu_item.SetItemLabel(self.t("menu_save"))
        self.export_circuit_menu_item.SetItemLabel(
            self.t("menu_export_circuit")
        )
        self.export_scope_menu_item.SetItemLabel(
            self.t("menu_export_scope")
        )
        self.exit_menu_item.SetItemLabel(self.t("menu_exit"))
        self.help_menu_item.SetItemLabel(self.t("menu_help_item"))
        self.about_menu_item.SetItemLabel(self.t("menu_about"))

        self.cycles_label.SetLabel(self.t("cycles"))
        self.run_button.SetLabel(self.t("run"))
        self.continue_button.SetLabel(self.t("continue"))
        self.step_button.SetLabel(self.t("step"))
        self.auto_run_button.SetLabel(self.t("auto_run"))
        self.speed_label.SetLabel(self.t("auto_speed"))
        self.open_button.SetLabel(self.t("open_file"))
        self.save_button.SetLabel(self.t("save_file"))
        self.export_circuit_button.SetLabel(self.t("export_circuit"))
        self.export_scope_button.SetLabel(self.t("export_scope"))
        self.language_button.SetLabel(self.t("language"))
        self.dark_mode_button.SetLabel(self.dark_mode_label())
        self.colour_blind_button.SetLabel(self.colour_blind_mode_label())
        self.help_button.SetLabel(self.t("help"))

        self.switch_box.SetLabel(self.t("switches"))
        self.monitor_box.SetLabel(self.t("monitors"))
        self.readings_box.SetLabel(self.t("readings"))
        self.log_box.SetLabel(self.t("log"))
        self.switch_label.SetLabel(self.t("switch"))
        self.switch_value.SetLabel(self.t("value"))
        self.set_switch_button.SetLabel(self.t("set_switch"))
        self.add_monitor_label.SetLabel(self.t("available_signals"))
        self.add_monitor_button.SetLabel(self.t("add_monitor"))
        self.remove_monitor_label.SetLabel(self.t("current_monitors"))
        self.remove_monitor_button.SetLabel(self.t("remove_monitor"))
        self.reset_view_button.SetLabel(self.t("reset_view"))
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
            self.set_status("Auto run started.")
        else:
            self.stop_auto_run()
            self.set_status("Auto run stopped.")

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
            self.after_action(False, "No switch selected.")
            return

        success, message = self.controller.set_switch(
            switch_name, self.switch_value.GetStringSelection()
        )
        self.after_action(success, message)

    def on_add_monitor_button(self, event):
        """Add the selected signal as a monitor."""
        signal_name = self.get_choice_value(self.add_monitor_choice)
        if signal_name is None:
            self.after_action(False, "No available signal selected.")
            return

        success, message = self.controller.add_monitor(signal_name)
        self.after_action(success, message)

    def on_remove_monitor_button(self, event):
        """Remove the selected monitor."""
        signal_name = self.get_choice_value(self.remove_monitor_choice)
        if signal_name is None:
            self.after_action(False, "No current monitor selected.")
            return

        self.archive_default_monitor(signal_name)
        success, message = self.controller.remove_monitor(signal_name)
        self.after_action(success, message)

    def on_reset_view_button(self, event):
        """Restore the default monitor view and reset canvas pan and zoom."""
        self.restore_default_monitors()
        self.refresh_choices()
        self.canvas.reset_view()
        self.set_status("View reset.")

    def on_open_file(self):
        """Load and parse a new definition file selected by the user."""
        with wx.FileDialog(
            self,
            "Open logic definition file",
            wildcard="Text files (*.txt)|*.txt|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            path = dialog.GetPath()

        self.load_definition_file(path)

    def on_save_file(self):
        """Save a copy of the currently loaded definition file."""
        default_dir = os.path.dirname(self.path)
        default_file = os.path.basename(self.path)

        with wx.FileDialog(
            self,
            "Save logic definition file",
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard="Text files (*.txt)|*.txt|All files (*.*)|*.*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            save_path = dialog.GetPath()

        try:
            if os.path.abspath(save_path) != os.path.abspath(self.path):
                shutil.copyfile(self.path, save_path)
            self.set_status("Saved file to " + save_path)
        except OSError as error:
            wx.MessageBox(
                "The file could not be saved.\n" + str(error),
                "File Save Error",
                wx.OK | wx.ICON_ERROR,
            )
            self.set_status("Could not save file.", error=True)

    def on_export_circuit(self):
        """Export the current circuit overview to an image or PDF."""
        default_dir = os.path.dirname(self.path)
        base_name = os.path.splitext(os.path.basename(self.path))[0]
        export_path = self.choose_export_path(
            "Export logic circuit",
            default_dir,
            base_name + "_circuit.png",
        )
        if export_path is None:
            return

        try:
            if self.canvas.save_circuit_image(export_path):
                self.set_status("Exported circuit to " + export_path)
            else:
                self.set_status("Could not export circuit.", error=True)
        except Exception as error:
            wx.MessageBox(
                "The circuit image could not be exported.\n" + str(error),
                "Circuit Export Error",
                wx.OK | wx.ICON_ERROR,
            )
            self.set_status("Could not export circuit.", error=True)

    def on_export_scope(self):
        """Export the current oscilloscope view to an image or PDF."""
        default_dir = os.path.dirname(self.path)
        base_name = os.path.splitext(os.path.basename(self.path))[0]
        export_path = self.choose_export_path(
            "Export oscilloscope",
            default_dir,
            base_name + "_oscilloscope.png",
        )
        if export_path is None:
            return

        try:
            if self.canvas.save_scope_image(export_path):
                self.set_status("Exported oscilloscope to " + export_path)
            else:
                self.set_status("Could not export oscilloscope.", error=True)
        except Exception as error:
            wx.MessageBox(
                "The oscilloscope image could not be exported.\n"
                + str(error),
                "Oscilloscope Export Error",
                wx.OK | wx.ICON_ERROR,
            )
            self.set_status("Could not export oscilloscope.", error=True)

    def choose_export_path(self, title, default_dir, default_file):
        """Return a PNG or PDF path selected by the user."""
        with wx.FileDialog(
            self,
            title,
            defaultDir=default_dir,
            defaultFile=default_file,
            wildcard="PNG image (*.png)|*.png|PDF document (*.pdf)|*.pdf",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
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

        if not parser.parse_network():
            wx.MessageBox(
                "The selected definition file could not be parsed.\n"
                "Check the terminal for syntax or semantic errors.",
                "File Load Error",
                wx.OK | wx.ICON_ERROR,
            )
            return

        self.path = path
        self.controller = GuiController(names, devices, network, monitors)
        self.canvas.devices = devices
        self.canvas.monitors = monitors
        self.canvas.reset_view()
        self.remember_default_monitors()
        self.refresh_choices()
        self.set_status("Loaded " + path)

    def on_help(self):
        """Display a concise user guide."""
        wx.MessageBox(
            self.t("help_text"),
            self.t("help_title"),
            wx.OK | wx.ICON_INFORMATION,
        )

    def on_about(self):
        """Display application information."""
        wx.MessageBox(
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
        prefix = "Error: " if error else ""
        status_text = (
            prefix + message + "\nCycles completed: "
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
        self.log_text.SetInsertionPointEnd()
        self.log_text.ShowPosition(self.log_text.GetLastPosition())
