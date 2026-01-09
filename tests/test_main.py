"""
Unit tests for the Tinnitus Frequency Matcher application.

These tests mock sounddevice and pynput for CI/CD environments
without audio hardware or physical keyboard.
"""

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Mock pynput before importing main module
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Mock sounddevice before importing main module
sys.modules["sounddevice"] = MagicMock()

# Now import the module under test (must be after mocking)
# pylint: disable=wrong-import-position
from src import main
from src.main import (SAMPLE_RATE, Oscillator, clear_screen, flush_input,
                      generate_notch_yaml, generate_simulator_yaml, on_press,
                      parse_arguments, print_interface, state)

# pylint: enable=wrong-import-position


# --- Oscillator Tests ---


class TestOscillator:
    """Test suite for the Oscillator class."""

    def test_init_default_frequency(self):
        """Test Oscillator initializes with default frequency of 1000 Hz."""
        osc = Oscillator()
        assert osc.frequency == 1000.0

    def test_init_custom_frequency(self):
        """Test Oscillator initializes with custom frequency."""
        osc = Oscillator(initial_frequency=4590.0)
        assert osc.frequency == 4590.0

    def test_init_frequency_clamped_to_minimum(self):
        """Test frequency is clamped to minimum 20 Hz."""
        osc = Oscillator(initial_frequency=10.0)
        assert osc.frequency == 20

    def test_init_frequency_clamped_to_maximum(self):
        """Test frequency is clamped to maximum 20000 Hz."""
        osc = Oscillator(initial_frequency=25000.0)
        assert osc.frequency == 20000

    def test_init_default_volume(self):
        """Test Oscillator initializes with default volume of 0.1 (10%)."""
        osc = Oscillator()
        assert osc.volume == 0.1

    def test_init_default_phase(self):
        """Test Oscillator initializes with phase 0."""
        osc = Oscillator()
        assert osc.phase == 0.0

    def test_init_not_playing(self):
        """Test Oscillator is not playing by default."""
        osc = Oscillator()
        assert osc.is_playing is False

    def test_set_frequency_valid(self):
        """Test setting a valid frequency."""
        osc = Oscillator()
        osc.set_frequency(5000.0)
        assert osc.frequency == 5000.0

    def test_set_frequency_clamped_minimum(self):
        """Test frequency is clamped to minimum when setting below 20 Hz."""
        osc = Oscillator()
        osc.set_frequency(5.0)
        assert osc.frequency == 20

    def test_set_frequency_clamped_maximum(self):
        """Test frequency is clamped to maximum when setting above 20000 Hz."""
        osc = Oscillator()
        osc.set_frequency(30000.0)
        assert osc.frequency == 20000

    def test_set_volume_valid(self):
        """Test setting a valid volume."""
        osc = Oscillator()
        osc.set_volume(0.5)
        assert osc.volume == 0.5

    def test_set_volume_clamped_minimum(self):
        """Test volume is clamped to minimum 0.0."""
        osc = Oscillator()
        osc.set_volume(-0.5)
        assert osc.volume == 0.0

    def test_set_volume_clamped_maximum(self):
        """Test volume is clamped to maximum 1.0."""
        osc = Oscillator()
        osc.set_volume(1.5)
        assert osc.volume == 1.0

    def test_callback_fills_zeros_when_not_playing(self):
        """Test callback fills output with zeros when not playing."""
        osc = Oscillator()
        osc.is_playing = False
        frames = 1024
        outdata = np.zeros((frames, 1), dtype=np.float32)

        osc.callback(outdata, frames, None, None)

        np.testing.assert_array_equal(outdata, np.zeros((frames, 1)))

    def test_callback_generates_sine_wave_when_playing(self):
        """Test callback generates non-zero output when playing."""
        osc = Oscillator(initial_frequency=440.0)
        osc.is_playing = True
        osc.volume = 0.5
        frames = 1024
        outdata = np.zeros((frames, 1), dtype=np.float32)

        osc.callback(outdata, frames, None, None)

        # Output should not be all zeros
        assert not np.all(outdata == 0)
        # Output should be within volume bounds
        assert np.max(np.abs(outdata)) <= osc.volume + 1e-6

    def test_callback_maintains_phase_continuity(self):
        """Test callback maintains phase continuity across calls."""
        osc = Oscillator(initial_frequency=1000.0)
        osc.is_playing = True
        osc.volume = 1.0
        frames = 512

        # First callback
        outdata1 = np.zeros((frames, 1), dtype=np.float32)
        osc.callback(outdata1, frames, None, None)
        phase_after_first = osc.phase

        # Second callback
        outdata2 = np.zeros((frames, 1), dtype=np.float32)
        osc.callback(outdata2, frames, None, None)
        phase_after_second = osc.phase

        # Phase should have advanced
        assert phase_after_first != 0.0 or phase_after_second != phase_after_first

    def test_callback_output_shape(self):
        """Test callback produces correct output shape."""
        osc = Oscillator()
        osc.is_playing = True
        frames = 2048
        outdata = np.zeros((frames, 1), dtype=np.float32)

        osc.callback(outdata, frames, None, None)

        assert outdata.shape == (frames, 1)

    def test_callback_handles_status_without_crash(self):
        """Test callback handles status parameter gracefully without I/O.

        Note: We intentionally don't print status in the callback to avoid
        I/O in the real-time audio thread. This test verifies the callback
        doesn't crash when a status is passed.
        """
        osc = Oscillator()
        osc.is_playing = True
        frames = 1024
        outdata = np.zeros((frames, 1), dtype=np.float32)

        # Callback should handle status gracefully without crashing
        osc.callback(outdata, frames, None, "underflow")
        # Verify audio was still generated
        assert not np.all(outdata == 0)

    def test_thread_safety_frequency(self):
        """Test set_frequency is thread-safe (uses lock)."""
        osc = Oscillator()

        # Verify lock is acquired during set_frequency
        with patch.object(osc, "lock") as mock_lock:
            mock_lock.__enter__ = MagicMock(return_value=None)
            mock_lock.__exit__ = MagicMock(return_value=None)
            osc.set_frequency(5000.0)
            mock_lock.__enter__.assert_called()

    def test_thread_safety_volume(self):
        """Test set_volume is thread-safe (uses lock)."""
        osc = Oscillator()

        # Verify lock is acquired during set_volume
        with patch.object(osc, "lock") as mock_lock:
            mock_lock.__enter__ = MagicMock(return_value=None)
            mock_lock.__exit__ = MagicMock(return_value=None)
            osc.set_volume(0.5)
            mock_lock.__enter__.assert_called()

    def test_fade_envelope_initialization(self):
        """Test fade envelope state is properly initialized."""
        osc = Oscillator()

        assert osc.get_current_gain() == 0.0
        assert osc.get_fade_samples() > 0

    def test_fade_in_gradual_amplitude_increase(self):
        """Test audio fades in gradually instead of starting at full amplitude."""
        osc = Oscillator(initial_frequency=1000.0)
        osc.volume = 1.0
        osc.is_playing = True
        frames = 512

        outdata = np.zeros((frames, 1), dtype=np.float32)
        osc.callback(outdata, frames, None, None)

        # First sample should NOT be at full amplitude (fade-in in progress)
        # The signal starts at 0 gain and ramps up
        first_samples = np.abs(outdata[:10].flatten())
        last_samples = np.abs(outdata[-10:].flatten())

        # First samples should have lower amplitude than later samples
        assert np.mean(first_samples) < np.mean(last_samples)

    def test_fade_out_gradual_amplitude_decrease(self):
        """Test audio fades out gradually instead of stopping abruptly."""
        osc = Oscillator(initial_frequency=1000.0)
        osc.volume = 1.0
        osc.is_playing = True
        osc.set_current_gain_for_testing(1.0)  # Simulate already playing at full gain
        frames = 512

        # First, generate audio while playing
        outdata1 = np.zeros((frames, 1), dtype=np.float32)
        osc.callback(outdata1, frames, None, None)

        # Now stop playing and generate another buffer (should fade out)
        osc.is_playing = False
        outdata2 = np.zeros((frames, 1), dtype=np.float32)
        osc.callback(outdata2, frames, None, None)

        # Fade-out buffer should have decreasing amplitude
        first_samples = np.abs(outdata2[:10].flatten())
        last_samples = np.abs(outdata2[-10:].flatten())

        # First samples should have higher amplitude than later samples (fading out)
        assert np.mean(first_samples) > np.mean(last_samples)

    def test_no_abrupt_start_prevents_clicks(self):
        """Test that audio never starts at full amplitude (prevents clicks)."""
        osc = Oscillator(initial_frequency=1000.0)
        osc.volume = 1.0
        osc.is_playing = True
        frames = 64  # Small buffer to catch the first samples

        outdata = np.zeros((frames, 1), dtype=np.float32)
        osc.callback(outdata, frames, None, None)

        # First sample should be near zero, not at full volume
        # (allowing small tolerance for floating point)
        assert np.abs(outdata[0, 0]) < osc.volume * 0.1

    def test_no_abrupt_stop_prevents_clicks(self):
        """Test that audio never stops abruptly (prevents clicks)."""
        osc = Oscillator(initial_frequency=1000.0)
        osc.volume = 1.0
        osc.is_playing = True
        osc.set_current_gain_for_testing(1.0)  # Simulate fully playing
        frames = 64

        # Stop playing
        osc.is_playing = False
        outdata = np.zeros((frames, 1), dtype=np.float32)
        osc.callback(outdata, frames, None, None)

        # Audio should still be generated during fade-out (not all zeros)
        assert not np.all(outdata == 0)

    def test_fade_duration_reasonable(self):
        """Test fade duration is in a reasonable range for inaudible transitions."""
        osc = Oscillator()

        # Fade should be between 5ms and 50ms (typical range for click-free audio)
        fade_duration_ms = (osc.get_fade_samples() / SAMPLE_RATE) * 1000
        assert 5 <= fade_duration_ms <= 50


