import argparse
import sys
import threading
import time
import traceback

import numpy as np
import sounddevice as sd
from colorama import Back, Fore, Style, init
from pynput import keyboard

# Try to import termios for terminal control (Unix/macOS)
try:
    import termios

    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

# Try to import msvcrt for terminal control (Windows)
try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# Initialize colorama
init(autoreset=True)

# --- AUDIO CONFIGURATION ---
SAMPLE_RATE = 44100


class Oscillator:
    """
    Sine wave generator with phase continuity and fade envelopes.

    Implements smooth fade-in/fade-out to prevent clicks and pops,
    as required for hearing safety.
    """

    # Fade duration in milliseconds (10ms is typically inaudible)
    FADE_DURATION_MS = 10.0

    def __init__(self, initial_frequency: float = 1000.0):
        self.frequency = max(20, min(20000, initial_frequency))
        self.volume = 0.1
        self.phase = 0.0
        self.is_playing = False
        self.lock = threading.Lock()

        # Fade envelope state
        self._fade_samples = int(SAMPLE_RATE * self.FADE_DURATION_MS / 1000.0)
        self._current_gain = 0.0  # Current envelope gain (0.0 to 1.0)
        self._target_gain = 0.0  # Target envelope gain

    def callback(self, outdata, frames, _time, status):
        # Note: We intentionally don't log status here to avoid I/O in the
        # real-time audio callback thread. Status errors (e.g., buffer underruns)
        # are typically transient and handled by sounddevice internally.
        _ = status  # Acknowledge parameter to satisfy linters

        with self.lock:
            # Update target gain based on playing state
            self._target_gain = 1.0 if self.is_playing else 0.0

            # Check if we need to generate audio (playing or fading out)
            if self._current_gain == 0.0 and self._target_gain == 0.0:
                outdata.fill(0)
                return

            # Generate sine wave (always generate during fade-out to avoid clicks)
            phase_increment = 2 * np.pi * self.frequency / SAMPLE_RATE
            phases = self.phase + np.arange(frames) * phase_increment
            signal = self.volume * np.sin(phases)
            self.phase = (self.phase + frames * phase_increment) % (2 * np.pi)

            # Apply fade envelope
            envelope = self._generate_fade_envelope(frames)
            signal = signal * envelope

            outdata[:] = signal.reshape(-1, 1).astype(np.float32)

    def _generate_fade_envelope(self, frames: int) -> np.ndarray:
        """
        Generate a linear fade envelope for the given number of frames.

        Uses vectorized NumPy operations for efficient real-time audio processing.

        Args:
            frames: Number of audio frames in the buffer.

        Returns:
            numpy array of envelope values (0.0 to 1.0) for each frame.
        """
        # If already at target gain, return a constant envelope
        if self._current_gain == self._target_gain:
            return np.full(frames, self._current_gain, dtype=np.float32)

        # Determine fade direction: +1 for fade in, -1 for fade out
        direction = 1.0 if self._target_gain > self._current_gain else -1.0
        fade_step = direction * (1.0 / self._fade_samples)

        # Vectorized computation of envelope over all frames
        idx = np.arange(1, frames + 1, dtype=np.float32)
        gains = self._current_gain + idx * fade_step

        if direction > 0:
            # Fade in: clamp so we do not overshoot the target
            envelope = np.minimum(gains, self._target_gain).astype(np.float32)
        else:
            # Fade out: clamp so we do not undershoot the target
            envelope = np.maximum(gains, self._target_gain).astype(np.float32)

        # Update current gain to the last value for continuity across callbacks
        self._current_gain = float(envelope[-1])

        return envelope

    def set_frequency(self, freq):
        with self.lock:
            self.frequency = max(20, min(20000, freq))

    def set_volume(self, vol):
        with self.lock:
            self.volume = max(0.0, min(1.0, vol))

    def get_fade_samples(self) -> int:
        """
        Get the number of samples used for fade transitions.

        Returns:
            Number of samples in the fade envelope.
        """
        with self.lock:
            return self._fade_samples

    def get_current_gain(self) -> float:
        """
        Get the current envelope gain value.

        Returns:
            Current gain value (0.0 to 1.0).
        """
        with self.lock:
            return self._current_gain

    def set_current_gain_for_testing(self, gain: float):
        """
        Set the current envelope gain for testing purposes.

        Args:
            gain: Gain value to set (0.0 to 1.0).
        """
        with self.lock:
            self._current_gain = max(0.0, min(1.0, gain))

    def get_frequency(self) -> float:
        """
        Get the current frequency in a thread-safe manner.

        Returns:
            Current frequency in Hz (20-20000).
        """
        with self.lock:
            return self.frequency

    def get_volume(self) -> float:
        """
        Get the current volume in a thread-safe manner.

        Returns:
            Current volume (0.0 to 1.0).
        """
        with self.lock:
            return self.volume

    def set_is_playing(self, playing: bool):
        """
        Set the is_playing state in a thread-safe manner.

        Args:
            playing: True to start playing, False to stop.
        """
        with self.lock:
            self.is_playing = playing

    def get_is_playing(self) -> bool:
        """
        Get the is_playing state in a thread-safe manner.

        Returns:
            True if currently playing, False otherwise.
        """
        with self.lock:
            return self.is_playing


