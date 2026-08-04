"use client";

import { useState, useEffect } from "react";
import { Camera, WifiOff, Wifi, Globe } from "lucide-react";

interface Props {
  label: string;
  endpoint: string; // "cam1" or "cam2"
  videoBaseUrl?: string;
}

export default function CameraFeed({ label, endpoint, videoBaseUrl }: Props) {
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  // Reset error state when URL changes
  useEffect(() => {
    setError(false);
  }, [videoBaseUrl]);

  const src = videoBaseUrl
    ? `${videoBaseUrl.replace(/\/$/, "")}/${endpoint}`
    : "";

  const isHttps =
    typeof window !== "undefined" && window.location.protocol === "https:";
  const isHttpUrl = src.startsWith("http://");
  const mixedContent = isHttps && isHttpUrl;

  return (
    <div className="bg-panel border border-border rounded-md flex flex-col overflow-hidden">
      {/* Title */}
      <div className="bg-border text-text-title text-[11px] font-bold tracking-wider px-2 py-1 uppercase flex items-center gap-2">
        {label}
        {src && !error && (
          <span className="w-1.5 h-1.5 rounded-full bg-ok" />
        )}
      </div>

      {/* Feed area */}
      <div className="flex-1 bg-panel-dark flex items-center justify-center relative min-h-0">
        {src && !error ? (
          <img
            key={retryKey}
            src={src}
            alt={label}
            className="w-full h-full object-contain"
            onError={() => setError(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-text-dim px-3 text-center">
            {error ? (
              <>
                <WifiOff className="w-8 h-8 text-error" />
                <span className="text-xs font-semibold text-error">
                  Connection Failed
                </span>
                {mixedContent ? (
                  <p className="text-[10px] text-warn/80 leading-relaxed max-w-[240px]">
                    <strong>Mixed Content blocked.</strong> Browsers block HTTP
                    streams on HTTPS pages. Use a Cloudflare Tunnel URL or open
                    locally.
                  </p>
                ) : (
                  <p className="text-[10px] text-text-dim/70 leading-relaxed max-w-[240px]">
                    Check that the GCS is running and the MJPEG server is
                    reachable at{" "}
                    <code className="text-cyan/70 text-[9px] break-all">
                      {videoBaseUrl || "http://192.168.1.100:8080"}
                    </code>
                  </p>
                )}
                <button
                  onClick={() => {
                    setError(false);
                    setRetryKey((k) => k + 1);
                  }}
                  className="text-[10px] text-cyan hover:underline mt-1"
                >
                  ↻ Retry
                </button>
              </>
            ) : src ? (
              <>
                <Camera className="w-8 h-8" />
                <span className="text-xs">Connecting…</span>
              </>
            ) : (
              <>
                <Wifi className="w-8 h-8 text-text-dim/60" />
                <span className="text-xs text-text-dim/70">
                  No video source configured
                </span>
                <p className="text-[10px] text-text-dim/50 leading-relaxed max-w-[240px]">
                  Click{" "}
                  <Globe className="w-3 h-3 inline text-cyan" />{" "}
                  <span className="text-cyan/70">Settings</span> in the top bar
                  to configure the GCS stream URL.
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
