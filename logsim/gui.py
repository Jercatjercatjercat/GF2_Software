"""Implement the graphical user interface for the Logic Simulator.

The GUI mirrors the required command-line operations: run, continue, set a
switch, add a monitor, and remove a monitor.  Signal traces are drawn in an
OpenGL canvas and can be panned or zoomed with the mouse.
"""

import wx
import wx.glcanvas as wxcanvas
from OpenGL import GL, GLUT

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
        self.cycle_width = 28
        self.row_height = 52
        self.high_offset = 30
        self.low_offset = 8

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
        """Draw all current monitor traces."""
        self.SetCurrent(self.context)
        if not self.init:
            self.init_gl()
            self.init = True

        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glLineWidth(1.0)

        monitor_items = list(self.monitors.monitors_dictionary.items())
        if not monitor_items:
            self.render_text("No monitor points selected.", 20, 40)
            self.finish_render()
            return

        self.left_margin = self.calculate_left_margin(monitor_items)
        self.draw_time_axis(monitor_items)
        for row_index, monitor_item in enumerate(monitor_items):
            self.draw_monitor_trace(row_index, monitor_item)

        self.finish_render()

    def finish_render(self):
        """Flush drawing commands and swap buffers."""
        GL.glFlush()
        self.SwapBuffers()

    def draw_time_axis(self, monitor_items):
        """Draw a simple cycle scale above the waveforms."""
        max_cycles = 0
        for _, signal_list in monitor_items:
            max_cycles = max(max_cycles, len(signal_list))

        y_pos = self.get_axis_y(len(monitor_items))
        self.set_colour(0.15, 0.15, 0.15)
        self.render_text("cycle", 10, y_pos - 4)

        GL.glBegin(GL.GL_LINES)
        GL.glVertex2f(self.left_margin, y_pos)
        GL.glVertex2f(self.left_margin + max_cycles * self.cycle_width, y_pos)
        GL.glEnd()

        for cycle in range(max_cycles + 1):
            x_pos = self.left_margin + cycle * self.cycle_width
            GL.glBegin(GL.GL_LINES)
            GL.glVertex2f(x_pos, y_pos - 4)
            GL.glVertex2f(x_pos, y_pos + 4)
            GL.glEnd()
            if cycle % 5 == 0:
                self.render_text(str(cycle), x_pos - 4, y_pos + 10)

    def calculate_left_margin(self, monitor_items):
        """Return enough left margin to fit the longest monitor name."""
        longest_name = 0
        for (device_id, output_id), _ in monitor_items:
            monitor_name = self.devices.get_signal_name(device_id, output_id)
            longest_name = max(longest_name, len(str(monitor_name)))
        return max(150, 20 + longest_name * 9)

    def draw_monitor_trace(self, row_index, monitor_item):
        """Draw one monitor name and its waveform."""
        (device_id, output_id), signal_list = monitor_item
        monitor_name = self.devices.get_signal_name(device_id, output_id)
        row_base = self.get_row_base(row_index)

        self.set_colour(0.0, 0.0, 0.0)
        self.render_text(monitor_name, 10, row_base + 14)

        self.draw_row_guides(row_base, len(signal_list))

        for index, signal in enumerate(signal_list):
            x_start = self.left_margin + index * self.cycle_width
            x_end = x_start + self.cycle_width
            self.draw_signal_segment(signal, x_start, x_end, row_base)

    def draw_row_guides(self, row_base, cycles):
        """Draw faint high and low guide lines for a waveform row."""
        x_start = self.left_margin
        x_end = self.left_margin + max(cycles, 1) * self.cycle_width
        self.set_colour(0.88, 0.88, 0.88)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex2f(x_start, row_base + self.high_offset)
        GL.glVertex2f(x_end, row_base + self.high_offset)
        GL.glVertex2f(x_start, row_base + self.low_offset)
        GL.glVertex2f(x_end, row_base + self.low_offset)
        GL.glEnd()

    def draw_signal_segment(self, signal, x_start, x_end, row_base):
        """Draw one cycle of a signal trace."""
        high_y = row_base + self.high_offset
        low_y = row_base + self.low_offset

        if signal == self.devices.BLANK:
            self.set_colour(0.72, 0.72, 0.72)
            self.draw_dashed_blank(x_start, x_end, row_base)
            return

        self.set_colour(0.0, 0.18, 0.75)
        GL.glLineWidth(2.0)
        GL.glBegin(GL.GL_LINES)
        if signal == self.devices.HIGH:
            GL.glVertex2f(x_start, high_y)
            GL.glVertex2f(x_end, high_y)
        elif signal == self.devices.LOW:
            GL.glVertex2f(x_start, low_y)
            GL.glVertex2f(x_end, low_y)
        elif signal == self.devices.RISING:
            GL.glVertex2f(x_start, low_y)
            GL.glVertex2f(x_end, high_y)
        elif signal == self.devices.FALLING:
            GL.glVertex2f(x_start, high_y)
            GL.glVertex2f(x_end, low_y)
        GL.glEnd()
        GL.glLineWidth(1.0)

    def draw_dashed_blank(self, x_start, x_end, row_base):
        """Draw a blank signal interval for monitors added mid-run."""
        mid_y = row_base + (self.high_offset + self.low_offset) / 2
        dash_width = 6
        x_pos = x_start
        GL.glBegin(GL.GL_LINES)
        while x_pos < x_end:
            GL.glVertex2f(x_pos, mid_y)
            GL.glVertex2f(min(x_pos + dash_width, x_end), mid_y)
            x_pos += dash_width * 2
        GL.glEnd()

    def get_axis_y(self, number_of_rows):
        """Return y position for the time axis."""
        return self.get_row_base(number_of_rows - 1) + self.row_height

    def get_row_base(self, row_index):
        """Return base y position for a row."""
        return 32 + row_index * self.row_height

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

    def render_text(self, text, x_pos, y_pos):
        """Draw bitmap text at the given position."""
        self.set_colour(0.0, 0.0, 0.0)
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
        """Create the File menu."""
        file_menu = wx.Menu()
        menu_bar = wx.MenuBar()
        file_menu.Append(wx.ID_ABOUT, "&About")
        file_menu.Append(wx.ID_EXIT, "&Exit")
        menu_bar.Append(file_menu, "&File")
        self.SetMenuBar(menu_bar)

    def create_controls(self):
        """Create all sidebar controls."""
        self.cycles_label = wx.StaticText(self, wx.ID_ANY, "Cycles")
        self.cycles_spin = wx.SpinCtrl(
            self, wx.ID_ANY, min=0, max=100000, initial=10
        )
        self.run_button = wx.Button(self, wx.ID_ANY, "Run")
        self.continue_button = wx.Button(self, wx.ID_ANY, "Continue")

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

        status_box.Add(self.status_box, 1, wx.EXPAND | wx.ALL, 6)

        side_sizer.Add(run_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(switch_box, 0, wx.EXPAND | wx.ALL, 6)
        side_sizer.Add(monitor_box, 0, wx.EXPAND | wx.ALL, 6)

        main_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 6)
        main_sizer.Add(side_sizer, 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(main_sizer)

    def bind_events(self):
        """Bind widget events to handlers."""
        self.Bind(wx.EVT_MENU, self.on_menu)
        self.run_button.Bind(wx.EVT_BUTTON, self.on_run_button)
        self.continue_button.Bind(wx.EVT_BUTTON, self.on_continue_button)
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
            self.Close(True)
        elif event_id == wx.ID_ABOUT:
            wx.MessageBox(
                "GF2 Logic Simulator\nGraphical user interface",
                "About Logsim",
                wx.ICON_INFORMATION | wx.OK,
            )

    def on_run_button(self, event):
        """Run the simulation from a cold start."""
        success, message = self.controller.run_from_start(
            self.cycles_spin.GetValue()
        )
        self.after_action(success, message)

    def on_continue_button(self, event):
        """Continue a previous simulation."""
        success, message = self.controller.continue_simulation(
            self.cycles_spin.GetValue()
        )
        self.after_action(success, message)

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
        self.SetStatusText(
            prefix + message + "  |  Cycles completed: "
            + str(self.controller.cycles_completed)
        )