# --- STATE LOGIC ---


class ThreadSafeDict(dict):
    """
    A thread-safe dictionary wrapper using an internal lock.

    Ensures concurrent gets/sets from multiple threads (keyboard listener
    and main thread) do not race.
    """

    # Explicitly mark as unhashable (mutable container)
    __hash__ = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()

    def __eq__(self, other):
        """Compare dictionaries, ignoring the lock attribute."""
        if isinstance(other, dict):
            with self._lock:
                return dict.__eq__(self, other)
        return NotImplemented

    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(self, key, value):
        with self._lock:
            return super().__setitem__(key, value)

    def __delitem__(self, key):
        with self._lock:
            return super().__delitem__(key)

    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)

    def __len__(self):
        with self._lock:
            return super().__len__()

    def __iter__(self):
        with self._lock:
            return iter(list(super().keys()))

    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)

    def update(self, *args, **kwargs):
        with self._lock:
            return super().update(*args, **kwargs)

    def keys(self):
        with self._lock:
            return list(super().keys())

    def values(self):
        with self._lock:
            return list(super().values())

    def items(self):
        with self._lock:
            return list(super().items())

    def pop(self, key, *args):
        with self._lock:
            return super().pop(key, *args)

    def setdefault(self, key, default=None):
        with self._lock:
            return super().setdefault(key, default)

    def clear(self):
        with self._lock:
            return super().clear()


osc = None  # Will be initialized in main() with optional frequency
state = ThreadSafeDict(
    {
        "running": True,
        "mode": "MATCHING",
        "step": 100,
        "base_freq": 0,
        "octave_option": 0,
        "final_freq": 0,
    }
)

# --- CAMILLA DSP YAML GENERATORS ---


def generate_notch_yaml(freq: float) -> str:
    """
    Generates the therapeutic filter: Removes the tinnitus frequency.

    Args:
        freq: Target frequency in Hz to remove.

    Returns:
        YAML configuration string for CamillaDSP notch filter.
    """
    return f"""
# Tinnitus NOTCH Filter (Therapeutic)
# Target frequency: {freq:.2f} Hz
# Purpose: Remove energy at this frequency for habituation therapy.

filters:
  my_notch:
    type: Biquad
    parameters:
      type: Notch
      freq: {freq:.1f}
      q: 10.0   # Narrow Q for precise targeting
      gain: 0

pipeline:
  - type: Filter
    channels: [0, 1]
    names:
      - my_notch
""".lstrip(
        "\n"
    )


