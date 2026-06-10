"""Load and select GUI languages for the logic simulator."""

import json
import locale as python_locale
import os
from pathlib import Path


DEFAULT_LANGUAGE = "en"
CATALOGUE_PATH = Path(__file__).with_name("locales") / "gui_text.json"
LANGUAGE_ALIASES = {
    "arabic": "ar",
    "deutsch": "de",
    "english": "en",
    "french": "fr",
    "german": "de",
    "spanish": "es",
}
WINDOWS_PRIMARY_LANGUAGE_IDS = {
    0x01: "ar",
    0x07: "de",
    0x09: "en",
    0x0A: "es",
    0x0C: "fr",
}
LINUX_LANGUAGE_KEYS = ["Language", "LANGUAGE", "LC_MESSAGES", "LANG"]


def supported_language_code(locale_name, supported_languages=None):
    """Return a supported language code parsed from a locale name."""
    supported_languages = set(supported_languages or [])
    code = normalise_language_code(locale_name)
    if code and (not supported_languages or code in supported_languages):
        return code
    return None


def load_catalogue(path=CATALOGUE_PATH):
    """Return the JSON language catalogue, or a minimal English fallback."""
    try:
        with open(path, encoding="utf-8") as catalogue_file:
            return json.load(catalogue_file)
    except (OSError, json.JSONDecodeError):
        return {
            "languages": {DEFAULT_LANGUAGE: "English"},
            "translations": {
                DEFAULT_LANGUAGE: {
                    "window_title": "Logic Simulator",
                    "status_prefix": "Status",
                }
            },
        }


def load_translations(path=CATALOGUE_PATH):
    """Return translations keyed first by language code, then text key."""
    catalogue = load_catalogue(path)
    translations = catalogue.get("translations", {})
    if DEFAULT_LANGUAGE not in translations:
        translations[DEFAULT_LANGUAGE] = {}
    return translations


def load_language_names(path=CATALOGUE_PATH):
    """Return display names for languages available in the catalogue."""
    catalogue = load_catalogue(path)
    return catalogue.get("languages", {DEFAULT_LANGUAGE: "English"})


def normalise_language_code(locale_name):
    """Extract a language code from a locale name such as es_ES.utf8."""
    if not locale_name:
        return None

    locale_name = str(locale_name).strip()
    if not locale_name or locale_name.upper() in {"C", "POSIX"}:
        return None

    locale_name = locale_name.split(":", 1)[0]
    locale_name = locale_name.split(".", 1)[0]
    locale_name = locale_name.split("@", 1)[0]
    locale_name = locale_name.replace("-", "_")
    code = locale_name.split("_", 1)[0].lower()
    return LANGUAGE_ALIASES.get(code, code)


def language_from_environment(environ=None, supported_languages=None):
    """Return the language requested by process locale environment vars."""
    if environ is None:
        environ = os.environ

    supported_languages = set(supported_languages or [])
    for variable in ["LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"]:
        code = normalise_language_code(environ.get(variable))
        if code and (not supported_languages or code in supported_languages):
            return code

    return None


def language_from_wx_locale(wx_module, supported_languages=None):
    """Return the desktop/account language reported by wx.Locale metadata."""
    if wx_module is None or not hasattr(wx_module, "Locale"):
        return None

    supported_languages = set(supported_languages or [])
    try:
        language_id = wx_module.Locale.GetSystemLanguage()
        language_info = wx_module.Locale.GetLanguageInfo(language_id)
    except (AttributeError, TypeError, RuntimeError):
        language_info = None

    for attribute_name in ["CanonicalName", "canonicalName", "Description"]:
        locale_name = getattr(language_info, attribute_name, None)
        code = normalise_language_code(locale_name)
        if code and (not supported_languages or code in supported_languages):
            return code

    return None


def language_from_python_locale(supported_languages=None, locale_module=None):
    """Return the desktop/account language reported by Python locale."""
    if locale_module is None:
        locale_module = python_locale

    locale_names = []
    try:
        locale_names.append(locale_module.getlocale()[0])
    except (AttributeError, TypeError, ValueError):
        pass

    try:
        locale_names.append(locale_module.getdefaultlocale()[0])
    except (AttributeError, TypeError, ValueError):
        pass

    supported_languages = set(supported_languages or [])
    for locale_name in locale_names:
        code = normalise_language_code(locale_name)
        if code and (not supported_languages or code in supported_languages):
            return code

    return None


