"use client";

import { useState, useCallback, useEffect } from "react";
import { useTelemetry } from "@/hooks/useTelemetry";
import TopBar from "@/app/components/TopBar";
import CameraFeed from "@/app/components/CameraFeed";
import DepthGauge from "@/app/components/DepthGauge";
import AttitudePanel from "@/app/components/AttitudePanel";
import QRPanel from "@/app/components/QRPanel";
import TrajectoryPanel from "@/app/components/TrajectoryPanel";
import ROVDesignPanel from "@/app/components/ROVDesignPanel";
import OfflineBanner from "@/app/components/OfflineBanner";
import Footer from "@/app/components/Footer";
import SettingsModal, { getStoredVideoUrl, storeVideoUrl } from "@/app/components/SettingsModal";

const ENV_VIDEO_BASE = process.env.NEXT_PUBLIC_VIDEO_BASE_URL;

export default function SpectatorPage() {
  const { online, status, metrics, qr } = useTelemetry();
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Dynamic video URL: stored → env → empty
  const [videoBaseUrl, setVideoBaseUrl] = useState(() => {
    const stored = getStoredVideoUrl();
    return stored || ENV_VIDEO_BASE || "";
  });

  const handleSaveVideoUrl = useCallback((url: string) => {
    setVideoBaseUrl(url);
    storeVideoUrl(url);
  }, []);

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
        <TopBar online={online} onOpenSettings={() => setSettingsOpen(true)} />

        {/* ── Settings modal ─────────────────────────────────────────── */}
        <SettingsModal
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          currentUrl={videoBaseUrl}
          onSave={handleSaveVideoUrl}
        />

        {/* ── Main grid — mirrors MainWindow._build_grid() ───────────── */}
        <main className="flex-1 grid grid-cols-[4fr_4fr_3fr] grid-rows-[6fr_4fr] gap-1 p-1.5 min-h-0">
          {/* Row 0, Col 0: Front Camera */}
          <CameraFeed label="FRONT CAM" endpoint="cam1" videoBaseUrl={videoBaseUrl} />

          {/* Row 0, Col 1: Bottom Camera */}
          <CameraFeed label="BOTTOM CAM" endpoint="cam2" videoBaseUrl={videoBaseUrl} />

          {/* Row 0, Col 2: QR Code & Status Panel */}
          <QRPanel
            armed={status.armed}
            mode={status.mode}
            voltage={metrics.voltage}
            qr={qr}
          />

          {/* Row 1, Col 0: Depth Gauge + Attitude */}
          <div className="grid grid-rows-2 gap-1 min-h-0">
            <DepthGauge depth={metrics.depth} />
            <AttitudePanel pitch={metrics.pitch} roll={metrics.roll} heading={metrics.heading} />
          </div>

          {/* Row 1, Col 1: Trajectory Map */}
          <TrajectoryPanel
            heading={metrics.heading}
            posX={metrics.pos_x}
            posY={metrics.pos_y}
            posDist={metrics.pos_dist}
          />

          {/* Row 1, Col 2: ROV Design Panel */}
          <ROVDesignPanel
            pitch={metrics.pitch}
            roll={metrics.roll}
            yaw={metrics.yaw}
          />
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