# --- YAML Generator Tests ---


class TestYAMLGenerators:
    """Test suite for YAML configuration generators."""

    def test_generate_notch_yaml_contains_frequency(self):
        """Test notch YAML contains the target frequency."""
        freq = 4590.0
        yaml_output = generate_notch_yaml(freq)

        assert "4590.00" in yaml_output or "4590.0" in yaml_output

    def test_generate_notch_yaml_contains_filter_type(self):
        """Test notch YAML specifies Notch filter type."""
        yaml_output = generate_notch_yaml(1000.0)

        assert "type: Notch" in yaml_output

    def test_generate_notch_yaml_contains_biquad(self):
        """Test notch YAML uses Biquad filter."""
        yaml_output = generate_notch_yaml(1000.0)

        assert "type: Biquad" in yaml_output

    def test_generate_notch_yaml_contains_pipeline(self):
        """Test notch YAML contains pipeline configuration."""
        yaml_output = generate_notch_yaml(1000.0)

        assert "pipeline:" in yaml_output
        assert "channel: 0" in yaml_output
        assert "channel: 1" in yaml_output

    def test_generate_notch_yaml_contains_q_factor(self):
        """Test notch YAML contains Q factor."""
        yaml_output = generate_notch_yaml(1000.0)

        assert "q: 10.0" in yaml_output

    def test_generate_notch_yaml_therapeutic_comment(self):
        """Test notch YAML contains therapeutic comment."""
        yaml_output = generate_notch_yaml(1000.0)

        assert "Therapeutic" in yaml_output

    def test_generate_simulator_yaml_contains_frequency(self):
        """Test simulator YAML contains the target frequency."""
        freq = 8000.0
        yaml_output = generate_simulator_yaml(freq)

        assert "8000.00" in yaml_output or "8000.0" in yaml_output

    def test_generate_simulator_yaml_contains_filter_type(self):
        """Test simulator YAML specifies Peaking filter type."""
        yaml_output = generate_simulator_yaml(1000.0)

        assert "type: Peaking" in yaml_output

    def test_generate_simulator_yaml_contains_gain(self):
        """Test simulator YAML contains positive gain."""
        yaml_output = generate_simulator_yaml(1000.0)

        assert "gain: 12.0" in yaml_output

    def test_generate_simulator_yaml_contains_warning(self):
        """Test simulator YAML contains volume warning."""
        yaml_output = generate_simulator_yaml(1000.0)

        assert "WARNING" in yaml_output

    def test_generate_simulator_yaml_contains_pipeline(self):
        """Test simulator YAML contains pipeline for both channels."""
        yaml_output = generate_simulator_yaml(1000.0)

        assert "pipeline:" in yaml_output
        assert "channel: 0" in yaml_output
        assert "channel: 1" in yaml_output

    def test_generate_simulator_yaml_narrow_q(self):
        """Test simulator YAML has narrow Q for pure tone."""
        yaml_output = generate_simulator_yaml(1000.0)

        assert "q: 20.0" in yaml_output

    def test_yaml_generators_different_frequencies(self):
        """Test YAML generators produce different output for different frequencies."""
        yaml1 = generate_notch_yaml(1000.0)
        yaml2 = generate_notch_yaml(5000.0)

        assert yaml1 != yaml2
        assert "1000.0" in yaml1
        assert "5000.0" in yaml2


