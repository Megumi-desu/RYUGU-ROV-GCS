# RYUGU ROV - Ground Control Station (GCS) & Web Spectator 🎮🌊
### **RYUGU ROV Team | Universitas Brawijaya | KKI 2026**

A hybrid **PyQt5 Desktop GCS** and **Next.js Real-time Web Spectator System** designed to monitor, control, and navigate the **RYUGU Remotely Operated Vehicle (ROV)** for the Indonesian Ship Competition (*Kontes Kapal Indonesia / KKI 2026*). 

The application communicates in real time with the onboard **NVIDIA Jetson Orin Nano** computer via a custom Ethernet UDP protocol, displaying low-latency telemetry, dual video streams, 2D trajectory tracking, and an integrated real-time QR code detection module. The accompanying Web Spectator allows competition judges and remote team members to observe live mission metrics from any web browser without interfering with pilot controls.

---

## 🚀 Key Features

### 🖥️ 1. PyQt5 Desktop GCS (Pilot Control Application)
- **Zero-Latency Control**: Optimized for pilot operations with Pygame-based Gamepad integration (Xbox / PlayStation controllers).
- **Dual Live Camera Stream**: Real-time video feeds (Front and Bottom cameras) transmitted from the Jetson Orin Nano via HTTP/MJPEG streams.
- **Ethernet UDP Telemetry Protocol**: High-speed, low-latency communication with the Jetson Orin Nano:
  - **Uplink (Commands)**: Motion vectors, flight modes (*Manual, Stabilize, Depth Hold, Autonomous*), dual speed profiles (*Fast/Slow*), gripper control, arm/disarm triggers, and E-STOP.
  - **Downlink (Telemetry)**: High-frequency IMU orientation (Pitch, Roll, Yaw), depth/altitude, battery status, arm state, and status log events.
- **Trajectory Mapping & Dead Reckoning**: Live 2D plotting of the ROV's movement path using `pyqtgraph` (Pixhawk Hybrid & Gamepad DR modes).
- **QR Code Detection & Event Logger**: OpenCV-based real-time QR code detection with snapshot frame captures and event logging.

### 🌐 2. Next.js Web Spectator (Remote Monitoring & Cloud Relay)
- **1:1 Mirror Layout**: Faithfully replicates the PyQt5 GCS desktop layout (Top Header Bar, Dual Video Viewports, QR & Status Panel, Altitude Gauge, 2D Trajectory Map, and ROV Design Panel).
- **Supabase Realtime Broadcast**: Non-blocking Python background thread (`telemetry_broadcaster.py`) streams live telemetry payloads to Supabase Realtime Channels (5–10 Hz) with zero persistent database overhead.
- **Heartbeat & Fail-Safe Indicator**: Automatically detects GCS connection state. Displays a prominent `🟢 LIVE / GCS CONNECTED` badge when active and transitions gracefully to `🔴 OFFLINE / GCS DISCONNECTED` when GCS is powered off.
- **Dynamic Stream Config & HTTPS Tunnel Support**: Includes a built-in settings modal ⚙️ to configure local WiFi streaming IPs or Cloudflare HTTPS Tunnels (`cloudflared`) for secure public streaming over Vercel.

---

## 📁 Monorepo Repository Structure

```bash
ROV-GUI/
├── assets/                      # Logos (UB, KKI, RYUGU) and static image assets
├── core/                        # Core Python logic and background workers
│   ├── camera_stream_worker.py  # MJPEG camera stream receiver thread
│   ├── ethernet_worker.py       # UDP networking thread (Commands & Telemetry)
│   ├── gamepad_controller.py    # Gamepad input polling thread
│   ├── mjpeg_server.py          # Local HTTP MJPEG streamer for web spectator
│   ├── protocol.py              # Custom binary UDP packet definitions
│   ├── state_machine.py         # Internal state machine for ROV status
│   └── telemetry_broadcaster.py # Supabase Realtime WebSocket broadcaster
├── gui/                         # PyQt5 Graphical User Interface
│   ├── widgets/                 # UI Panels (Depth, Camera, QR, Trajectory, ROV Design)
│   ├── styles/                  # QSS stylesheets (dark_theme.qss)
│   └── main_window.py           # Main window layout construction & signal wiring
├── web-spectator/               # 🌐 Next.js Web Spectator Frontend (Vercel App)
│   ├── app/                     # App Router pages and UI components
│   ├── hooks/                   # useTelemetry custom React hook (Supabase Realtime)
│   ├── lib/                     # Supabase JS client configuration
│   ├── public/                  # Public web assets (rov_design.png, icon.png)
│   └── package.json             # Node.js dependencies
├── utils/                       # Configuration settings and color constants
├── tests/                       # Testing and simulation scripts
│   └── mock_jetson.py           # Jetson Orin Nano emulator (for offline testing)
├── .env                         # Python environment variables (Supabase keys)
├── requirements.txt             # Python package dependencies
├── main.py                      # Entry point for the PyQt5 GCS application
└── README.md                    # Project documentation
```

