#!/usr/bin/env python3
"""Parse command line options and arguments for the Logic Simulator.

This script parses options and arguments specified on the command line, and
runs either the command line user interface or the graphical user interface.

Usage
-----
Show help: logsim.py -h
Command line user interface: logsim.py -c <file path>
Graphical user interface: logsim.py <file path>
3D graphical interface: logsim.py --3d <file path>
"""
import getopt
import sys


from names import Names
from devices import Devices
from network import Network
from monitors import Monitors
from scanner import Scanner
from parse import Parser, parse_network_with_diagnostics
from userint import UserInterface
from language import (
    language_from_linux_locale,
    language_from_environment,
    language_from_python_locale,
    language_from_windows_locale,
    load_translations,
    non_default_language,
)


def detect_startup_language(environ=None, locale_module=None,
                            windows_api=None, linux_config_paths=None,
                            wsl_command_runner=None, osrelease_path=None):
    """Return an explicit process or account language, if one is set."""
    translations = load_translations()
    supported_languages = set(translations)
    return (
        non_default_language(
            language_from_environment(environ, supported_languages)
        )
        or non_default_language(
            language_from_windows_locale(
                supported_languages,
                windows_api,
                environ,
                wsl_command_runner,
                osrelease_path,
            )
        )
        or non_default_language(
            language_from_linux_locale(
                supported_languages, environ, linux_config_paths
            )
        )
        or non_default_language(
            language_from_python_locale(supported_languages, locale_module)
        )
    )


def main(arg_list):
    """Parse the command line options and arguments specified in arg_list.

    Run either the command line user interface, the graphical user interface,
    the 3D graphical user interface, or display the usage message.
    """
    usage_message = ("Usage:\n"
                     "Show help: logsim.py -h\n"
                     "Command line user interface: logsim.py -c <file path>\n"
                     "Graphical user interface: logsim.py <file path>\n"
                     "3D graphical interface: logsim.py --3d <file path>")
    try:
        options, arguments = getopt.getopt(arg_list, "hc:", ["3d"])
    except getopt.GetoptError:
        print("Error: invalid command line arguments\n")
        print(usage_message)
        sys.exit()

    command_line_path = None
    use_3d_gui = False

    for option, path in options:
        if option == "-h":  # print the usage message
            print(usage_message)
            sys.exit()
        if option == "-c":  # use the command line user interface
            command_line_path = path
        elif option == "--3d":  # use the 3D graphical user interface
            use_3d_gui = True

    if command_line_path is not None and use_3d_gui:
        print("Error: choose either -c or --3d, not both\n")
        print(usage_message)
        sys.exit()

    # Initialise instances of the four inner simulator classes
    names = Names()
    devices = Devices(names)
    network = Network(names, devices)
    monitors = Monitors(names, devices, network)

    if command_line_path is not None:
        scanner = Scanner(command_line_path, names)
        parser = Parser(names, devices, network, monitors, scanner)
        if parser.parse_network():
            # Initialise an instance of the userint.UserInterface() class
            userint = UserInterface(names, devices, network, monitors)
            userint.command_interface()
        return

    if len(arguments) != 1:  # wrong number of arguments
        print("Error: one file path required\n")
        print(usage_message)
        sys.exit()

    [path] = arguments
    scanner = Scanner(path, names)
    parser = Parser(names, devices, network, monitors, scanner)
    success, diagnostics = parse_network_with_diagnostics(parser)
    startup_language = detect_startup_language()

    # Initialise wx here so GUI parse errors can be reported both in the
    # terminal and in a graphical dialog.
    import wx
    if use_3d_gui:
        from gui_3D import Gui3D as Gui
        from gui_3D import show_parse_error_dialog
    else:
        from gui import Gui, show_parse_error_dialog

    app = wx.App()
    if success:
        gui = Gui("Logic Simulator", path, names, devices, network,
                  monitors, startup_language)
        gui.Show(True)
        app.MainLoop()
    else:
        show_parse_error_dialog(None, path, diagnostics, startup_language)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