def generate_simulator_yaml(freq: float) -> str:
    """
    Generates the simulator filter: Exaggerates the tinnitus frequency.

    Uses a Peaking filter with high positive gain.

    Args:
        freq: Target frequency in Hz to boost.

    Returns:
        YAML configuration string for CamillaDSP peaking filter.
    """
    return f"""
# Tinnitus SIMULATOR (Empathy)
# Target frequency: {freq:.2f} Hz
# Purpose: Aggressively boost this frequency to simulate the symptom.
# WARNING: Lower the volume before applying.

filters:
  tinnitus_sim:
    type: Biquad
    parameters:
      type: Peaking
      freq: {freq:.1f}
      q: 20.0    # Very narrow Q, pure tone
      gain: 12.0 # +12dB gain at that frequency

pipeline:
  - type: Filter
    channels: [0, 1]
    names:
      - tinnitus_sim
""".lstrip(
        "\n"
    )


# --- UI & UTILITIES ---
def clear_screen():
    print("\033[H\033[J", end="")


def flush_input():
    """
    Flush the terminal input buffer to prevent key presses from appearing after exit.
    """
    if HAS_TERMIOS:
        try:
            # Flush stdin buffer
            termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        except (termios.error, OSError):
            # Terminal may not support flushing, safe to ignore
            pass
    elif HAS_MSVCRT:
        # Fallback for Windows: try to read and discard any pending input
        try:
            while msvcrt.kbhit():
                msvcrt.getch()
        except OSError:
            # Windows terminal may not support kbhit/getch, safe to ignore
            pass


def print_interface():
    # Guard against osc not yet being initialized
    if osc is None:
        return

    clear_screen()
    print(Fore.CYAN + Style.BRIGHT + "========================================")
    print(Fore.CYAN + Style.BRIGHT + "       TINNITUS FREQUENCY MATCHER       ")
    print(Fore.CYAN + Style.BRIGHT + "========================================")
    print("")

    if state["mode"] == "MATCHING":
        step_value = state["step"]
        freq = osc.get_frequency()
        vol = osc.get_volume()
        print(f"Frequency: {Fore.YELLOW}{freq:.2f} Hz{Fore.RESET}")
        print(f"Volume:    {Fore.GREEN}{int(vol * 100)}%{Fore.RESET}")
        print(f"Step:      {step_value} Hz")
        print("")
        print(Fore.WHITE + Back.BLUE + " CONTROLS: ")
        print(" [⬆/⬇] Adjust Frequency")
        print(" [⮕/⬅] Change precision (1, 10, 100... Hz)")
        print(" [W/S]   Increase/Decrease Volume")
        print(" [ENTER] Confirm and verify Octave")
        print(" [ESC]   Exit")

    elif state["mode"] == "OCTAVE_CHECK":
        base = state["base_freq"]
        opts = [base, base / 2, base * 2]
        labels = ["Original", "-1 Octave", "+1 Octave"]

        print(Fore.MAGENTA + "OCTAVE VERIFICATION")
        print("Select which one sounds identical to your tinnitus:")
        print("")

        for i in range(3):
            prefix = " > " if state["octave_option"] == i else "   "
            color = Fore.GREEN if state["octave_option"] == i else Fore.WHITE
            print(f"{color}{prefix}{labels[i]}: {opts[i]:.2f} Hz")

        print("")
        print(Fore.WHITE + Back.BLUE + " [ENTER] Generate Configuration Files ")


