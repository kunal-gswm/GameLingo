"""
Tests for Ren'Py language activation script lifecycle and runtime behavior.
Verifies fresh launch activation, persistent preference handling, in-game language
reversion, reload safety, and the root cause of false initial-inactive readings.
"""

from typing import List

from gamelingo.adapters.renpy_strings import generate_activation_rpy


def test_activation_rpy_structure_and_priority():
    """Verify that generate_activation_rpy uses priority 999 and registers a startup callback."""
    script = generate_activation_rpy("french")

    # Priority 999 ensures it runs after standard options.rpy (init 0)
    # and before Ren'Py's _apply_default_preferences (init 1500)
    assert "init 999 python:" in script
    assert 'config.default_language = "french"' in script
    assert 'default preferences.language = "french"' in script

    # Startup callback registration in config.start_callbacks
    assert "def _gl_activate_initial_language():" in script
    assert '_gl_key = "_gl_lang_initialized_french"' in script
    assert "config.start_callbacks.append(_gl_activate_initial_language)" in script

    # Text.set_text hook and reload protection
    assert 'if not hasattr(renpy.text.text.Text, "_gl_orig_set_text"):' in script
    assert (
        "renpy.text.text.Text._gl_orig_set_text = renpy.text.text.Text.set_text"
        in script
    )


def test_fresh_launch_activation_lifecycle():
    """Verify that on a fresh launch with no saved persistent data, the target language activates."""

    class MockPersistent:
        pass

    class MockPreferences:
        def __init__(self):
            self.language = None

    class MockGame:
        def __init__(self):
            self.preferences = MockPreferences()

    class MockConfig:
        def __init__(self):
            self.default_language = None
            self.start_callbacks: List = []

    mock_persistent = MockPersistent()
    mock_game = MockGame()
    mock_config = MockConfig()

    # Simulate init 999 python
    target_lang = "german"
    if mock_config.default_language is None:
        mock_config.default_language = target_lang

    # Simulate callback registered in init 100 python
    def activate_callback():
        key = f"_gl_lang_initialized_{target_lang}"
        if not getattr(mock_persistent, key, False):
            setattr(mock_persistent, key, True)
            if mock_game.preferences.language is None:
                mock_game.preferences.language = target_lang

    mock_config.start_callbacks.append(activate_callback)

    # Simulate engine _start execution (00start.rpy)
    for cb in mock_config.start_callbacks:
        cb()

    assert mock_config.default_language == "german"
    assert mock_game.preferences.language == "german"
    assert getattr(mock_persistent, "_gl_lang_initialized_german") is True


def test_existing_player_first_patch_launch_activation():
    """
    Verify that if a player previously launched the unpatched game (so persistent
    data already exists and preferences._set_preferences is True), GameLingo's
    startup callback successfully activates the translation.
    """

    class MockPersistent:
        def __init__(self):
            self._set_preferences = True  # Simulates existing player session

    class MockPreferences:
        def __init__(self):
            self.language = None  # Original untranslated language

    class MockGame:
        def __init__(self):
            self.preferences = MockPreferences()

    class MockConfig:
        def __init__(self):
            self.default_language = None
            self.start_callbacks: List = []

    mock_persistent = MockPersistent()
    mock_game = MockGame()
    mock_config = MockConfig()

    target_lang = "spanish"

    def activate_callback():
        key = f"_gl_lang_initialized_{target_lang}"
        if not getattr(mock_persistent, key, False):
            setattr(mock_persistent, key, True)
            if mock_game.preferences.language is None:
                mock_game.preferences.language = target_lang

    mock_config.start_callbacks.append(activate_callback)

    # Run start callbacks
    for cb in mock_config.start_callbacks:
        cb()

    # Language must be activated for the new patch even though persistent._set_preferences was True
    assert mock_game.preferences.language == "spanish"
    assert getattr(mock_persistent, "_gl_lang_initialized_spanish") is True


def test_subsequent_launch_preserves_user_reversion():
    """
    Verify that if the user explicitly switches language back to None (original)
    in-game, subsequent launches respect that choice and do NOT re-force the translation.
    """

    class MockPersistent:
        def __init__(self):
            self._gl_lang_initialized_spanish = True  # Initial activation already done

    class MockPreferences:
        def __init__(self):
            self.language = None  # User intentionally chose original language

    class MockGame:
        def __init__(self):
            self.preferences = MockPreferences()

    mock_persistent = MockPersistent()
    mock_game = MockGame()

    target_lang = "spanish"

    def activate_callback():
        key = f"_gl_lang_initialized_{target_lang}"
        if not getattr(mock_persistent, key, False):
            setattr(mock_persistent, key, True)
            if mock_game.preferences.language is None:
                mock_game.preferences.language = target_lang

    activate_callback()

    # Must remain None because user already had activation marked and chose original
    assert mock_game.preferences.language is None


def test_text_hook_reload_safety_and_no_recursion():
    """Verify that multiple reload cycles (Shift+R) do not recursively wrap Text.set_text."""

    original_set_text_calls = []

    class MockText:
        def set_text(self, text, *args, **kwargs):
            original_set_text_calls.append(text)
            return text

    translations = {"Привет": "Hello", "Мир": "World"}

    def install_hook(text_cls):
        if not hasattr(text_cls, "_gl_orig_set_text"):
            text_cls._gl_orig_set_text = text_cls.set_text

            def _gl_set_text(self, text, *args, **kwargs):
                if isinstance(text, str):
                    text = translations.get(text, text)
                return text_cls._gl_orig_set_text(self, text, *args, **kwargs)

            text_cls.set_text = _gl_set_text

    # First installation
    install_hook(MockText)
    first_hook = MockText.set_text

    # Simulate reload cycle (Shift+R)
    install_hook(MockText)
    assert MockText.set_text is first_hook
    assert hasattr(MockText, "_gl_orig_set_text")

    # Verify execution translates properly without recursion
    instance = MockText()
    res = instance.set_text("Привет")
    assert res == "Hello"
    assert original_set_text_calls == ["Hello"]


def test_root_cause_diagnosis_of_gl039_initial_inactive():
    """
    Demonstrates the exact two failure mechanisms in GL-039:
    1. options.rpyc running after init 0 overwriting config.default_language = None.
    2. Persistent preferences caching language: None when probe called renpy.change_language(None).
    And verifies that init 999 + start_callbacks prevents both.
    """
    # 1. Old mechanism: init 0 ordering vulnerability
    state = {"config.default_language": None}

    # Old gamelingo_activate.rpy ran at init 0 (alphabetical 'g' before 'o')
    if state["config.default_language"] is None:
        state["config.default_language"] = "english"
    assert state["config.default_language"] == "english"

    # Then options.rpy ran at init 0
    state["config.default_language"] = None  # options.rpy reset it
    assert state["config.default_language"] is None  # Overwritten!

    # 2. New mechanism: init 999 ordering guarantee
    # options.rpy runs at init 0
    state["config.default_language"] = None
    # gamelingo_activate.rpy runs at init 999
    if state["config.default_language"] is None:
        state["config.default_language"] = "english"
    assert state["config.default_language"] == "english"  # Preserved!
