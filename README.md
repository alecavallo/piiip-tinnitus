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

## 6. Installing CamillaDSP

[CamillaDSP](https://github.com/HEnquist/camilladsp) is a flexible cross-platform IIR and FIR engine for crossovers, room correction, and audio filtering. It's the engine that applies the generated filters to your system audio.

### Download

1. Go to the [CamillaDSP Releases page](https://github.com/HEnquist/camilladsp/releases)
2. Download the appropriate binary for your platform:
   - **macOS (Apple Silicon):** `camilladsp-macos-aarch64.tar.gz`
   - **macOS (Intel):** `camilladsp-macos-x86_64.tar.gz`
   - **Windows:** `camilladsp-windows-amd64.zip`
   - **Linux:** `camilladsp-linux-amd64.tar.gz` (or ARM variants for Raspberry Pi)

3. Extract and place the binary somewhere in your PATH:
   ```bash
   # macOS/Linux example
   tar -xzf camilladsp-*.tar.gz
   sudo mv camilladsp /usr/local/bin/

   # Verify installation
   camilladsp --version
   ```

4. **macOS only – Fix Gatekeeper security warning:**

   Since CamillaDSP is an unsigned binary, macOS will block it with a message like *"camilladsp cannot be opened because Apple cannot check it for malicious software."*

   **Solution:** Remove the quarantine attribute:
   ```bash
   xattr -d com.apple.quarantine /usr/local/bin/camilladsp
   ```

   Alternatively, you can go to **System Settings → Privacy & Security** and click **"Open Anyway"** after the first blocked attempt.

### Create a Complete Configuration

The files generated by this tool are **filter fragments**. You need to combine them with a device configuration. Create a file called `config.yml`:

```yaml
devices:
  samplerate: 44100
  chunksize: 1024
  capture:
    type: CoreAudio  # Use: Wasapi (Windows), Alsa/Pulse (Linux)
    channels: 2
    device: "BlackHole 2ch"  # Your virtual audio device
  playback:
    type: CoreAudio  # Use: Wasapi (Windows), Alsa/Pulse (Linux)
    channels: 2
    device: "Your Headphones"  # Your actual output device

# --- PASTE THE CONTENT OF camilla_notch_therapy.yml BELOW ---
filters:
  my_notch:
    type: Biquad
    parameters:
      type: Notch
      freq: 4590.0  # Your detected frequency
      q: 10.0
      gain: 0

pipeline:
  - type: Filter
    channels: [0, 1]
    names:
      - my_notch
```

### List Available Audio Devices

CamillaDSP doesn't have a built-in flag to list devices. Use your OS tools:

**macOS:**
```bash
# List all audio devices
system_profiler SPAudioDataType
```

**Linux (ALSA):**
```bash
# Playback devices
aplay -l
# Capture devices
arecord -l
```

**Linux (PulseAudio/PipeWire):**
```bash
# List sinks (playback)
pactl list sinks short
# List sources (capture)
pactl list sources short
```

**Windows (PowerShell):**
```powershell
Get-AudioDevice -List
```

**Tip:** If you use an invalid device name in your config, CamillaDSP will show an error with hints about available devices.

---

## 7. System-Wide Audio Routing

To filter audio from Spotify/Browser, you need to route system audio into CamillaDSP, and then out to your headphones.

### 🍎 macOS

1. **Install BlackHole:** A virtual audio driver.
   ```bash
   brew install blackhole-2ch
   ```

2. **System Settings:** Set your Mac's Sound Output to BlackHole 2ch.

3. **Update your CamillaDSP config:**
   - Capture device: `"BlackHole 2ch"`
   - Playback device: Your Headphones / DAC name (use `system_profiler SPAudioDataType` on macOS).

4. **Run CamillaDSP:**
   ```bash
   # First, check the config for errors
   camilladsp -c config.yml

   # If no errors, run it with verbose output
   camilladsp -v config.yml
   ```

   > ⚠️ **Common mistake:** Don't use `-s` (statefile) to pass the config. Use `-c` to check or just pass the file directly.

### 🪟 Windows

1. **Install VB-Cable:** Download from [vb-audio.com/Cable](https://vb-audio.com/Cable/).

2. **Sound Settings:** Set Windows Output to "CABLE Input".

3. **Update your CamillaDSP config:**
   - Capture device: `"CABLE Output"` (type: Wasapi)
   - Playback device: Your Headphones name (type: Wasapi).

4. **Run CamillaDSP:**
   ```bash
   camilladsp.exe -v config.yml
   ```

### 🐧 Linux (PipeWire/PulseAudio)

#### Option A: Direct with ALSA/Pulse

1. Create a loopback device or use PulseAudio's module-loopback.
2. Configure CamillaDSP with `type: Pulse` or `type: Alsa`.

#### Option B: EasyEffects (Simpler Alternative)

If CamillaDSP setup is too complex, [EasyEffects](https://github.com/wwmm/easyeffects) provides a GUI for audio filtering:

1. Install EasyEffects (available in most package managers).
2. Go to "Effects" → "Equalizer" → "Parametric".
3. Add a Notch filter at your detected frequency with the Q factor from this tool.

---

## 8. Installing CamillaGUI (Optional)

[CamillaGUI](https://github.com/HEnquist/camillagui-backend) is an optional web-based interface for controlling and monitoring CamillaDSP in real-time. It provides volume meters, filter visualization, and the ability to adjust settings without editing YAML files.

### Prerequisites

CamillaGUI requires:
1. **CamillaDSP** running with websocket enabled (see below)
2. **A specific directory structure** for configs and coefficients

### Step 1: Create the Required Directory Structure

CamillaGUI expects config files in a specific location:

```bash
# Create the directories
mkdir -p ~/camilladsp/configs ~/camilladsp/coeffs

# Copy your config file
cp config.yml ~/camilladsp/configs/
```

### Step 2: Install CamillaGUI Backend

There are two installation methods:

#### Option A: Pre-built Bundle (Easiest)

1. Go to [CamillaGUI Backend Releases](https://github.com/HEnquist/camillagui-backend/releases)
2. Download the appropriate bundle:
   - **macOS (Apple Silicon):** `camillagui_macos_aarch64.zip`
   - **macOS (Intel):** `camillagui_macos_x86_64.zip`
   - **Windows:** `camillagui_windows.zip`
   - **Linux:** `camillagui_linux_amd64.zip`

3. Extract the bundle:
   ```bash
   unzip camillagui_*.zip -d camillagui_backend
   ```

4. **macOS only – Fix Gatekeeper security warning:**

   The bundle contains embedded Python libraries that macOS will block. You must remove the quarantine attribute from the **entire folder** recursively:

   ```bash
   # Remove quarantine from ALL files in the bundle
   xattr -rd com.apple.quarantine camillagui_backend/
   ```

   > ⚠️ **Important:** Use `-rd` (recursive + delete) not just `-d`. The bundled Python framework inside has multiple files that need clearing.

5. Run the backend:
   ```bash
   cd camillagui_backend
   ./camillagui_backend   # macOS/Linux
   camillagui_backend.exe  # Windows
   ```

#### Option B: Run from Source (More Reliable)

If the pre-built bundle doesn't work, running from source is straightforward:

```bash
# Clone the repository
git clone https://github.com/HEnquist/camillagui-backend.git
cd camillagui-backend

# Install dependencies
pip install aiohttp

# Run
python main.py
```

### Step 3: Run CamillaDSP with Websocket Enabled

CamillaGUI communicates with CamillaDSP via websocket. You must start CamillaDSP with the `-p` flag:

```bash
# Run CamillaDSP with websocket on port 1234
camilladsp -p 1234 -v ~/camilladsp/configs/config.yml
```

| Flag | Meaning |
|------|---------|
| `-p 1234` | Enable websocket server on port 1234 |
| `-v` | Verbose output (optional but helpful) |

> 💡 **Tip:** Keep CamillaDSP running in one terminal, and CamillaGUI backend in another.

### Step 4: Access the Web Interface

Open your browser and navigate to:

```
http://localhost:5005/gui/index.html
```

### Verifying CamillaGUI is Working

When everything is connected correctly, you should see:

| Indicator | Expected Value | Meaning |
|-----------|----------------|---------|
| **State** | `RUNNING` | CamillaDSP is processing audio |
| **OUT meters** | Green bars moving | Audio is passing through |
| **Capt. samplerate** | `44100` (or your config value) | Correct sample rate |
| **Clipped samples** | `0` | No audio distortion |
| **DSP load** | Low percentage | Filter is running efficiently |

### Platform-Specific Notes

#### 🍎 macOS

- **Gatekeeper issues:** If you see "cannot be opened" or "Python shared library" errors, ensure you ran `xattr -rd com.apple.quarantine` on the entire folder.
- **Microphone permissions:** CamillaDSP needs access to audio input. Go to **System Settings → Privacy & Security → Microphone** and allow Terminal (or your terminal app).

#### 🪟 Windows

- **Firewall:** Windows may prompt to allow network access for `camillagui_backend.exe`. Click "Allow" for private networks.
- **Antivirus:** Some antivirus software may flag the bundled executable. Add an exception if needed.

#### 🐧 Linux

- Usually works without issues. Ensure port 5005 is not blocked by your firewall:
  ```bash
  sudo ufw allow 5005/tcp
  ```

### CamillaGUI Troubleshooting

- **"Connection refused" in browser:** CamillaGUI backend is not running. Start it first.
- **"Websocket connection failed" in GUI:** CamillaDSP is not running with `-p` flag, or wrong port.
- **Meters not moving:** Check that your system audio output is set to the virtual device (BlackHole/VB-Cable).
- **"All applied: ⚠"** warning: This is normal on startup. Click "Fetch from DSP" to sync.

---

## 9. Troubleshooting

- **Audio Glitches/Clicks:** Increase the `chunksize` in your CamillaDSP config (e.g., from 1024 to 4096).

- **Latency:** Decrease the `chunksize`.

- **"Device not found":** Use your OS tools to list audio devices (see "List Available Audio Devices" section above) and copy the exact name string.

- **CamillaDSP won't start:** Ensure the YAML syntax is correct. Run `camilladsp -c config.yml` to check the configuration.

- **"Invalid statefile" error:** You used `-s` instead of `-c` or no flag. The flags mean:
  - `camilladsp config.yml` — Run with config file
  - `camilladsp -c config.yml` — Check config syntax and exit
  - `camilladsp -v config.yml` — Run with verbose output
  - `camilladsp -s state.yml config.yml` — Run with a statefile (for persisting mute/volume)

- **BlackHole not detected (macOS):** Restart CoreAudio:
  ```bash
  sudo launchctl kickstart -k system/com.apple.audio.coreaudiod
  ```
  If that doesn't work, try a full system reboot.

- **No audio change when filtering:** The notch filter is subtle. To verify:
  1. Ensure macOS Sound Output is set to "BlackHole 2ch" (not directly to headphones)
  2. Generate a test sweep: `play -n synth 10 sine 20:20000` (requires `sox`)
  3. You should hear a brief "dip" at your notch frequency

---

## 10. Resources

- **CamillaDSP:** [GitHub Repository](https://github.com/HEnquist/camilladsp) - The DSP engine used for filtering.
- **CamillaGUI Frontend:** [GitHub Repository](https://github.com/HEnquist/camillagui) - The web UI components.
- **CamillaGUI Backend:** [GitHub Repository](https://github.com/HEnquist/camillagui-backend) - The Python server that connects the GUI to CamillaDSP.
- **BlackHole:** [GitHub Repository](https://github.com/ExistentialAudio/BlackHole) - Virtual audio driver for macOS.
- **VB-Cable:** [vb-audio.com](https://vb-audio.com/Cable/) - Virtual audio driver for Windows.
- **REW (Room EQ Wizard):** [roomeqwizard.com](https://www.roomeqwizard.com/) - Professional measurement software that can export CamillaDSP filters.