---

## 🛠️ Installation & Setup

### 1. Prerequisites
- **Python >= 3.10**
- **Node.js >= 18** (for Web Spectator frontend)
- A **Gamepad / Joystick** (e.g. Xbox Controller) connected to the GCS PC.
- A **Supabase** account (Free tier) & **Vercel** account (Free tier).

### 2. Python Desktop GCS Setup
1. Clone this repository to your GCS computer:
   ```bash
   git clone https://github.com/Megumi-desu/RYUGU-ROV-GCS.git
   cd RYUGU-ROV-GCS
   ```
2. Create and activate a Python virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the root directory:
   ```env
   SUPABASE_URL=https://<your-project-ref>.supabase.co
   SUPABASE_ANON_KEY=<your-supabase-anon-key>
   TELEMETRY_BROADCAST_HZ=5
   MJPEG_PORT=8080
   ```

### 3. Web Spectator Frontend Setup (Local Development)
1. Navigate to the `web-spectator` folder:
   ```bash
   cd web-spectator
   ```
2. Install Node.js dependencies:
   ```bash
   npm install
   ```
3. Create a `.env.local` file inside `web-spectator/`:
   ```env
   NEXT_PUBLIC_SUPABASE_URL=https://<your-project-ref>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
   NEXT_PUBLIC_VIDEO_BASE_URL=http://localhost:8080
   ```
4. Run the Next.js local development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in your browser.

---

## 🌐 Deploying Web Spectator to Vercel

1. Push your repository to GitHub.
2. Log in to [Vercel](https://vercel.com) and click **Add New Project** -> **Import Repository**.
3. Configure the Project Settings:
   - **Root Directory**: Set to `web-spectator` *(Crucial: Ensures Vercel builds only the Next.js subfolder)*.
   - **Framework Preset**: `Next.js` (auto-detected).
4. Add Environment Variables in Vercel Dashboard:
   - `NEXT_PUBLIC_SUPABASE_URL` = `https://<your-project-ref>.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = `<your-supabase-anon-key>`
   - `NEXT_PUBLIC_VIDEO_BASE_URL` = `http://<laptop-wifi-ip>:8080` (or Cloudflare Tunnel URL)
5. Click **Deploy**. Your Web Spectator will be live at `https://ryugu-rov-gcs.vercel.app`.

---

## 🕹️ How to Run & Test

### Offline Simulation Mode (Without Physical ROV/Jetson)
You can test the complete end-to-end telemetry streaming (Python GCS ➔ Supabase ➔ Web Spectator Vercel) without connecting to the actual ROV:

1. **Terminal 1 — Launch Mock Jetson Emulator**:
   ```bash
   .venv\Scripts\activate
   python tests/mock_jetson.py --gcs-ip 127.0.0.1
   ```
2. **Terminal 2 — Launch Desktop GCS Application**:
   ```bash
   .venv\Scripts\activate
   python main.py
   ```
3. **Browser — View Live Web Spectator**:
   Open **`https://ryugu-rov-gcs.vercel.app`** on your browser/phone. The status will immediately switch from `🔴 OFFLINE` to `🟢 LIVE`, and all gauges, compass, and trajectory path lines will update in real time!

### Live Operation Mode (Connected to ROV Tether)
1. Configure a static IP of `192.168.1.100` on your GCS Laptop Ethernet Adapter.
2. Connect the tether cable to the GCS Laptop.
3. Launch the GCS:
   ```bash
   python main.py
   ```
4. Option for Public Internet Video Stream: Run a Cloudflare Tunnel on the GCS laptop:
   ```bash
   cloudflared tunnel --url http://localhost:8080
   ```
   Enter the generated `https://...trycloudflare.com` URL into the Web Spectator Settings Modal ⚙️.

---

## 📌 Troubleshooting

- **Web Spectator Shows Offline**: Ensure `python-dotenv` and `supabase` are installed in Python (`pip install supabase python-dotenv`), and verify that `.env` contains valid Supabase URL & Anon Keys.
- **Video Feed Blocked on Web**: Web browsers block `http://` streams inside `https://` pages (Mixed Content). Use the Settings Modal ⚙️ in the Web Spectator header to set your local WiFi IP or Cloudflare HTTPS Tunnel URL.
- **Gamepad Disconnected**: Ensure the gamepad is connected to your PC prior to launching `main.py`.

---

### 🏆 Credits & Team
- **Team**: RYUGU ROV Team
- **Institution**: Universitas Brawijaya
- **Event**: Kontes Kapal Indonesia (KKI) 2026
