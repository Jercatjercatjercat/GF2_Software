"""Test GUI language catalogue selection."""

from types import SimpleNamespace

from logsim import detect_startup_language
from language import (
    choose_language,
    language_from_environment,
    language_from_python_locale,
    language_from_windows_locale,
    load_language_names,
    load_translations,
    normalise_language_code,
    translate,
    wx_language_id,
)


def test_normalise_language_code_reads_locale_prefix():
    """Test if locale names reduce to supported language codes."""
    assert normalise_language_code("es_ES.utf8") == "es"
    assert normalise_language_code("de-DE") == "de"
    assert normalise_language_code("ar-EG") == "ar"
    assert normalise_language_code("Spanish_Spain") == "es"
    assert normalise_language_code("C") is None


def test_language_from_environment_uses_lang_for_logsim_only():
    """Test if LANG can select Spanish for the current process."""
    translations = load_translations()
    environ = {"LANG": "es_ES.utf8"}

    assert language_from_environment(environ, translations) == "es"
    assert choose_language(translations, environ=environ) == "es"


def test_language_from_environment_accepts_arabic_locale():
    """Test if LANG can select Arabic for the current process."""
    translations = load_translations()
    environ = {"LANG": "ar_SA.utf8"}

    assert language_from_environment(environ, translations) == "ar"
    assert choose_language(translations, environ=environ) == "ar"


def test_lang_overrides_other_locale_variables_for_logsim():
    """Test if LANG is the explicit launch override from the handout."""
    translations = load_translations()
    environ = {
        "LANG": "ar_SA.utf8",
        "LANGUAGE": "en_GB.utf8",
        "LC_ALL": "en_GB.utf8",
        "LC_MESSAGES": "en_GB.utf8",
    }

    assert language_from_environment(environ, translations) == "ar"
    assert choose_language(translations, environ=environ) == "ar"


def test_choose_language_uses_python_account_locale_when_env_unset():
    """Test if the account locale can select Spanish at startup."""
    translations = load_translations()

    class FakeLocaleModule:
        """Small stand-in for the Python locale module."""

        @staticmethod
        def getlocale():
            """Return a fake active locale."""
            return "es_ES", "UTF-8"

        @staticmethod
        def getdefaultlocale():
            """Return a fake account/default locale."""
            return "es_ES", "UTF-8"

    assert language_from_python_locale(translations, FakeLocaleModule) == "es"
    assert choose_language(
        translations, environ={}, locale_module=FakeLocaleModule
    ) == "es"


def test_env_lang_overrides_python_account_locale():
    """Test if explicit LANG beats the account locale."""
    translations = load_translations()

    class FakeLocaleModule:
        """Small stand-in for the Python locale module."""

        @staticmethod
        def getlocale():
            """Return a fake active locale."""
            return "es_ES", "UTF-8"

        @staticmethod
        def getdefaultlocale():
            """Return a fake account/default locale."""
            return "es_ES", "UTF-8"

    assert choose_language(
        translations,
        environ={"LANG": "ar_SA.utf8"},
        locale_module=FakeLocaleModule,
    ) == "ar"


def test_logsim_detects_startup_language_before_wx_starts():
    """Test if logsim preserves account language before wx.App exists."""

    class FakeLocaleModule:
        """Small stand-in for the Python locale module."""

        @staticmethod
        def getlocale():
            """Return a fake active locale."""
            return "es_ES", "UTF-8"

        @staticmethod
        def getdefaultlocale():
            """Return a fake account/default locale."""
            return "es_ES", "UTF-8"

    assert detect_startup_language({}, FakeLocaleModule) == "es"


def test_choose_language_uses_windows_display_language():
    """Test if Windows UI locale can select Spanish at startup."""
    translations = load_translations()

    class NoLocaleModule:
        """Small stand-in for an unset Python locale module."""

        @staticmethod
        def getlocale():
            """Return no active locale."""
            return None, None

        @staticmethod
        def getdefaultlocale():
            """Return no default locale."""
            return None, None

    class FakeWindowsApi:
        """Small stand-in for Windows locale APIs."""

        @staticmethod
        def get_locale_names():
            """Return fake Windows locale names."""
            return ["Spanish_Spain"]

        @staticmethod
        def get_language_ids():
            """Return no fake Windows language IDs."""
            return []

    assert language_from_windows_locale(translations, FakeWindowsApi) == "es"
    assert choose_language(
        translations,
        environ={},
        locale_module=NoLocaleModule,
        windows_api=FakeWindowsApi,
    ) == "es"


