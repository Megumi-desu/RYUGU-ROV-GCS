"use client";

import { useState } from "react";
import { Camera, WifiOff } from "lucide-react";

interface Props {
  label: string;
  endpoint: string; // "cam1" or "cam2"
  videoBaseUrl?: string;
}

export default function CameraFeed({ label, endpoint, videoBaseUrl }: Props) {
  const [error, setError] = useState(false);
  const src = videoBaseUrl ? `${videoBaseUrl.replace(/\/$/, "")}/${endpoint}` : "";

  return (
    <div className="bg-panel border border-border rounded-md flex flex-col overflow-hidden">
      {/* Title */}
      <div className="bg-border text-text-title text-[11px] font-bold tracking-wider px-2 py-1 uppercase">
        {label}
      </div>

      {/* Feed area */}
      <div className="flex-1 bg-panel-dark flex items-center justify-center relative min-h-0">
        {src && !error ? (
          <img
            src={src}
            alt={label}
            className="w-full h-full object-contain"
            onError={() => setError(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-text-dim">
            {error ? (
              <>
                <WifiOff className="w-8 h-8 text-warn" />
                <span className="text-xs">NO VIDEO — LAN only</span>
              </>
            ) : (
              <>
                <Camera className="w-8 h-8" />
                <span className="text-xs">Waiting for stream…</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