# --- Argument Parser Tests ---


class TestArgumentParser:
    """Test suite for command line argument parsing."""

    def test_parse_arguments_default_frequency(self):
        """Test default frequency is 1000 Hz."""
        with patch("sys.argv", ["main.py"]):
            args = parse_arguments()
            assert args.frequency == 1000.0

    def test_parse_arguments_custom_frequency_short_flag(self):
        """Test custom frequency with -f flag."""
        with patch("sys.argv", ["main.py", "-f", "4590"]):
            args = parse_arguments()
            assert args.frequency == 4590.0

    def test_parse_arguments_custom_frequency_long_flag(self):
        """Test custom frequency with --frequency flag."""
        with patch("sys.argv", ["main.py", "--frequency", "8000"]):
            args = parse_arguments()
            assert args.frequency == 8000.0

    def test_parse_arguments_float_frequency(self):
        """Test float frequency value."""
        with patch("sys.argv", ["main.py", "-f", "4590.5"]):
            args = parse_arguments()
            assert args.frequency == 4590.5

    def test_parse_arguments_invalid_frequency_too_low(self):
        """Test error for frequency below 20 Hz."""
        with patch("sys.argv", ["main.py", "-f", "10"]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_parse_arguments_invalid_frequency_too_high(self):
        """Test error for frequency above 20000 Hz."""
        with patch("sys.argv", ["main.py", "-f", "25000"]):
            with pytest.raises(SystemExit):
                parse_arguments()

    def test_parse_arguments_boundary_frequency_min(self):
        """Test minimum valid frequency (20 Hz)."""
        with patch("sys.argv", ["main.py", "-f", "20"]):
            args = parse_arguments()
            assert args.frequency == 20.0

    def test_parse_arguments_boundary_frequency_max(self):
        """Test maximum valid frequency (20000 Hz)."""
        with patch("sys.argv", ["main.py", "-f", "20000"]):
            args = parse_arguments()
            assert args.frequency == 20000.0


# --- UI Function Tests ---


class TestUIFunctions:
    """Test suite for UI utility functions."""

    def test_clear_screen_outputs_escape_sequence(self):
        """Test clear_screen outputs ANSI escape sequence."""
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            clear_screen()
            output = mock_stdout.getvalue()
            assert "\033[H\033[J" in output

    @patch("src.main.HAS_MSVCRT", False)
    @patch("src.main.HAS_TERMIOS", True)
    def test_flush_input_with_termios(self):
        """Test flush_input uses termios on Unix/macOS."""
        with patch("src.main.termios") as mock_termios:
            mock_termios.TCIOFLUSH = 2
            flush_input()
            mock_termios.tcflush.assert_called_once()

    @patch("src.main.HAS_MSVCRT", False)
    @patch("src.main.HAS_TERMIOS", False)
    def test_flush_input_without_termios(self):
        """Test flush_input handles missing termios gracefully."""
        # Should not raise any exception
        flush_input()

    @pytest.mark.skipif(
        sys.platform != "win32", reason="msvcrt only available on Windows"
    )
    @patch("src.main.HAS_TERMIOS", False)
    @patch("src.main.HAS_MSVCRT", True)
    def test_flush_input_with_msvcrt(self):
        """Test flush_input uses msvcrt on Windows."""
        with patch("src.main.msvcrt") as mock_msvcrt:
            mock_msvcrt.kbhit.return_value = False
            flush_input()
            mock_msvcrt.kbhit.assert_called_once()

    def test_print_interface_returns_early_if_osc_is_none(self):
        """Test print_interface returns early when osc is None."""
        original_osc = main.osc
        try:
            main.osc = None
            # Should not raise any exception
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                print_interface()
                # Nothing should be printed when osc is None
                assert mock_stdout.getvalue() == ""
        finally:
            main.osc = original_osc

    def test_print_interface_matching_mode(self):
        """Test print_interface displays correctly in MATCHING mode."""
        main.osc = Oscillator(initial_frequency=1000.0)
        state["mode"] = "MATCHING"
        state["step"] = 100

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_interface()
            output = mock_stdout.getvalue()
            assert "TINNITUS FREQUENCY MATCHER" in output
            assert "1000.00 Hz" in output
            assert "CONTROLS" in output

    def test_print_interface_octave_check_mode(self):
        """Test print_interface displays correctly in OCTAVE_CHECK mode."""
        main.osc = Oscillator(initial_frequency=4000.0)
        state["mode"] = "OCTAVE_CHECK"
        state["base_freq"] = 4000.0
        state["octave_option"] = 0

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_interface()
            output = mock_stdout.getvalue()
            assert "OCTAVE VERIFICATION" in output
            assert "Original" in output
            assert "-1 Octave" in output
            assert "+1 Octave" in output


# --- State Management Tests ---


class TestStateManagement:
    """Test suite for application state management."""

    def test_initial_state_values(self):
        """Test initial state dictionary values."""
        # Note: state might be modified by other tests, so we check structure
        assert "running" in state
        assert "mode" in state
        assert "step" in state
        assert "base_freq" in state
        assert "octave_option" in state
        assert "final_freq" in state

    def test_thread_safe_dict_getitem(self):
        """Test ThreadSafeDict __getitem__ is thread-safe."""
        state["test_key"] = "test_value"
        assert state["test_key"] == "test_value"

    def test_thread_safe_dict_setitem(self):
        """Test ThreadSafeDict __setitem__ is thread-safe."""
        state["new_key"] = 42
        assert state["new_key"] == 42

    def test_thread_safe_dict_get(self):
        """Test ThreadSafeDict get method with default."""
        assert state.get("nonexistent_key", "default") == "default"
        state["existing_key"] = "value"
        assert state.get("existing_key") == "value"

    def test_thread_safe_dict_update(self):
        """Test ThreadSafeDict update method."""
        state.update({"update_key": "updated"})
        assert state["update_key"] == "updated"


# --- Input Handler Tests ---


class TestInputHandler:
    """Test suite for keyboard input handling."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset state before each test
        state["running"] = True
        state["mode"] = "MATCHING"

    def test_on_press_returns_early_if_osc_is_none(self):
        """Test on_press returns early when osc is None."""
        original_osc = main.osc
        original_running = state["running"]
        try:
            main.osc = None
            mock_key = MagicMock()
            mock_key.char = "w"
            # Should not raise any exception
            on_press(mock_key)
            # State should not change when osc is None
            assert state["running"] == original_running
        finally:
            main.osc = original_osc
            # Reset state for test isolation
            state["step"] = 100
            state["base_freq"] = 0
            state["octave_option"] = 0
            state["final_freq"] = 0

    def test_on_press_esc_stops_running(self):
        """Test ESC key stops the application."""
        # Initialize osc for the test
        main.osc = Oscillator()
        state["running"] = True

        # Create a sentinel object for ESC key
        esc_key = object()
        main.keyboard.Key.esc = esc_key
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        on_press(esc_key)

        assert state["running"] is False

    def test_on_press_up_increases_frequency(self):
        """Test UP arrow increases frequency."""
        main.osc = Oscillator(initial_frequency=1000.0)
        state["mode"] = "MATCHING"
        state["step"] = 100

        mock_key = MagicMock()
        main.keyboard.Key.up = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        # Make mock_key equal to keyboard.Key.up
        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.up

        initial_freq = main.osc.get_frequency()
        on_press(mock_key)

        assert main.osc.get_frequency() == initial_freq + state["step"]

    def test_on_press_down_decreases_frequency(self):
        """Test DOWN arrow decreases frequency."""
        main.osc = Oscillator(initial_frequency=1000.0)
        state["mode"] = "MATCHING"
        state["step"] = 100

        mock_key = MagicMock()
        main.keyboard.Key.down = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.down

        initial_freq = main.osc.get_frequency()
        on_press(mock_key)

        assert main.osc.get_frequency() == initial_freq - state["step"]

    def test_on_press_w_increases_volume(self):
        """Test 'w' key increases volume."""
        main.osc = Oscillator()
        main.osc.set_volume(0.1)
        state["mode"] = "MATCHING"

        mock_key = MagicMock()
        mock_key.char = "w"
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        # Mock comparisons to return False
        mock_key.__eq__ = lambda self, other: False

        initial_vol = main.osc.get_volume()
        on_press(mock_key)

        assert main.osc.get_volume() == pytest.approx(initial_vol + 0.05, abs=1e-6)

    def test_on_press_s_decreases_volume(self):
        """Test 's' key decreases volume."""
        main.osc = Oscillator()
        main.osc.set_volume(0.5)
        state["mode"] = "MATCHING"

        mock_key = MagicMock()
        mock_key.char = "s"
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: False

        initial_vol = main.osc.get_volume()
        on_press(mock_key)

        assert main.osc.get_volume() == pytest.approx(initial_vol - 0.05, abs=1e-6)

    def test_on_press_plus_increases_volume(self):
        """Test '+' key increases volume."""
        main.osc = Oscillator()
        main.osc.set_volume(0.1)
        state["mode"] = "MATCHING"

        mock_key = MagicMock()
        mock_key.char = "+"
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: False

        initial_vol = main.osc.get_volume()
        on_press(mock_key)

        assert main.osc.get_volume() == pytest.approx(initial_vol + 0.05, abs=1e-6)

    def test_on_press_minus_decreases_volume(self):
        """Test '-' key decreases volume."""
        main.osc = Oscillator()
        main.osc.set_volume(0.5)
        state["mode"] = "MATCHING"

        mock_key = MagicMock()
        mock_key.char = "-"
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: False

        initial_vol = main.osc.get_volume()
        on_press(mock_key)

        assert main.osc.get_volume() == pytest.approx(initial_vol - 0.05, abs=1e-6)

    def test_on_press_right_increases_step(self):
        """Test RIGHT arrow increases step precision."""
        state["mode"] = "MATCHING"
        state["step"] = 100

        mock_key = MagicMock()
        main.keyboard.Key.right = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.right

        initial_step = state["step"]
        on_press(mock_key)

        assert state["step"] == min(1000, initial_step * 10)

    def test_on_press_left_decreases_step(self):
        """Test LEFT arrow decreases step precision."""
        state["mode"] = "MATCHING"
        state["step"] = 100

        mock_key = MagicMock()
        main.keyboard.Key.left = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.right = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.left

        initial_step = state["step"]
        on_press(mock_key)

        assert state["step"] == max(1, initial_step // 10)
        assert isinstance(state["step"], int)  # Ensure it remains an integer

    def test_on_press_enter_in_matching_mode(self):
        """Test ENTER key in MATCHING mode transitions to OCTAVE_CHECK."""
        main.osc = Oscillator(initial_frequency=4590.0)
        state["mode"] = "MATCHING"
        state["base_freq"] = 0

        mock_key = MagicMock()
        main.keyboard.Key.enter = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.left = MagicMock()
        main.keyboard.Key.right = MagicMock()

        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.enter

        current_freq = main.osc.get_frequency()
        on_press(mock_key)

        assert state["mode"] == "OCTAVE_CHECK"
        assert state["base_freq"] == current_freq

    def test_on_press_enter_in_octave_check_mode(self):
        """Test ENTER key in OCTAVE_CHECK mode finalizes frequency."""
        main.osc = Oscillator(initial_frequency=4590.0)
        state["mode"] = "OCTAVE_CHECK"
        state["base_freq"] = 4590.0
        state["octave_option"] = 0
        state["final_freq"] = 0
        state["running"] = True

        mock_key = MagicMock()
        main.keyboard.Key.enter = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.down = MagicMock()

        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.enter

        base = state["base_freq"]
        opts = [base, base / 2, base * 2]
        expected_freq = opts[state["octave_option"]]

        on_press(mock_key)

        assert state["mode"] == "FINISHED"
        assert state["final_freq"] == expected_freq
        assert state["running"] is False

    def test_on_press_up_in_octave_check_mode(self):
        """Test UP arrow in OCTAVE_CHECK mode cycles octave options."""
        main.osc = Oscillator(initial_frequency=4590.0)
        state["mode"] = "OCTAVE_CHECK"
        state["base_freq"] = 4590.0
        state["octave_option"] = 1

        mock_key = MagicMock()
        main.keyboard.Key.up = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.down = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.up

        initial_option = state["octave_option"]
        on_press(mock_key)

        assert state["octave_option"] == (initial_option - 1) % 3

    def test_on_press_down_in_octave_check_mode(self):
        """Test DOWN arrow in OCTAVE_CHECK mode cycles octave options."""
        main.osc = Oscillator(initial_frequency=4590.0)
        state["mode"] = "OCTAVE_CHECK"
        state["base_freq"] = 4590.0
        state["octave_option"] = 1

        mock_key = MagicMock()
        main.keyboard.Key.down = mock_key
        main.keyboard.Key.esc = MagicMock()
        main.keyboard.Key.up = MagicMock()
        main.keyboard.Key.enter = MagicMock()

        mock_key.__eq__ = lambda self, other: other is main.keyboard.Key.down

        initial_option = state["octave_option"]
        on_press(mock_key)

        assert state["octave_option"] == (initial_option + 1) % 3


# --- Audio Configuration Tests ---


class TestAudioConfiguration:
    """Test suite for audio configuration constants."""

    def test_sample_rate_standard(self):
        """Test sample rate is standard 44100 Hz."""
        assert SAMPLE_RATE == 44100

    def test_sample_rate_positive(self):
        """Test sample rate is positive."""
        assert SAMPLE_RATE > 0


# --- Integration Tests ---


class TestIntegration:
    """Integration tests for the application workflow."""

    def test_oscillator_frequency_precision(self):
        """Test oscillator maintains frequency precision through operations."""
        osc = Oscillator(initial_frequency=4590.0)

        # Simulate adjustments
        osc.set_frequency(osc.frequency + 10)
        osc.set_frequency(osc.frequency - 5)
        osc.set_frequency(osc.frequency + 100)

        assert osc.frequency == 4695.0

    def test_yaml_generation_workflow(self):
        """Test complete YAML generation workflow."""
        detected_freq = 4590.0

        notch_yaml = generate_notch_yaml(detected_freq)
        sim_yaml = generate_simulator_yaml(detected_freq)

        # Both should be valid strings with content
        assert len(notch_yaml) > 100
        assert len(sim_yaml) > 100

        # Both should contain the frequency
        assert "4590" in notch_yaml
        assert "4590" in sim_yaml

    def test_signal_generation_mathematical_accuracy(self):
        """Test sine wave generation is mathematically accurate."""
        osc = Oscillator(initial_frequency=440.0)  # A4 note
        osc.is_playing = True
        osc.volume = 1.0
        osc.phase = 0.0

        frames = SAMPLE_RATE  # 1 second of audio
        outdata = np.zeros((frames, 1), dtype=np.float32)

        osc.callback(outdata, frames, None, None)

        # Calculate expected number of cycles in 1 second at 440 Hz
        # The signal should cross zero approximately 2 * 440 = 880 times
        signal = outdata.flatten()
        zero_crossings = np.where(np.diff(np.signbit(signal)))[0]

        # Allow some tolerance due to sampling
        expected_crossings = 2 * 440
        assert abs(len(zero_crossings) - expected_crossings) < 10
