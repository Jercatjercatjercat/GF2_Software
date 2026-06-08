#!/usr/bin/env python3
"""Parse command line options and arguments for the Logic Simulator.

This script parses options and arguments specified on the command line, and
runs either the command line user interface or the graphical user interface.

Usage
-----
Show help: logsim.py -h
Command line user interface: logsim.py -c <file path>
Graphical user interface: logsim.py <file path>
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
    language_from_environment,
    language_from_python_locale,
    load_translations,
)


def detect_startup_language(environ=None, locale_module=None):
    """Return an explicit process or account language, if one is set."""
    translations = load_translations()
    supported_languages = set(translations)
    return (
        language_from_environment(environ, supported_languages)
        or language_from_python_locale(supported_languages, locale_module)
    )


def main(arg_list):
    """Parse the command line options and arguments specified in arg_list.

    Run either the command line user interface, the graphical user interface,
    or display the usage message.
    """
    usage_message = ("Usage:\n"
                     "Show help: logsim.py -h\n"
                     "Command line user interface: logsim.py -c <file path>\n"
                     "Graphical user interface: logsim.py <file path>")
    try:
        options, arguments = getopt.getopt(arg_list, "hc:")
    except getopt.GetoptError:
        print("Error: invalid command line arguments\n")
        print(usage_message)
        sys.exit()

    # Initialise instances of the four inner simulator classes
    names = Names()
    devices = Devices(names)
    network = Network(names, devices)
    monitors = Monitors(names, devices, network)

    for option, path in options:
        if option == "-h":  # print the usage message
            print(usage_message)
            sys.exit()
        elif option == "-c":  # use the command line user interface
            scanner = Scanner(path, names)
            parser = Parser(names, devices, network, monitors, scanner)
            if parser.parse_network():
                # Initialise an instance of the userint.UserInterface() class
                userint = UserInterface(names, devices, network, monitors)
                userint.command_interface()

    if not options:  # no option given, use the graphical user interface

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
