"""Select a reliable GTK display backend before wx initialises.

Under Wayland compositors (including WSLg, where the simulator is marked)
GTK's native Wayland backend mishandles modal dialog stacking: file
dialogs opened from the menu bar can flash up and then vanish behind the
main window until focus changes.  Routing GTK through XWayland (the X11
backend) restores normal dialog behaviour, so prefer it whenever an X
display is actually reachable.  Setting ``GDK_BACKEND`` in the
environment beforehand still overrides this default.
"""

from __future__ import annotations

import os
import sys


def prefer_x11_backend(environ: object = None,
                       platform: str | None = None) -> str | None:
    """Prefer the x11 GDK backend on Linux when an X display exists.

    The choice only applies on Linux and only when ``DISPLAY`` is set, so
    a pure-Wayland session without XWayland keeps its native backend and
    other platforms are untouched.  Returns the resulting backend value
    (or ``None`` when no preference applies).
    """
    env = os.environ if environ is None else environ
    plat = sys.platform if platform is None else platform
    if plat.startswith("linux") and env.get("DISPLAY"):
        env.setdefault("GDK_BACKEND", "x11")
    return env.get("GDK_BACKEND")


prefer_x11_backend()
