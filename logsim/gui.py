"""Implement the graphical user interface for the Logic Simulator.

The GUI mirrors the required command-line operations: run, continue, set a
switch, add a monitor, and remove a monitor.  Signal traces are drawn in an
OpenGL canvas and can be panned or zoomed with the mouse.
"""

import math

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

        self.left_margin = 150
        self.cycle_width = 26
        self.row_height = 38
        self.high_offset = 22
        self.low_offset = 6
        self.trace_colours = [
            (0.20, 0.23, 0.78),
            (0.16, 0.50, 0.26),
            (0.70, 0.22, 0.22),
            (0.57, 0.31, 0.70),
            (0.10, 0.55, 0.62),
            (0.72, 0.43, 0.12),
        ]

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.on_mouse)

    def reset_view(self):
        """Reset pan and zoom to their defaults."""
        self.pan_x = 0
        self.pan_y = 0
        self.zoom = 1.0
        self.init = False
        self.Refresh()

    def init_gl(self):
        """Configure the OpenGL projection for the current canvas size."""
        size = self.GetClientSize()
        self.SetCurrent(self.context)
        GL.glDrawBuffer(GL.GL_BACK)
        GL.glClearColor(1.0, 1.0, 1.0, 0.0)
        GL.glViewport(0, 0, size.width, size.height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        GL.glOrtho(0, size.width, 0, size.height, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glTranslated(self.pan_x, self.pan_y, 0.0)
        GL.glScaled(self.zoom, self.zoom, self.zoom)

    def render(self):
        """Draw the circuit overview and oscilloscope-style traces."""
        self.SetCurrent(self.context)
        if not self.init:
            self.init_gl()
            self.init = True

        size = self.GetClientSize()
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glLineWidth(1.0)

        monitor_items = list(self.monitors.monitors_dictionary.items())
        circuit_bounds = (18, size.height - 218, size.width - 36, 190)
        scope_bounds = (18, 28, size.width - 36, size.height - 270)

        if scope_bounds[3] < 240:
            scope_bounds = (18, 28, size.width - 36, 240)
            circuit_bounds = (18, 290, size.width - 36, 190)

        self.draw_canvas_grid(size)
        self.draw_circuit_overview(circuit_bounds)
        self.draw_oscilloscope(scope_bounds, monitor_items)
        self.finish_render()

    def finish_render(self):
        """Flush drawing commands and swap buffers."""
        GL.glFlush()
        self.SwapBuffers()

    def draw_canvas_grid(self, size):
        """Draw a faint simulator-style workspace grid."""
        self.set_colour(0.94, 0.94, 0.90)
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
        self.draw_rectangle(bounds, (0.98, 0.98, 0.95), (0.70, 0.70, 0.62))
        self.render_text("Circuit overview", x_pos + 10, y_pos + height - 20)

        positions = self.build_device_positions(bounds)
        self.draw_connections(positions)

        for device in self.devices.devices_list:
            if device.device_id in positions:
                self.draw_device_node(device, positions[device.device_id])

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
        block_width = 92
        block_height = 34
        usable_width = max(width - block_width - 90, 1)

        for layer, devices_in_layer in layer_groups.items():
            if max_layer == 0:
                node_x = x_pos + width / 2 - block_width / 2
            else:
                node_x = x_pos + 48 + layer * usable_width / max_layer

            count = len(devices_in_layer)
            available_height = max(height - 58, 1)
            for index, device in enumerate(devices_in_layer):
                if count == 1:
                    node_y = y_pos + height / 2 - block_height / 2 - 4
                else:
                    gap = available_height / (count - 1)
                    node_y = y_pos + height - 58 - index * gap
                positions[device.device_id] = (
                    node_x, node_y, block_width, block_height
                )

        return positions

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

        self.draw_rectangle(bounds, fill_colour, (0.30, 0.30, 0.32))
        self.render_text(str(name), x_pos + 7, y_pos + height - 15)
        self.render_text(str(kind), x_pos + 7, y_pos + 10)

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
            return (1.00, 0.96, 0.76)
        if device.device_kind == self.devices.CLOCK:
            return (0.80, 0.94, 0.82)
        if device.device_kind == self.devices.D_TYPE:
            return (0.83, 0.91, 1.00)
        return (0.95, 0.95, 1.00)

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

        margin_x = 34 if width > 520 else 8
        scope_bounds = (
            x_pos + margin_x,
            y_pos + 8,
            width - 2 * margin_x,
            height - 16,
        )
        scope_x, scope_y, scope_width, scope_height = scope_bounds

        self.draw_rectangle(
            (scope_x + 7, scope_y - 7, scope_width, scope_height),
            (0.42, 0.42, 0.42),
        )
        self.draw_rectangle(
            scope_bounds, (0.78, 0.78, 0.78), (0.36, 0.36, 0.38)
        )
        self.draw_scope_header(scope_bounds)
        self.draw_scope_controls(scope_bounds)

        if not monitor_items:
            self.render_text(
                "No monitor points selected.",
                scope_x + 20,
                scope_y + scope_height - 78,
            )
            return

        max_cycles = self.max_recorded_cycles(monitor_items)
        if max_cycles == 0:
            self.render_text(
                "Press Run to record signal traces.",
                scope_x + 20,
                scope_y + scope_height - 78,
            )

        label_width = self.calculate_scope_label_width(monitor_items)
        title_height = 28
        control_height = 42
        axis_height = 54
        scroll_width = 14

        plot_x = scope_x + label_width
        plot_y = scope_y + axis_height
        plot_width = scope_width - label_width - scroll_width - 20
        control_y = scope_y + scope_height - title_height - control_height
        plot_height = control_y - plot_y - 8

        max_visible_cycles = max(10, int(plot_width // 13))
        if max_cycles > max_visible_cycles:
            first_cycle = max_cycles - max_visible_cycles
            cycle_count = max_visible_cycles
        else:
            first_cycle = 0
            cycle_count = max(max_cycles, 10)
        self.cycle_width = plot_width / max(cycle_count, 1)

        self.draw_scope_grid(
            plot_x, plot_y, plot_width, plot_height, cycle_count
        )
        self.draw_scope_scrollbars(
            scope_bounds, plot_x, plot_y, plot_width, plot_height,
            first_cycle, max_cycles, cycle_count
        )
        self.draw_scope_rows(
            scope_x, plot_x, plot_y, plot_height, monitor_items,
            first_cycle, cycle_count
        )
        self.draw_scope_axis(plot_x, plot_y, cycle_count, first_cycle)

    def draw_scope_header(self, bounds):
        """Draw the oscilloscope title strip."""
        x_pos, y_pos, width, height = bounds
        header_bounds = (x_pos, y_pos + height - 28, width, 28)
        self.draw_rectangle(header_bounds, (0.70, 0.80, 0.91),
                            (0.48, 0.48, 0.52))
        self.render_text("Oscilloscope", x_pos + 30, y_pos + height - 18)
        self.draw_rectangle(
            (x_pos + 9, y_pos + height - 21, 12, 12),
            (0.82, 0.90, 0.98), (0.35, 0.48, 0.64)
        )

        button_y = y_pos + height - 21
        self.draw_window_button(x_pos + width - 55, button_y, "_")
        self.draw_window_button(x_pos + width - 37, button_y, "[]")
        self.draw_window_button(x_pos + width - 19, button_y, "x")

    def draw_scope_controls(self, bounds):
        """Draw toolbar buttons and top slider inside the scope."""
        x_pos, y_pos, width, height = bounds
        controls_y = y_pos + height - 70

        self.draw_toolbar_button(x_pos + 12, controls_y + 12, "||")
        self.draw_toolbar_button(x_pos + 39, controls_y + 12, "+")

        slider_x = x_pos + 110
        slider_y = controls_y + 24
        slider_width = width - 190
        self.set_colour(0.88, 0.88, 0.88)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex2f(slider_x, slider_y)
        GL.glVertex2f(slider_x + slider_width, slider_y)
        GL.glEnd()
        self.draw_rectangle(
            (slider_x + slider_width * 0.50 - 4, slider_y - 10, 8, 20),
            (0.74, 0.88, 0.94), (0.42, 0.58, 0.66)
        )

    def draw_window_button(self, x_pos, y_pos, label):
        """Draw a small title-bar window button."""
        self.draw_rectangle(
            (x_pos, y_pos, 13, 12), (0.86, 0.89, 0.93), (0.45, 0.48, 0.52)
        )
        self.render_text(label, x_pos + 3, y_pos + 2, (0.18, 0.20, 0.22))

    def draw_toolbar_button(self, x_pos, y_pos, label):
        """Draw a small oscilloscope toolbar button."""
        self.draw_rectangle(
            (x_pos, y_pos, 20, 22), (0.88, 0.92, 0.96), (0.52, 0.56, 0.62)
        )
        self.render_text(label, x_pos + 5, y_pos + 7, (0.20, 0.34, 0.60))

    def draw_scope_grid(self, plot_x, plot_y, width, height, cycle_count):
        """Draw oscilloscope grid lines."""
        GL.glBegin(GL.GL_LINES)
        for cycle in range(cycle_count + 1):
            if cycle % 5 == 0:
                self.set_colour(0.70, 0.70, 0.74)
            else:
                self.set_colour(0.86, 0.86, 0.88)
            x_pos = plot_x + cycle * self.cycle_width
            GL.glVertex2f(x_pos, plot_y)
            GL.glVertex2f(x_pos, plot_y + height)

        for row in range(0, int(height), 24):
            self.set_colour(0.90, 0.90, 0.91)
            GL.glVertex2f(plot_x, plot_y + row)
            GL.glVertex2f(plot_x + width, plot_y + row)
        GL.glEnd()

    def draw_scope_rows(self, label_x, plot_x, plot_y, plot_height,
                        monitor_items, first_cycle, cycle_count):
        """Draw all monitored signal names and waveforms."""
        row_gap = min(
            self.row_height, plot_height / max(len(monitor_items), 1)
        )
        for index, monitor_item in enumerate(monitor_items):
            (device_id, output_id), signal_list = monitor_item
            name = self.devices.get_signal_name(device_id, output_id)
            row_mid = plot_y + plot_height - 18 - index * row_gap
            row_base = row_mid - self.high_offset / 2

            colour = self.trace_colour_for_monitor(
                device_id, output_id, index
            )
            self.set_colour(*colour)
            self.render_text(name, label_x + 14, row_mid - 5, colour)
            visible_signals = signal_list[
                first_cycle:first_cycle + cycle_count
            ]
            self.draw_digital_signal(plot_x, row_base, visible_signals, colour)

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
        self.set_colour(0.70, 0.70, 0.70)
        GL.glBegin(GL.GL_LINES)
        while x_start < x_end:
            GL.glVertex2f(x_start, mid_y)
            GL.glVertex2f(min(x_start + dash_width, x_end), mid_y)
            x_start += dash_width * 2
        GL.glEnd()

    def draw_scope_scrollbars(self, bounds, plot_x, plot_y, plot_width,
                              plot_height, first_cycle, max_cycles,
                              cycle_count):
        """Draw decorative scrollbars like a scope display."""
        x_pos, y_pos, width, _ = bounds
        right_x = plot_x + plot_width + 6

        self.draw_rectangle(
            (right_x, plot_y, 10, plot_height), (0.88, 0.88, 0.88),
            (0.62, 0.62, 0.64)
        )
        thumb_height = max(28, plot_height * 0.28)
        self.draw_rectangle(
            (right_x + 1, plot_y + plot_height * 0.48, 8, thumb_height),
            (0.72, 0.72, 0.74), (0.48, 0.48, 0.50)
        )

        bar_y = y_pos + 22
        bar_x = plot_x
        bar_width = plot_width
        self.draw_rectangle(
            (bar_x, bar_y, bar_width, 13), (0.88, 0.88, 0.88),
            (0.62, 0.62, 0.64)
        )
        self.draw_rectangle(
            (bar_x - 12, bar_y, 12, 13), (0.86, 0.86, 0.86),
            (0.62, 0.62, 0.64)
        )
        self.draw_rectangle(
            (bar_x + bar_width, bar_y, 12, 13), (0.86, 0.86, 0.86),
            (0.62, 0.62, 0.64)
        )

        if max_cycles > cycle_count:
            fraction = first_cycle / max(max_cycles - cycle_count, 1)
            thumb_width = max(44, bar_width * cycle_count / max_cycles)
            thumb_x = bar_x + fraction * (bar_width - thumb_width)
        else:
            thumb_width = max(44, bar_width * 0.55)
            thumb_x = bar_x + (bar_width - thumb_width) / 2
        self.draw_rectangle(
            (thumb_x, bar_y + 2, thumb_width, 9), (0.72, 0.72, 0.74),
            (0.48, 0.48, 0.50)
        )
        self.render_text("<", bar_x - 9, bar_y + 2, (0.26, 0.26, 0.28))
        self.render_text(">", bar_x + bar_width + 4, bar_y + 2,
                         (0.26, 0.26, 0.28))

    def draw_scope_axis(self, plot_x, plot_y, cycle_count, first_cycle):
        """Draw cycle tick labels along the bottom of the scope."""
        self.set_colour(0.22, 0.22, 0.24)
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

        self.render_text("Cycles", plot_x, plot_y - 34)

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
        self.set_colour(0.24, 0.24, 0.24)
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
        if signal in [self.devices.HIGH, self.devices.RISING]:
            return (0.86, 0.08, 0.08)
        if signal in [self.devices.LOW, self.devices.FALLING]:
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

        if event.Dragging():
            self.pan_x += event.GetX() - self.last_mouse_x
            self.pan_y -= event.GetY() - self.last_mouse_y
            self.last_mouse_x = event.GetX()
            self.last_mouse_y = event.GetY()
            self.init = False
            self.Refresh()

        wheel_rotation = event.GetWheelRotation()
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

    def render_text(self, text, x_pos, y_pos, colour=(0.0, 0.0, 0.0)):
        """Draw bitmap text at the given position."""
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

        self.path = path
        self.controller = GuiController(names, devices, network, monitors)
        self.auto_timer = wx.Timer(self)

        self.configure_menu()
        self.CreateStatusBar()
        self.canvas = MyGLCanvas(self, devices, monitors)
        self.create_controls()
        self.configure_layout()
        self.bind_events()
        self.refresh_choices()
        self.set_status("Loaded " + path)

        self.SetSizeHints(760, 520)

    def configure_menu(self):
        """Create the File and Help menus."""
        self.help_menu_id = wx.NewIdRef()

        file_menu = wx.Menu()
        menu_bar = wx.MenuBar()
        file_menu.Append(wx.ID_OPEN, "&Open definition file...")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "&Exit")

        help_menu = wx.Menu()
        help_menu.Append(self.help_menu_id, "&Help")
        help_menu.Append(wx.ID_ABOUT, "&About")

        menu_bar.Append(file_menu, "&File")
        menu_bar.Append(help_menu, "&Help")
        self.SetMenuBar(menu_bar)

    def create_controls(self):
        """Create all sidebar controls."""
        self.cycles_label = wx.StaticText(self, wx.ID_ANY, "Cycles")
        self.cycles_spin = wx.SpinCtrl(
            self, wx.ID_ANY, min=0, max=100000, initial=10
        )
        self.run_button = wx.Button(self, wx.ID_ANY, "Run")
        self.continue_button = wx.Button(self, wx.ID_ANY, "Continue")
        self.step_button = wx.Button(self, wx.ID_ANY, "Step")
        self.auto_run_button = wx.ToggleButton(self, wx.ID_ANY, "Auto Run")
        self.speed_label = wx.StaticText(self, wx.ID_ANY, "Auto speed")
        self.speed_slider = wx.Slider(
            self, wx.ID_ANY, value=5, minValue=1, maxValue=10
        )
        self.status_label = wx.StaticText(self, wx.ID_ANY, "")
        self.status_label.Wrap(230)

        self.switch_label = wx.StaticText(self, wx.ID_ANY, "Switch")
        self.switch_choice = wx.Choice(self, wx.ID_ANY)
        self.switch_value = wx.RadioBox(
            self,
            wx.ID_ANY,
            "Value",
            choices=["0", "1"],
            majorDimension=2,
            style=wx.RA_SPECIFY_COLS,
        )
        self.set_switch_button = wx.Button(self, wx.ID_ANY, "Set Switch")

        self.add_monitor_label = wx.StaticText(
            self, wx.ID_ANY, "Available signals"
        )
        self.add_monitor_choice = wx.Choice(self, wx.ID_ANY)
        self.add_monitor_button = wx.Button(self, wx.ID_ANY, "Add Monitor")

        self.remove_monitor_label = wx.StaticText(
            self, wx.ID_ANY, "Current monitors"
        )
        self.remove_monitor_choice = wx.Choice(self, wx.ID_ANY)
        self.remove_monitor_button = wx.Button(
            self, wx.ID_ANY, "Remove Monitor"
        )

        self.reset_view_button = wx.Button(self, wx.ID_ANY, "Reset View")

    def configure_layout(self):
        """Arrange canvas and controls in sizers."""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        side_sizer = wx.BoxSizer(wx.VERTICAL)

        run_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Simulation"),
                                    wx.VERTICAL)
        switch_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Switches"),
                                       wx.VERTICAL)
        monitor_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Monitors"),
                                        wx.VERTICAL)

        run_box.Add(self.cycles_label, 0, wx.TOP | wx.LEFT | wx.RIGHT, 6)
        run_box.Add(self.cycles_spin, 0, wx.EXPAND | wx.ALL, 6)
        run_box.Add(self.run_button, 0, wx.EXPAND | wx.ALL, 6)
        run_box.Add(self.continue_button, 0, wx.EXPAND | wx.ALL, 6)
        run_box.Add(self.step_button, 0, wx.EXPAND | wx.ALL, 6)
        run_box.Add(self.auto_run_button, 0, wx.EXPAND | wx.ALL, 6)
        run_box.Add(self.speed_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        run_box.Add(self.speed_slider, 0, wx.EXPAND | wx.ALL, 6)
        run_box.Add(self.status_label, 0, wx.EXPAND | wx.ALL, 6)

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

        side_sizer.Add(run_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(switch_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(monitor_box, 0, wx.EXPAND | wx.ALL, 6)

        main_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 6)
        main_sizer.Add(side_sizer, 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(main_sizer)

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

    def on_menu(self, event):
        """Handle menu events."""
        event_id = event.GetId()
        if event_id == wx.ID_EXIT:
            self.stop_auto_run()
            self.Close(True)
        elif event_id == wx.ID_OPEN:
            self.on_open_file()
        elif event_id == int(self.help_menu_id):
            self.on_help()
        elif event_id == wx.ID_ABOUT:
            self.on_about()

    def on_close(self, event):
        """Stop background timers before closing the window."""
        self.stop_auto_run()
        event.Skip()

    def on_run_button(self, event):
        """Run the simulation from a cold start."""
        self.stop_auto_run()
        success, message = self.controller.run_from_start(
            self.cycles_spin.GetValue()
        )
        self.after_action(success, message)

    def on_continue_button(self, event):
        """Continue a previous simulation."""
        self.stop_auto_run()
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

        success, message = self.controller.remove_monitor(signal_name)
        self.after_action(success, message)

    def on_reset_view_button(self, event):
        """Reset canvas pan and zoom."""
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
        self.refresh_choices()
        self.set_status("Loaded " + path)

    def on_help(self):
        """Display a concise user guide."""
        wx.MessageBox(
            "Run: cold-starts the circuit and records N cycles.\n"
            "Continue: records N more cycles without clearing traces.\n"
            "Step: advances by one cycle.\n"
            "Auto Run: keeps stepping until you stop it.\n"
            "Set Switch: changes the selected switch to 0 or 1.\n"
            "Add/Remove Monitor: controls which outputs are shown.\n"
            "Mouse drag pans the display; mouse wheel zooms it.\n"
            "File > Open loads another definition file.",
            "Interface Help",
            wx.OK | wx.ICON_INFORMATION,
        )

    def on_about(self):
        """Display application information."""
        wx.MessageBox(
            "GF2 Logic Simulator\n"
            "Graphical interface with circuit overview and oscilloscope.",
            "About Logsim",
            wx.OK | wx.ICON_INFORMATION,
        )

    def after_action(self, success, message):
        """Refresh state after a user action."""
        self.refresh_choices()
        self.canvas.Refresh()
        self.set_status(message, error=not success)

    def refresh_choices(self):
        """Refresh switch and monitor choice controls."""
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

    def set_status(self, message, error=False):
        """Show a status message to the user."""
        prefix = "Error: " if error else ""
        status_text = (
            prefix + message + "\nCycles completed: "
            + str(self.controller.cycles_completed)
        )
        self.status_label.SetLabel(status_text)
        self.status_label.Wrap(230)
        self.SetStatusText(status_text.replace("\n", "  |  "))
        self.Layout()