def running_under_wsl(environ=None, osrelease_path=None):
    """Return True when the process appears to be running under WSL."""
    if environ is None:
        environ = os.environ
    if environ.get("WSL_DISTRO_NAME") or environ.get("WSL_INTEROP"):
        return True

    if osrelease_path is None:
        osrelease_path = Path("/proc/sys/kernel/osrelease")

    try:
        with open(osrelease_path, encoding="utf-8") as osrelease_file:
            osrelease = osrelease_file.read().lower()
    except OSError:
        return False

    return "microsoft" in osrelease or "wsl" in osrelease


def wsl_windows_locale_names(environ=None, command_runner=None,
                             osrelease_path=None):
    """Return Windows UI locale names when launched from WSL."""
    if not running_under_wsl(environ, osrelease_path):
        return []

    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "$PSUICulture; (Get-UICulture).Name; "
        "[System.Globalization.CultureInfo]::CurrentUICulture.Name",
    ]

    try:
        if command_runner is None:
            import subprocess
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        else:
            result = command_runner(command)
    except (OSError, TypeError):
        return []
    except Exception:
        return []

    output = getattr(result, "stdout", result)
    return [line.strip() for line in str(output).splitlines() if line.strip()]


def linux_locale_config_paths(environ=None):
    """Return likely Linux desktop locale configuration paths."""
    if environ is None:
        environ = os.environ
        include_system_paths = True
    else:
        include_system_paths = False

    paths = []
    user_name = environ.get("USER") or environ.get("LOGNAME")
    home_path = environ.get("HOME")
    config_home = environ.get("XDG_CONFIG_HOME")

    if user_name:
        paths.append(Path("/var/lib/AccountsService/users") / user_name)
    if home_path:
        paths.append(Path(home_path) / ".pam_environment")
    if config_home:
        paths.append(Path(config_home) / "locale.conf")
    elif home_path:
        paths.append(Path(home_path) / ".config" / "locale.conf")
    if include_system_paths:
        paths.extend([Path("/etc/locale.conf"), Path("/etc/default/locale")])

    return paths


def locale_config_values(path):
    """Return key/value pairs from a Linux locale-style config file."""
    values = {}
    try:
        with open(path, encoding="utf-8") as config_file:
            lines = config_file.readlines()
    except OSError:
        return values

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue

        if " DEFAULT=" in line:
            key, value = line.split(" DEFAULT=", 1)
        elif " OVERRIDE=" in line:
            key, value = line.split(" OVERRIDE=", 1)
        elif "=" in line:
            key, value = line.split("=", 1)
        else:
            continue

        key = key.strip()
        value = value.strip().strip("\"'")
        values.setdefault(key, value)

    return values


def language_from_linux_locale(supported_languages=None, environ=None,
                               config_paths=None):
    """Return the Linux desktop/account language, when configured."""
    supported_languages = set(supported_languages or [])
    if config_paths is None:
        config_paths = linux_locale_config_paths(environ)

    for path in config_paths:
        values = locale_config_values(path)
        for key in LINUX_LANGUAGE_KEYS:
            code = supported_language_code(values.get(key),
                                           supported_languages)
            if code:
                return code

    return None


def windows_locale_names_and_ids(windows_api=None, environ=None,
                                 wsl_command_runner=None,
                                 osrelease_path=None):
    """Return Windows locale names and language IDs, when available."""
    if windows_api is not None:
        return (
            list(windows_api.get_locale_names()),
            list(windows_api.get_language_ids()),
        )

    wsl_locale_names = wsl_windows_locale_names(
        environ, wsl_command_runner, osrelease_path
    )
    if wsl_locale_names:
        return wsl_locale_names, []

    try:
        import ctypes
    except ImportError:
        return [], []

    kernel32 = getattr(getattr(ctypes, "windll", None), "kernel32", None)
    if kernel32 is None:
        return [], []
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)

    locale_names = []
    language_ids = []

    try:
        mui_language_name = 0x8
        language_count = ctypes.c_ulong()
        buffer_length = ctypes.c_ulong()
        kernel32.GetUserPreferredUILanguages(
            mui_language_name,
            ctypes.byref(language_count),
            None,
            ctypes.byref(buffer_length),
        )
        if buffer_length.value:
            buffer = ctypes.create_unicode_buffer(buffer_length.value)
            if kernel32.GetUserPreferredUILanguages(
                mui_language_name,
                ctypes.byref(language_count),
                buffer,
                ctypes.byref(buffer_length),
            ):
                locale_names.extend(
                    name for name in "".join(buffer).split("\x00") if name
                )
    except (AttributeError, OSError, TypeError):
        pass

    try:
        buffer = ctypes.create_unicode_buffer(85)
        if kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
            locale_names.append(buffer.value)
    except (AttributeError, OSError, TypeError):
        pass

    try:
        buffer = ctypes.create_unicode_buffer(85)
        if kernel32.GetSystemDefaultLocaleName(buffer, len(buffer)):
            locale_names.append(buffer.value)
    except (AttributeError, OSError, TypeError):
        pass

    if user32 is not None:
        try:
            language_ids.append(user32.GetKeyboardLayout(0) & 0xFFFF)
        except (AttributeError, OSError, TypeError):
            pass

    for function_name in [
        "GetUserDefaultUILanguage",
        "GetUserDefaultLangID",
        "GetSystemDefaultUILanguage",
    ]:
        try:
            language_ids.append(getattr(kernel32, function_name)())
        except (AttributeError, OSError, TypeError):
            pass

    return locale_names, language_ids


