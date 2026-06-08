"""Test GUI language catalogue selection."""

from types import SimpleNamespace

from language import (
    choose_language,
    language_from_environment,
    load_language_names,
    load_translations,
    normalise_language_code,
    translate,
)


def test_normalise_language_code_reads_locale_prefix():
    """Test if locale names reduce to supported language codes."""
    assert normalise_language_code("es_ES.utf8") == "es"
    assert normalise_language_code("de-DE") == "de"
    assert normalise_language_code("ar-EG") == "ar"
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


def test_choose_language_uses_wx_account_locale_when_env_unset():
    """Test if the desktop/account language can select a catalogue."""
    translations = load_translations()

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

    fake_wx = SimpleNamespace(Locale=FakeLocale)

    assert choose_language(translations, fake_wx, environ={}) == "fr"


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
