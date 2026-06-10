# Internationalisation README

The graphical Logic Simulator supports multiple GUI languages through wxPython internationalisation. The editable source text is kept in a JSON catalogue, and compiled gettext catalogues are loaded through `wx.Locale` so GUI text is retrieved with `wx.GetTranslation`.

## Supported Languages

The editable source catalogue is stored in `logsim/locales/gui_text.json`. At startup, `logsim/language.py` compiles this JSON into temporary wx gettext catalogues such as `<temp>/logsim_wx_locale_.../es_ES/LC_MESSAGES/logsim.mo`.

The supported languages are:

- English: `en`
- Spanish: `es`
- Arabic: `ar`
- French: `fr`
- German: `de`

Every supported language currently has the same set of GUI text keys as English. If wx returns the untranslated key, the helper falls back to the JSON catalogue and then to English.

## How Startup Language Is Chosen

When the GUI starts, `logsim/logsim.py` calls `detect_startup_language()`. The language is chosen in this order:

1. Environment variables: `LANG`, `LC_ALL`, `LC_MESSAGES`, then `LANGUAGE`.
2. Windows display/account language, including WSL where available.
3. wxPython desktop locale metadata.
4. Linux desktop/account locale files.
5. Python locale from the user account.
6. English fallback.

The selected code is passed into `Gui(..., initial_language=...)`. `logsim/language.py` then initialises `wx.Locale`, registers the generated temporary catalogue directory as the catalogue lookup path, loads the `logsim` catalogue, and GUI labels are read using `wx.GetTranslation(key)`.

## Change Language From The GUI

1. Start the graphical simulator:

   ```bash
   python3 logsim/logsim.py examples/example1_mixed_combinational.txt
   ```

2. Click `Settings` in the top toolbar.
3. Open the `Language` submenu.
4. Select the desired language.

The window title, menu labels, toolbar buttons, side-panel labels, status messages, help/about text, circuit title, and oscilloscope labels update immediately.

## Start In A Specific Language From macOS/Linux

Set `LANG` only for this launch:

```bash
LANG=fr_FR.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=de_DE.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=es_ES.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=ar_SA.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
LANG=en_GB.utf8 python3 logsim/logsim.py examples/example1_mixed_combinational.txt
```

To clear a shell-level setting afterwards:

```bash
unset LANG
```

## Start In A Specific Language From PowerShell

Set `LANG` for the current PowerShell session:

```powershell
$env:LANG = "fr_FR.utf8"   # French
$env:LANG = "de_DE.utf8"   # German
$env:LANG = "es_ES.utf8"   # Spanish
$env:LANG = "ar_SA.utf8"   # Arabic
$env:LANG = "en_GB.utf8"   # English
```

Then run:

```powershell
python logsim\logsim.py examples\example1_mixed_combinational.txt
```

Clear it afterwards with:

```powershell
Remove-Item Env:LANG
```

## Add Or Edit A Translation

1. Open `logsim/locales/gui_text.json`.
2. Add or edit the language display name under `languages`.
3. Add or edit the matching dictionary under `translations`.
4. Keep the translated dictionary keys identical to the English keys.
5. Restart the simulator. The wx `.mo` catalogues are regenerated automatically from `gui_text.json`.
6. Run the language tests:

   ```bash
   pytest -q logsim/test_language.py
   ```

## Relevant Files

- `logsim/language.py`: chooses the startup language, initialises `wx.Locale`, loads the `logsim` gettext catalogue, and wraps `wx.GetTranslation`.
- `logsim/locales/gui_text.json`: editable source for GUI text.
- runtime temp directory `logsim_wx_locale_.../<locale>/LC_MESSAGES/logsim.mo`: compiled gettext catalogues generated from `gui_text.json` and loaded by wxPython.
- `logsim/gui.py`: applies translated labels from `wx.GetTranslation` and lets the user switch language from `Settings > Language`.
- `logsim/logsim.py`: detects the startup language before opening the GUI.
- `logsim/test_language.py`: verifies locale detection, fallback behaviour, Unicode/non-Latin support, wx catalogue loading, and catalogue completeness.
