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
import main
from main import (SAMPLE_RATE, Oscillator, clear_screen, flush_input,
                  generate_notch_yaml, generate_simulator_yaml, on_press,
                  parse_arguments, state)

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

    def test_callback_prints_status_on_error(self):
        """Test callback prints status to stderr when there's an error."""
        osc = Oscillator()
        osc.is_playing = True
        frames = 1024
        outdata = np.zeros((frames, 1), dtype=np.float32)

        with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
            osc.callback(outdata, frames, None, "underflow")
            assert "underflow" in mock_stderr.getvalue()

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

    @patch("main.HAS_MSVCRT", False)
    @patch("main.HAS_TERMIOS", True)
    def test_flush_input_with_termios(self):
        """Test flush_input uses termios on Unix/macOS."""
        with patch("main.termios") as mock_termios:
            mock_termios.TCIOFLUSH = 2
            flush_input()
            mock_termios.tcflush.assert_called_once()

    @patch("main.HAS_MSVCRT", False)
    @patch("main.HAS_TERMIOS", False)
    def test_flush_input_without_termios(self):
        """Test flush_input handles missing termios gracefully."""
        # Should not raise any exception
        flush_input()

    @pytest.mark.skipif(sys.platform != "win32", reason="msvcrt only available on Windows")
    @patch("main.HAS_TERMIOS", False)
    @patch("main.HAS_MSVCRT", True)
    def test_flush_input_with_msvcrt(self):
        """Test flush_input uses msvcrt on Windows."""
        with patch("main.msvcrt") as mock_msvcrt:
            mock_msvcrt.kbhit.return_value = False
            flush_input()
            mock_msvcrt.kbhit.assert_called_once()


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


# --- Input Handler Tests ---


class TestInputHandler:
    """Test suite for keyboard input handling."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset state before each test
        state["running"] = True
        state["mode"] = "MATCHING"
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

        initial_freq = main.osc.frequency
        on_press(mock_key)

        assert main.osc.frequency == initial_freq + state["step"]

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

        initial_freq = main.osc.frequency
        on_press(mock_key)

        assert main.osc.frequency == initial_freq - state["step"]

    def test_on_press_w_increases_volume(self):
        """Test 'w' key increases volume."""
        main.osc = Oscillator()
        main.osc.volume = 0.1
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

        initial_vol = main.osc.volume
        on_press(mock_key)

        assert main.osc.volume == pytest.approx(initial_vol + 0.05, abs=1e-6)

    def test_on_press_s_decreases_volume(self):
        """Test 's' key decreases volume."""
        main.osc = Oscillator()
        main.osc.volume = 0.5
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

        initial_vol = main.osc.volume
        on_press(mock_key)

        assert main.osc.volume == pytest.approx(initial_vol - 0.05, abs=1e-6)


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
