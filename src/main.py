import argparse
import sys
import threading
import time

import numpy as np
import sounddevice as sd
from colorama import Back, Fore, Style, init
from pynput import keyboard

# Initialize colorama
init(autoreset=True)

# --- AUDIO CONFIGURATION ---
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024


class Oscillator:
    """
    Sine wave generator with phase continuity.
    """

    def __init__(self, initial_frequency: float = 1000.0):
        self.frequency = max(20, min(20000, initial_frequency))
        self.volume = 0.1
        self.phase = 0.0
        self.is_playing = False
        self.lock = threading.Lock()

    def callback(self, outdata, frames, _time, status):
        if status:
            print(status, file=sys.stderr)

        with self.lock:
            if not self.is_playing:
                outdata.fill(0)
                return

            phase_increment = 2 * np.pi * self.frequency / SAMPLE_RATE
            phases = self.phase + np.arange(frames) * phase_increment
            signal = self.volume * np.sin(phases)
            self.phase = (self.phase + frames * phase_increment) % (2 * np.pi)

            # Smooth fade in/out to avoid clicks when activating/deactivating
            outdata[:] = signal.reshape(-1, 1).astype(np.float32)

    def set_frequency(self, freq):
        with self.lock:
            self.frequency = max(20, min(20000, freq))

    def set_volume(self, vol):
        with self.lock:
            self.volume = max(0.0, min(1.0, vol))


# --- STATE LOGIC ---
osc = None  # Will be initialized in main() with optional frequency
state = {
    "running": True,
    "mode": "MATCHING",
    "step": 100,
    "base_freq": 0,
    "octave_option": 0,
    "final_freq": 0,
}

# --- CAMILLA DSP YAML GENERATORS ---


def generate_notch_yaml(freq):
    """
    Generates the therapeutic filter: Removes the tinnitus frequency.
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
      q: 10.0   # Wide Q to ensure coverage
      gain: 0

pipeline:
  - type: Filter
    channel: 0
    names:
      - my_notch
  - type: Filter
    channel: 1
    names:
      - my_notch
"""


def generate_simulator_yaml(freq):
    """
    Generates the simulator filter: Exaggerates the tinnitus frequency.
    Uses a Peaking filter with high positive gain.
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
    channel: 0
    names:
      - tinnitus_sim
  - type: Filter
    channel: 1
    names:
      - tinnitus_sim
"""


# --- UI & UTILITIES ---
def clear_screen():
    print("\033[H\033[J", end="")


def print_interface():
    clear_screen()
    print(Fore.CYAN + Style.BRIGHT + "========================================")
    print(Fore.CYAN + Style.BRIGHT + "       TINNITUS FREQUENCY MATCHER       ")
    print(Fore.CYAN + Style.BRIGHT + "========================================")
    print("")

    if state["mode"] == "MATCHING":
        step_value = state["step"]
        print(f"Frequency: {Fore.YELLOW}{osc.frequency:.2f} Hz{Fore.RESET}")
        print(f"Volume:    {Fore.GREEN}{int(osc.volume * 100)}%{Fore.RESET}")
        print(f"Step:      {step_value} Hz")
        print("")
        print(Fore.WHITE + Back.BLUE + " CONTROLS: ")
        print(" [⬆/⬇] Adjust Frequency")
        print(" [⮕/⬅] Change precision (1, 10, 100... Hz)")
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
    try:
        if key == keyboard.Key.esc:
            state["running"] = False
            return False

        if state["mode"] == "MATCHING":
            if key == keyboard.Key.up:
                osc.set_frequency(osc.frequency + state["step"])
            elif key == keyboard.Key.down:
                osc.set_frequency(osc.frequency - state["step"])
            elif key == keyboard.Key.right:
                state["step"] = min(1000, state["step"] * 10)
            elif key == keyboard.Key.left:
                state["step"] = max(1, state["step"] / 10)
            elif hasattr(key, "char") and key.char == "+":
                osc.set_volume(osc.volume + 0.05)
            elif hasattr(key, "char") and key.char == "-":
                osc.set_volume(osc.volume - 0.05)
            elif key == keyboard.Key.enter:
                state["base_freq"] = osc.frequency
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
                return False

            osc.set_frequency(opts[state["octave_option"]])

        print_interface()
    except AttributeError:
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

    stream = sd.OutputStream(channels=1, samplerate=SAMPLE_RATE, callback=osc.callback)
    with stream:
        osc.is_playing = True
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        print_interface()
        while state["running"]:
            time.sleep(0.1)
        listener.join()

    if state["mode"] == "FINISHED":
        clear_screen()
        final_f = state["final_freq"]
        print(Fore.GREEN + Style.BRIGHT + "PROCESS COMPLETED!")
        print(f"Detected frequency: {final_f:.2f} Hz\n")

        # Generate Notch (Therapy)
        notch_file = "camilla_notch_therapy.yml"
        with open(notch_file, "w", encoding="utf-8") as f:
            f.write(generate_notch_yaml(final_f))
        print(f"1. Therapeutic filter saved to: {Fore.YELLOW}{notch_file}")

        # Generate Simulator (Empathy)
        sim_file = "camilla_simulator.yml"
        with open(sim_file, "w", encoding="utf-8") as f:
            f.write(generate_simulator_yaml(final_f))
        print(f"2. Tinnitus simulator saved to: {Fore.YELLOW}{sim_file}")

        print(f"\n{Fore.CYAN}Copy these files to your CamillaDSP configuration folder.")


if __name__ == "__main__":
    main()
