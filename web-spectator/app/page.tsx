"use client";

import { useTelemetry } from "@/hooks/useTelemetry";
import TopBar from "@/app/components/TopBar";
import CameraFeed from "@/app/components/CameraFeed";
import DepthGauge from "@/app/components/DepthGauge";
import AttitudePanel from "@/app/components/AttitudePanel";
import StatusPanel from "@/app/components/StatusPanel";
import TrajectoryPanel from "@/app/components/TrajectoryPanel";
import OfflineBanner from "@/app/components/OfflineBanner";
import Footer from "@/app/components/Footer";

const VIDEO_BASE = process.env.NEXT_PUBLIC_VIDEO_BASE_URL;

export default function SpectatorPage() {
  const { online, status, metrics } = useTelemetry();

  return (
    <>
      <OfflineBanner online={online} />

      {/* Wrap everything so offline dims telemetry panels */}
      <div
        className={`flex flex-col h-screen transition-opacity duration-300 ${
          online ? "opacity-100" : "opacity-60"
        }`}
      >
        {/* ── Top bar (52px) ─────────────────────────────────────────── */}
        <TopBar online={online} />

        {/* ── Main grid — mirrors MainWindow._build_grid() ───────────── */}
        <main className="flex-1 grid grid-cols-[4fr_4fr_3fr] grid-rows-[6fr_4fr] gap-1 p-1.5 min-h-0">
          {/* Row 0, Col 0: Front Camera */}
          <CameraFeed label="FRONT CAM" endpoint="cam1" videoBaseUrl={VIDEO_BASE} />

          {/* Row 0, Col 1: Bottom Camera */}
          <CameraFeed label="BOTTOM CAM" endpoint="cam2" videoBaseUrl={VIDEO_BASE} />

          {/* Row 0, Col 2: Status Panel (QR + E-STOP equivalent) */}
          <StatusPanel armed={status.armed} mode={status.mode} voltage={metrics.voltage} />

          {/* Row 1, Col 0: Depth Gauge + Attitude */}
          <div className="grid grid-rows-2 gap-1 min-h-0">
            <DepthGauge depth={metrics.depth} />
            <AttitudePanel pitch={metrics.pitch} roll={metrics.roll} heading={metrics.heading} />
          </div>

          {/* Row 1, Col 1: Trajectory Map */}
          <TrajectoryPanel heading={metrics.heading} />

          {/* Row 1, Col 2: Additional info / Logo */}
          <div className="bg-panel border border-border rounded-md p-3 flex flex-col items-center justify-center gap-2">
            <img src="/logo_team.png" alt="RYUGU" className="h-24 object-contain opacity-80" />
            <span className="text-text-dim text-[10px]">RYUGU ROV — KKI 2026</span>
            {!online && (
              <span className="text-error text-xs font-semibold mt-1">
                Waiting for GCS connection…
              </span>
            )}
          </div>
        </main>

        {/* ── Footer status bar ──────────────────────────────────────── */}
        <Footer
          online={online}
          mode={status.mode}
          armed={status.armed}
          voltage={metrics.voltage}
        />
      </div>
    </>
  );
}
