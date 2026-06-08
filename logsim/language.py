"""Load and select GUI languages for the logic simulator."""

import json
import os
from pathlib import Path


DEFAULT_LANGUAGE = "en"
CATALOGUE_PATH = Path(__file__).with_name("locales") / "gui_text.json"


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
    return locale_name.split("_", 1)[0].lower()


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
    """Return the desktop/account language reported by wx.Locale."""
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

    try:
        locale_object = wx_module.Locale()
        default_language = getattr(wx_module, "LANGUAGE_DEFAULT", -1)
        locale_object.Init(default_language)
        code = normalise_language_code(locale_object.GetCanonicalName())
    except (AttributeError, TypeError, RuntimeError):
        return None

    if code and (not supported_languages or code in supported_languages):
        return code
    return None


def initialise_wx_locale(wx_module):
    """Initialise and return a wx.Locale object for this application."""
    if wx_module is None or not hasattr(wx_module, "Locale"):
        return None

    try:
        locale_object = wx_module.Locale()
        default_language = getattr(wx_module, "LANGUAGE_DEFAULT", -1)
        locale_object.Init(default_language)
    except (AttributeError, TypeError, RuntimeError):
        return None

    return locale_object


def choose_language(translations, wx_module=None, environ=None):
    """Choose the best available language for the GUI."""
    supported_languages = set(translations)
    language_code = language_from_environment(environ, supported_languages)
    if language_code:
        return language_code

    language_code = language_from_wx_locale(wx_module, supported_languages)
    if language_code:
        return language_code

    return DEFAULT_LANGUAGE


def translate(translations, language_code, key):
    """Return translated text, falling back to English and then the key."""
    selected_language = translations.get(language_code, {})
    english = translations.get(DEFAULT_LANGUAGE, {})
    return selected_language.get(key, english.get(key, key))