def on_press(key):
    # Guard against osc not yet being initialized
    if osc is None:
        return

    try:
        if key == keyboard.Key.esc:
            state["running"] = False
            return  # Don't return False, let listener continue until main loop stops

        if state["mode"] == "MATCHING":
            if key == keyboard.Key.up:
                current_freq = osc.get_frequency()
                osc.set_frequency(current_freq + state["step"])
            elif key == keyboard.Key.down:
                current_freq = osc.get_frequency()
                osc.set_frequency(current_freq - state["step"])
            elif key == keyboard.Key.right:
                state["step"] = min(1000, state["step"] * 10)
            elif key == keyboard.Key.left:
                state["step"] = max(1, state["step"] // 10)
            elif hasattr(key, "char") and key.char in ("+", "w"):
                current_vol = osc.get_volume()
                osc.set_volume(current_vol + 0.05)
            elif hasattr(key, "char") and key.char in ("-", "s"):
                current_vol = osc.get_volume()
                osc.set_volume(current_vol - 0.05)
            elif key == keyboard.Key.enter:
                state["base_freq"] = osc.get_frequency()
                state["mode"] = "OCTAVE_CHECK"
                osc.set_frequency(state["base_freq"])

        elif state["mode"] == "OCTAVE_CHECK":
            base = state["base_freq"]
            opts = [base, base / 2, base * 2]

            if key == keyboard.Key.up:
                state["octave_option"] = (state["octave_option"] - 1) % 3
            elif key == keyboard.Key.down:
                state["octave_option"] = (state["octave_option"] + 1) % 3
            elif key == keyboard.Key.enter:
                state["final_freq"] = opts[state["octave_option"]]
                state["mode"] = "FINISHED"
                state["running"] = False
                return  # Don't return False, let listener continue until main loop stops

            osc.set_frequency(opts[state["octave_option"]])

        print_interface()
    except AttributeError:
        # Some key events (e.g., special keys without a .char attribute) can raise AttributeError.
        # These are safe to ignore so that the listener continues processing other key presses.
        pass


def parse_arguments():
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Tinnitus Frequency Matcher - Identify your tinnitus frequency and generate CamillaDSP filters"
    )
    parser.add_argument(
        "-f",
        "--frequency",
        type=float,
        default=1000.0,
        help="Initial frequency in Hz to start from (default: 1000.0). Must be between 20 and 20000 Hz.",
    )
    args = parser.parse_args()

    # Validate frequency range
    if not 20 <= args.frequency <= 20000:
        parser.error("Frequency must be between 20 and 20000 Hz")

    return args


def main():
    args = parse_arguments()

    # Initialize oscillator with the specified frequency
    global osc
    osc = Oscillator(initial_frequency=args.frequency)

    # Initialize audio stream with error handling
    try:
        stream = sd.OutputStream(
            channels=1,
            samplerate=SAMPLE_RATE,
            callback=osc.callback,
        )
    except sd.PortAudioError as e:
        print(
            f"{Fore.RED}Error: Could not initialize audio output device: {e}",
            file=sys.stderr,
        )
        return
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Log full exception details for debugging unexpected errors
        print(
            f"{Fore.RED}Unexpected error while initializing audio output: {e}",
            file=sys.stderr,
        )
        print(
            f"{Fore.RED}Full traceback:\n{traceback.format_exc()}",
            file=sys.stderr,
        )
        return

    with stream:
        osc.set_is_playing(True)
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        print_interface()
        try:
            while state["running"]:
                time.sleep(0.1)
        except KeyboardInterrupt:
            state["running"] = False
        finally:
            # Ensure listener stops and all events are processed
            if listener.is_alive():
                listener.stop()
            listener.join(timeout=1.0)
            # Flush input buffer to prevent keys from appearing
            flush_input()
            # Small delay to ensure all suppressed keys are processed
            time.sleep(0.1)

    if state["mode"] == "FINISHED":
        clear_screen()
        final_f = state["final_freq"]
        print(Fore.GREEN + Style.BRIGHT + "PROCESS COMPLETED!")
        print(f"Detected frequency: {final_f:.2f} Hz\n")

        # Generate Notch (Therapy)
        notch_file = "camilla_notch_therapy.yml"
        try:
            with open(notch_file, "w", encoding="utf-8") as f:
                f.write(generate_notch_yaml(final_f))
            print(f"1. Therapeutic filter saved to: {Fore.YELLOW}{notch_file}")
        except OSError as e:
            print(
                f"{Fore.RED}Error: Could not write therapeutic filter "
                f"'{notch_file}': {e}",
                file=sys.stderr,
            )

        # Generate Simulator (Empathy)
        sim_file = "camilla_simulator.yml"
        try:
            with open(sim_file, "w", encoding="utf-8") as f:
                f.write(generate_simulator_yaml(final_f))
            print(f"2. Tinnitus simulator saved to: {Fore.YELLOW}{sim_file}")
        except OSError as e:
            print(
                f"{Fore.RED}Error: Could not write simulator file "
                f"'{sim_file}': {e}",
                file=sys.stderr,
            )

        print(f"\n{Fore.CYAN}Copy these files to your CamillaDSP configuration folder.")


if __name__ == "__main__":
    main()