def test_windows_display_language_overrides_python_locale():
    """Test if Windows UI language wins over Python's locale fallback."""
    translations = load_translations()

    class EnglishLocaleModule:
        """Small stand-in for Python reporting an English locale."""

        @staticmethod
        def getlocale():
            """Return a fake active locale."""
            return "en_GB", "UTF-8"

        @staticmethod
        def getdefaultlocale():
            """Return a fake account/default locale."""
            return "en_GB", "UTF-8"

    class FakeWindowsApi:
        """Small stand-in for Windows locale APIs."""

        @staticmethod
        def get_locale_names():
            """Return a fake Windows Spanish UI locale."""
            return ["es-ES"]

        @staticmethod
        def get_language_ids():
            """Return no fake Windows language IDs."""
            return []

    assert choose_language(
        translations,
        environ={},
        locale_module=EnglishLocaleModule,
        windows_api=FakeWindowsApi,
    ) == "es"


def test_windows_language_id_overrides_english_locale_name():
    """Test if active Windows language ID can choose Spanish."""
    translations = load_translations()

    class FakeWindowsApi:
        """Small stand-in for Windows locale APIs."""

        @staticmethod
        def get_locale_names():
            """Return fake English Windows locale names."""
            return ["en-GB", "en-US"]

        @staticmethod
        def get_language_ids():
            """Return a fake Spanish language ID."""
            return [0x0C0A]

    assert language_from_windows_locale(translations, FakeWindowsApi) == "es"


def test_logsim_detects_windows_language_before_wx_starts():
    """Test if logsim preserves Windows UI language before wx.App exists."""

    class NoLocaleModule:
        """Small stand-in for an unset Python locale module."""

        @staticmethod
        def getlocale():
            """Return no active locale."""
            return None, None

        @staticmethod
        def getdefaultlocale():
            """Return no default locale."""
            return None, None

    class FakeWindowsApi:
        """Small stand-in for Windows locale APIs."""

        @staticmethod
        def get_locale_names():
            """Return no fake Windows locale names."""
            return []

        @staticmethod
        def get_language_ids():
            """Return a fake Spanish UI language ID."""
            return [0x0A]

    assert detect_startup_language(
        {}, NoLocaleModule, FakeWindowsApi
    ) == "es"


def test_wx_language_id_uses_selected_language_constant():
    """Test if wx.Locale is initialised with the selected language."""
    fake_wx = SimpleNamespace(
        LANGUAGE_DEFAULT=-1,
        LANGUAGE_SPANISH=2,
        LANGUAGE_ARABIC=3,
    )

    assert wx_language_id(fake_wx, "es") == 2
    assert wx_language_id(fake_wx, "ar") == 3
    assert wx_language_id(fake_wx, "unknown") == -1


def test_choose_language_uses_wx_account_locale_when_env_unset():
    """Test if the desktop/account language can select a catalogue."""
    translations = load_translations()

    class NoLocaleModule:
        """Small stand-in for an unset Python locale module."""

        @staticmethod
        def getlocale():
            """Return no active locale."""
            return None, None

        @staticmethod
        def getdefaultlocale():
            """Return no default locale."""
            return None, None

    class FakeLocale:
        """Small stand-in for wx.Locale."""

        @staticmethod
        def GetSystemLanguage():
            """Return a fake wx language ID."""
            return 1

        @staticmethod
        def GetLanguageInfo(_language_id):
            """Return fake desktop language information."""
            return SimpleNamespace(CanonicalName="fr_FR")

    class NoWindowsApi:
        """Small stand-in for unavailable Windows locale APIs."""

        @staticmethod
        def get_locale_names():
            """Return no fake Windows locale names."""
            return []

        @staticmethod
        def get_language_ids():
            """Return no fake Windows language IDs."""
            return []

    fake_wx = SimpleNamespace(Locale=FakeLocale)

    assert choose_language(
        translations,
        fake_wx,
        environ={},
        locale_module=NoLocaleModule,
        windows_api=NoWindowsApi,
    ) == "fr"


def test_translate_falls_back_to_english():
    """Test if missing translations fall back to English text."""
    translations = {"en": {"hello": "Hello"}, "es": {}}

    assert translate(translations, "es", "hello") == "Hello"
    assert translate(translations, "es", "missing") == "missing"


def test_catalogue_contains_non_latin_sample():
    """Test if the GUI can display arbitrary non-Latin characters."""
    translations = load_translations()
    about_text = translations["es"]["about_text"]

    assert "\u03a9" in about_text
    assert "\u0416" in about_text
    assert "\u4e2d" in about_text


def test_catalogue_contains_arabic_language():
    """Test if the catalogue contains Arabic GUI labels."""
    translations = load_translations()
    language_names = load_language_names()

    assert language_names["ar"] == "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"
    assert translations["ar"]["window_title"] == (
        "\u0645\u062d\u0627\u0643\u064a "
        "\u0627\u0644\u0645\u0646\u0637\u0642"
    )
    assert translations["ar"]["language"] == "\u0627\u0644\u0644\u063a\u0629"


def test_arabic_translation_has_complete_gui_key_set():
    """Test if Arabic translates every English GUI text key."""
    translations = load_translations()

    assert set(translations["ar"]) == set(translations["en"])
