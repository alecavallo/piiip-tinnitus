# piiip-tinnitus

**Tinnitus Frequency Matcher & DSP Filter Generator**

A Python-based acoustic tool designed to help users identify their specific tinnitus frequency (pitch matching) and automatically generate configuration files for CamillaDSP. These configurations can be used to create a therapeutic "Notched Audio" environment or a Tinnitus Simulator.

---

## ⚠️ IMPORTANT MEDICAL & SAFETY DISCLAIMER

**PLEASE READ BEFORE USING:**

- **Not a Medical Device:** This software is a personal project created by a software developer, not by audiologists, otolaryngologists, or medical professionals. It is not a substitute for professional medical diagnosis, advice, or treatment.

- **Volume Safety:** This tool generates pure sinusoidal waves. High-frequency tones can be damaging to hearing if played at high volumes. **ALWAYS start with the volume at the lowest possible setting (1-5%) and increase slowly.**

- **Consult a Professional:** Before attempting any "Sound Therapy" or "Notch Therapy," consult with a hearing specialist. Improper use of sound therapy can potentially aggravate tinnitus (reactive tinnitus).

- **"AS IS" Warranty:** The software is provided "as is", without warranty of any kind, express or implied. The authors are not liable for any claim, damages, or other liability arising from the use of this software.

---

## 1. Project Overview

This tool solves two problems: **identification** and **processing**.

- **Pitch Matching:** It provides a CLI (Command Line Interface) to sweep through frequencies and identify the pitch of your phantom sound. It includes an "Octave Check" to ensure you haven't identified a harmonic frequency by mistake.

- **DSP Generation:** Once the frequency is found, it generates YAML configuration files for CamillaDSP, a powerful system-wide audio processor.
  - **Notch Filter:** Removes the specific frequency from system audio (Spotify, YouTube, etc.) for habituation therapy.
  - **Simulator:** Adds the specific frequency to system audio to help friends/family understand what the sufferer hears.

---

## 2. Installation

### Prerequisites

- Python 3.8+
- CamillaDSP (Required for the filtering stage, not for the frequency finder).

### Step 1: Install Python Dependencies

Open your terminal/command prompt and run:

```bash
pip install numpy sounddevice pynput colorama pyyaml
```

### Step 2: System-Specific Audio Libraries

- **Windows:** Usually works out of the box with the pip install.

- **macOS:** You may need PortAudio:
  ```bash
  brew install portaudio
  ```

- **Linux:** You need the development headers for PortAudio:
  ```bash
  sudo apt-get install libportaudio2
  ```

---

## 3. How to Use the Frequency Matcher

### The Setup

- **Environment:** Find a very quiet room. External noise makes matching difficult.
- **Hardware:** Use high-quality headphones (over-ear preferred) with a flat frequency response. Do not use speakers.
- **State:** Try to be relaxed. Stress can alter tinnitus perception.

### Running the Tool

Run the script from your terminal:

```bash
python src/main.py
```

### The Process

#### Matching Mode:

- Use **UP/DOWN** arrows to change frequency.
- Use **LEFT/RIGHT** to change the step size (Precision).
- Match the tone in the software to the tone in your head.

#### Octave Check (Crucial):

Once you press **ENTER**, the tool will play 3 tones:
- Your chosen frequency
- One octave below
- One octave above

**Why?** It is very common to mistake 8000Hz for 4000Hz. Select the one that truly blends with your tinnitus.

#### Generation:

Upon confirmation, the tool generates two `.yml` files in the current directory.

---

## 4. Understanding the Generated Files

The tool produces two YAML configuration fragments:

### A. `camilla_notch_therapy.yml`

- **Purpose:** Therapeutic / Habituation.
- **Mechanism:** Uses a high-Q Notch Filter (Band-stop).
- **Effect:** It "carves out" the tinnitus frequency from your music. By listening to music with this "hole," your brain may reduce the activity of the neurons corresponding to that frequency over time (Lateral Inhibition).

### B. `camilla_simulator.yml`

- **Purpose:** Empathy / Demonstration.
- **Mechanism:** Uses a high-gain Peaking Filter.
- **Effect:** It dramatically boosts the tinnitus frequency in any audio passing through. This allows non-sufferers to "hear" the constant ringing overlaid on music or voices.

---

## 5. Setting Up CamillaDSP

CamillaDSP is the engine that applies these filters to your computer's audio. The generated files are fragments containing the filter and pipeline logic. You must integrate them into a full CamillaDSP configuration file that defines your input/output devices.

### Basic Structure of a CamillaDSP Config

You will need a `config.yml` that looks like this (simplified):

```yaml
devices:
  samplerate: 44100
  chunksize: 1024
  capture:
    type: CoreAudio # or Wasapi, Alsa, Pulse
    channels: 2
    device: "Name of Input Device"
  playback:
    type: CoreAudio # or Wasapi, Alsa, Pulse
    channels: 2
    device: "Name of Output Device"

# --- PASTE THE CONTENT OF THE GENERATED FILE HERE ---
filters:
  my_notch:
    type: Biquad
    # ... (content from generated file)

pipeline:
  - type: Filter
    # ... (content from generated file)
```

---

## 6. System-Wide Audio Routing

To filter audio from Spotify/Browser, you need to route system audio into CamillaDSP, and then out to your headphones.

### 🍎 macOS

1. **Install BlackHole:** A virtual audio driver.
   ```bash
   brew install blackhole-2ch
   ```

2. **System Settings:** Set your Mac's Sound Output to BlackHole 2ch.

3. **CamillaDSP Config:**
   - Capture device: `"BlackHole 2ch"`
   - Playback device: Your Headphones / DAC.

4. **Run:**
   ```bash
   camilladsp -v config.yml
   ```

### 🪟 Windows

1. **Install VB-Cable:** A virtual audio cable driver.

2. **Sound Settings:** Set Windows Output to CABLE Input.

3. **CamillaDSP Config:**
   - Capture device: `"CABLE Output"` (Wasapi)
   - Playback device: Your Headphones (Wasapi).

4. **Run:**
   ```bash
   camilladsp.exe -v config.yml
   ```

### 🐧 Linux (PipeWire - Recommended)

PipeWire makes this easy using a filter chain. You don't necessarily need to run the standalone CamillaDSP binary if you use the PipeWire module, but running the binary is often simpler for testing.

#### Standard Method:

Use a loopback device or configure PipeWire to sink audio into CamillaDSP.

#### Easy Method (EasyEffects):

If CamillaDSP is too complex, you can install EasyEffects.

1. Go to "Plugins" -> "Crystalizer" or "Equalizer".
2. Manually enter the Frequency and Q factor obtained from this Python tool.

---

## 7. Troubleshooting

- **Audio Glitches/Clicks:** Increase the `chunksize` in your CamillaDSP config (e.g., from 1024 to 4096).

- **Latency:** Decrease the `chunksize`.

- **"Device not found":** Run `camilladsp -p` to list all available audio devices on your system and copy the exact name string.
