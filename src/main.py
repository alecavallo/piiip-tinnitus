import sys
import time
import math
import threading
import numpy as np
import sounddevice as sd
from pynput import keyboard
from colorama import init, Fore, Style, Back

# Inicializar colorama
init(autoreset=True)

# --- CONFIGURACIÓN DE AUDIO ---
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024


class Oscillator:
    """
    Generador de onda sinusoidal con continuidad de fase.
    """

    def __init__(self):
        self.frequency = 1000.0
        self.volume = 0.1
        self.phase = 0.0
        self.is_playing = False
        self.lock = threading.Lock()

    def callback(self, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        with self.lock:
            if not self.is_playing:
                outdata.fill(0)
                return

            t = np.arange(frames) / SAMPLE_RATE
            phase_increment = 2 * np.pi * self.frequency / SAMPLE_RATE
            phases = self.phase + np.arange(frames) * phase_increment
            signal = self.volume * np.sin(phases)
            self.phase = (self.phase + frames * phase_increment) % (2 * np.pi)

            # Fade in/out suave para evitar clicks al activar/desactivar
            outdata[:] = signal.reshape(-1, 1).astype(np.float32)

    def set_frequency(self, freq):
        with self.lock:
            self.frequency = max(20, min(20000, freq))

    def set_volume(self, vol):
        with self.lock:
            self.volume = max(0.0, min(1.0, vol))


# --- LÓGICA DE ESTADO ---
osc = Oscillator()
state = {
    "running": True,
    "mode": "MATCHING",
    "step": 100,
    "base_freq": 0,
    "octave_option": 0,
    "final_freq": 0,
}

# --- GENERADORES YAML CAMILLA DSP ---


def generate_notch_yaml(freq):
    """
    Genera el filtro terapéutico: Elimina la frecuencia del tinnitus.
    """
    return f"""
# Tinnitus NOTCH Filter (Terapéutico)
# Frecuencia objetivo: {freq:.2f} Hz
# Objetivo: Eliminar la energía en esta frecuencia para habituación.

filters:
  my_notch:
    type: Biquad
    parameters:
      type: Notch
      freq: {freq:.1f}
      q: 10.0   # Q ancho para asegurar cobertura
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
    Genera el filtro simulador: Exagera la frecuencia del tinnitus.
    Usa un Peaking filter con ganancia positiva alta.
    """
    return f"""
# Tinnitus SIMULATOR (Empatía)
# Frecuencia objetivo: {freq:.2f} Hz
# Objetivo: Resaltar agresivamente esta frecuencia para simular el síntoma.
# PRECAUCIÓN: Bajar el volumen antes de aplicar.

filters:
  tinnitus_sim:
    type: Biquad
    parameters:
      type: Peaking
      freq: {freq:.1f}
      q: 20.0    # Q muy estrecho, tono puro
      gain: 12.0 # +12dB de ganancia en esa frecuencia

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


# --- UI & UTILIDADES ---
def clear_screen():
    print("\033[H\033[J", end="")


def print_interface():
    clear_screen()
    print(Fore.CYAN + Style.BRIGHT + "========================================")
    print(Fore.CYAN + Style.BRIGHT + "       TINNITUS FREQUENCY MATCHER       ")
    print(Fore.CYAN + Style.BRIGHT + "========================================")
    print("")

    if state["mode"] == "MATCHING":
        print(f"Frecuencia: {Fore.YELLOW}{osc.frequency:.2f} Hz{Fore.RESET}")
        print(f"Volumen:    {Fore.GREEN}{int(osc.volume * 100)}%{Fore.RESET}")
        print(f"Paso:       {state['step']} Hz")
        print("")
        print(Fore.WHITE + Back.BLUE + " CONTROLES: ")
        print(" [⬆/⬇] Ajustar Frecuencia")
        print(" [⮕/⬅] Cambiar precisión (1, 10, 100... Hz)")
        print(" [ENTER] Confirmar y verificar Octava")
        print(" [ESC]   Salir")

    elif state["mode"] == "OCTAVE_CHECK":
        base = state["base_freq"]
        opts = [base, base / 2, base * 2]
        labels = ["Original", "-1 Octava", "+1 Octava"]

        print(Fore.MAGENTA + "VERIFICACIÓN DE OCTAVA")
        print("Selecciona cuál suena idéntico a tu tinnitus:")
        print("")

        for i in range(3):
            prefix = " > " if state["octave_option"] == i else "   "
            color = Fore.GREEN if state["octave_option"] == i else Fore.WHITE
            print(f"{color}{prefix}{labels[i]}: {opts[i]:.2f} Hz")

        print("")
        print(Fore.WHITE + Back.BLUE + " [ENTER] Generar Archivos de Configuración ")


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


def main():
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
        print(Fore.GREEN + Style.BRIGHT + "¡PROCESO FINALIZADO!")
        print(f"Frecuencia detectada: {final_f:.2f} Hz\n")

        # Generar Notch (Terapia)
        notch_file = "camilla_notch_therapy.yml"
        with open(notch_file, "w") as f:
            f.write(generate_notch_yaml(final_f))
        print(f"1. Filtro Terapéutico guardado en: {Fore.YELLOW}{notch_file}")

        # Generar Simulador (Empatía)
        sim_file = "camilla_simulator.yml"
        with open(sim_file, "w") as f:
            f.write(generate_simulator_yaml(final_f))
        print(f"2. Simulador de Tinnitus guardado en: {Fore.YELLOW}{sim_file}")

        print(
            f"\n{Fore.CYAN}Copia estos archivos a tu carpeta de configuración de CamillaDSP."
        )


if __name__ == "__main__":
    main()
