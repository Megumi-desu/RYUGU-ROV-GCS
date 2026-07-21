# RYUGU ROV - Ground Control Station (GCS) 🎮🌊
### **RYUGU ROV Team | Universitas Brawijaya | KKI 2026**

A **PyQt5-based** Ground Control Station (GCS) designed to monitor, control, and navigate the **RYUGU Remotely Operated Vehicle (ROV)** for the Indonesian Ship Competition (Kontes Kapal Indonesia / KKI) 2026. This application communicates in real-time with the onboard **NVIDIA Jetson Orin Nano** computer via a custom Ethernet UDP protocol, displaying live telemetry, dual video streams, and an integrated real-time QR code detection module.

---

## 🚀 Key Features

- **Dual Live Camera Stream**: Displays real-time video feeds (Front and Bottom cameras) transmitted from the Jetson Orin Nano via HTTP/MJPEG streams.
- **Real-Time Ethernet UDP Protocol**: High-speed, low-latency communication with the Jetson Orin Nano:
  - **Uplink (Commands)**: Transmits movement commands (motion), gripper actions, flight mode switches, arm/disarm triggers, and emergency stop (E-STOP) signals.
  - **Downlink (Telemetry)**: Receives high-frequency IMU orientation data (Pitch, Roll, Yaw), depth/altitude, battery status, arm state, and real-time thruster outputs.
- **Gamepad Controller Integration**: Leverages the Pygame library for precise joystick and button mapping:
  - Manual navigation and flight mode changes (*Manual, Stabilize, Depth Hold, Autonomous*).
  - Dual speed profiles (*Fast* for normal transits, *Slow* for precision maneuvering).
  - Interactive gripper control.
- **Trajectory Mapping & Dead Reckoning**:
  - Live 2D plotting of the ROV's trajectory using `pyqtgraph`.
  - Supports two operational modes: **Gamepad Only** (dead reckoning simulation) and **Pixhawk Hybrid** (utilizing real IMU orientation combined with gamepad thrust).
- **QR Code Detection & Event Logger**:
  - Real-time QR Code scanning and decoding using OpenCV and `pyzbar`.
  - Chronological event logger to keep track of connection states, arm status, telemetry warnings, and scanned QR codes.
- **Depth & Altitude Gauges**: Visual vertical indicators with customizable safety zones (*safe, warning, critical*).
- **DPI-Aware & Modern Dark Theme**: A responsive, dark maritime-themed user interface powered by custom QSS, optimized for high-DPI displays.

---

## 📁 Repository Structure

```bash
ROV-GUI/
├── assets/                  # Logos (UB, KKI, RYUGU) and static image assets
├── core/                    # Core logic and background workers
│   ├── camera_stream_worker.py  # MJPEG camera stream receiver thread
│   ├── ethernet_worker.py       # UDP networking thread (Commands & Telemetry)
│   ├── gamepad_controller.py    # Gamepad input polling and parsing thread
│   ├── protocol.py              # Custom binary UDP packet definitions
│   └── state_machine.py         # Internal state machine for ROV status
├── gui/                     # Graphical User Interface (PyQt5)
│   ├── widgets/             # UI Panels (Depth, Camera, Trajectory, etc.)
│   │   ├── altitude_panel.py
│   │   ├── camera_panel.py
│   │   ├── qr_panel.py
│   │   ├── rov_design_panel.py
│   │   ├── status_bar.py
│   │   └── trajectory_panel.py
│   ├── styles/              # QSS stylesheet files (dark_theme.qss)
│   └── main_window.py       # Main layout construction and Qt signal wiring
├── utils/                   # Utilities and configuration settings
│   └── constants.py         # Theme colors, network parameters, tuning caps
├── tests/                   # Testing and simulation scripts
│   └── mock_jetson.py       # Jetson Orin Nano emulator (for offline testing)
├── verify_env.py            # Environment checklist and PyQt test tool
├── requirements.txt         # Python package dependencies
├── main.py                  # Main entry point of the GCS application
└── README.md                # Project documentation
```

---

## 🛠️ Installation & Environment Setup

### 1. Requirements
- **Python >= 3.10** is highly recommended.
- A **Gamepad / Joystick** (e.g., Xbox Controller) connected to the GCS PC.
- ZBar shared libraries (required for the QR code detector `pyzbar` on Windows).

### 2. Setup Guide
1. Clone this repository to your GCS computer.
2. Create and activate a new virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Verify Your Environment
Run the verification script to ensure all libraries are correctly installed and that your display/DPI configuration functions as expected:
```bash
python verify_env.py
```
*If successful, a small window titled "Environment OK" will appear.*

---

## 🌐 Network Configuration (Ethernet)

To establish communication between the GCS and the Jetson Orin Nano on the ROV, you must configure a static IP on your GCS PC/Laptop's ethernet adapter:

- **IP Address**: `192.168.1.100` (GCS IP)
- **Subnet Mask**: `255.255.255.0`
- **Gateway**: (Can be left blank or set to `192.168.1.1`)

By default, the network endpoints configured in `utils/constants.py` are:
- **Jetson IP**: `192.168.1.10`
- **Uplink Command Port (UDP)**: `5001`
- **Downlink Telemetry Port (UDP)**: `5002`

---

## 🎮 How to Run

### Offline Testing Mode (Without the ROV)
If you are developing or testing offline without connecting to the actual hardware:

1. Launch the **Mock Jetson Server** to simulate telemetric data flows (IMU oscillations, changing depth, mock QR codes):
   ```bash
   python tests/mock_jetson.py
   ```
2. In a separate terminal, launch the **GCS**:
   ```bash
   python main.py
   ```
3. You can now use your gamepad to navigate and observe real-time response graphs and changes in GCS indicators.

### Live Mode (Connected to the ROV)
1. Connect your GCS PC to the ROV tether (which bridges to the Jetson Orin Nano).
2. Verify that your static IP (`192.168.1.100`) is active.
3. Launch the GCS application:
   ```bash
   python main.py
   ```
4. The GCS status bar will automatically display `ONLINE` once it detects telemetry packets arriving from the ROS 2 node running on the Jetson Orin Nano.

---

## 📌 Troubleshooting

- **Gamepad Lost / Unresponsive**: Make sure the gamepad is connected to the PC *before* running `main.py`. Verify that the controller is registered by your operating system.
- **Jetson Connection Offline**: Run `ping 192.168.1.10`. If there is no response, check the physical ethernet connections, your static IP configuration on Windows, or verify that the ROS 2 startup service is running on the Jetson.
- **Camera Panel shows a black screen**: Double check the HTTP MJPEG streaming URLs in `utils/constants.py` and confirm that the camera stream server on the Jetson is actively broadcasting.