def language_from_windows_locale(supported_languages=None, windows_api=None,
                                 environ=None, wsl_command_runner=None,
                                 osrelease_path=None):
    """Return the Windows account or display language, when available."""
    supported_languages = set(supported_languages or [])
    locale_names, language_ids = windows_locale_names_and_ids(
        windows_api,
        environ,
        wsl_command_runner,
        osrelease_path,
    )

    for language_id in language_ids:
        try:
            primary_language_id = int(language_id) & 0x3FF
        except (TypeError, ValueError):
            continue
        code = WINDOWS_PRIMARY_LANGUAGE_IDS.get(primary_language_id)
        if code and (not supported_languages or code in supported_languages):
            return code

    for locale_name in locale_names:
        code = normalise_language_code(locale_name)
        if code and (not supported_languages or code in supported_languages):
            return code

    return None


def non_default_language(language_code):
    """Return the language code unless it is the English fallback."""
    if language_code and language_code != DEFAULT_LANGUAGE:
        return language_code
    return None


def wx_language_id(wx_module, language_code):
    """Return the wx language constant for a catalogue language code."""
    constant_names = {
        "ar": ["LANGUAGE_ARABIC", "LANGUAGE_ARABIC_SAUDI_ARABIA"],
        "de": ["LANGUAGE_GERMAN"],
        "en": ["LANGUAGE_ENGLISH", "LANGUAGE_ENGLISH_UK"],
        "es": ["LANGUAGE_SPANISH"],
        "fr": ["LANGUAGE_FRENCH"],
    }
    for constant_name in constant_names.get(language_code, []):
        if hasattr(wx_module, constant_name):
            return getattr(wx_module, constant_name)
    return getattr(wx_module, "LANGUAGE_DEFAULT", -1)


def initialise_wx_locale(wx_module, language_code=DEFAULT_LANGUAGE):
    """Initialise and return a wx.Locale object for this application."""
    if wx_module is None or not hasattr(wx_module, "Locale"):
        return None
    if language_code == DEFAULT_LANGUAGE:
        return None

    try:
        language_id = wx_language_id(wx_module, language_code)
        if (
            hasattr(wx_module.Locale, "IsAvailable")
            and not wx_module.Locale.IsAvailable(language_id)
        ):
            return None
        locale_object = wx_module.Locale()
        if not locale_object.Init(language_id):
            return None
    except (AttributeError, TypeError, RuntimeError):
        return None

    return locale_object


def choose_language(translations, wx_module=None, environ=None,
                    locale_module=None, windows_api=None,
                    linux_config_paths=None, wsl_command_runner=None,
                    osrelease_path=None):
    """Choose the best available language for the GUI."""
    supported_languages = set(translations)
    environment_language = language_from_environment(
        environ, supported_languages
    )
    language_code = non_default_language(environment_language)
    if language_code:
        return language_code

    language_code = language_from_windows_locale(
        supported_languages,
        windows_api,
        environ,
        wsl_command_runner,
        osrelease_path,
    )
    if language_code:
        return language_code

    language_code = language_from_wx_locale(wx_module, supported_languages)
    if language_code:
        return language_code

    language_code = language_from_linux_locale(
        supported_languages, environ, linux_config_paths
    )
    if language_code:
        return language_code

    language_code = language_from_python_locale(
        supported_languages, locale_module
    )
    if language_code:
        return language_code

    if environment_language:
        return environment_language

    return DEFAULT_LANGUAGE


def translate(translations, language_code, key):
    """Return translated text, falling back to English and then the key."""
    selected_language = translations.get(language_code, {})
    english = translations.get(DEFAULT_LANGUAGE, {})
    return selected_language.get(key, english.get(key, key))
