"use client";

import { useState, useEffect, useCallback } from "react";
import { X, Info, Wifi, Globe } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  currentUrl: string;
  onSave: (url: string) => void;
}

const STORAGE_KEY = "rov_gcs_video_base_url";

export function getStoredVideoUrl(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(STORAGE_KEY) ?? "";
}

export function storeVideoUrl(url: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, url);
}

export default function SettingsModal({
  open,
  onClose,
  currentUrl,
  onSave,
}: Props) {
  const [url, setUrl] = useState(currentUrl);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setUrl(currentUrl);
    setSaved(false);
  }, [currentUrl, open]);

  const handleSave = useCallback(() => {
    const trimmed = url.trim().replace(/\/$/, "");
    onSave(trimmed);
    storeVideoUrl(trimmed);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [url, onSave]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleSave();
      if (e.key === "Escape") onClose();
    },
    [handleSave, onClose]
  );

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-[420px] max-w-[95vw]">
        <div className="bg-panel border border-border rounded-lg shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <h2 className="text-text text-sm font-bold flex items-center gap-2">
              <Wifi className="w-4 h-4 text-cyan" />
              Video Stream Settings
            </h2>
            <button
              onClick={onClose}
              className="text-text-dim hover:text-text transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Body */}
          <div className="px-4 py-3 flex flex-col gap-3">
            {/* URL Input */}
            <div>
              <label className="text-text-dim text-[10px] uppercase tracking-wider block mb-1">
                Video Base URL
              </label>
              <input
                type="text"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setSaved(false);
                }}
                onKeyDown={handleKeyDown}
                placeholder="http://192.168.1.100:8080"
                className="w-full bg-panel-dark border border-border rounded px-3 py-2 text-text text-xs font-mono
                           focus:outline-none focus:border-cyan placeholder:text-text-dim/40"
                autoFocus
              />
              <p className="text-text-dim/60 text-[9px] mt-1">
                Streams served at <code className="text-cyan/80">/cam1</code> and{" "}
                <code className="text-cyan/80">/cam2</code>
              </p>
            </div>

            {/* Connection info */}
            <div className="bg-panel-dark border border-border rounded p-3 flex flex-col gap-2">
              {/* LAN */}
              <div className="flex items-start gap-2">
                <Wifi className="w-3.5 h-3.5 text-ok mt-0.5 shrink-0" />
                <div>
                  <span className="text-ok text-[10px] font-bold">
                    Local Network (LAN)
                  </span>
                  <p className="text-text-dim text-[9px] leading-relaxed">
                    Use the GCS IP + port 8080 when on the same WiFi:
                    <br />
                    <code className="text-text/70">
                      http://192.168.1.100:8080
                    </code>
                  </p>
                </div>
              </div>

              {/* Cloudflare Tunnel */}
              <div className="flex items-start gap-2">
                <Globe className="w-3.5 h-3.5 text-cyan mt-0.5 shrink-0" />
                <div>
                  <span className="text-cyan text-[10px] font-bold">
                    Cloudflare Tunnel (HTTPS)
                  </span>
                  <p className="text-text-dim text-[9px] leading-relaxed">
                    For remote access, run{" "}
                    <code className="text-text/70">
                      cloudflared tunnel --url http://localhost:8080
                    </code>
                    {" "}on the GCS machine and paste the resulting HTTPS URL:
                    <br />
                    <code className="text-text/70">
                      https://xyz-trycloudflare.com
                    </code>
                  </p>
                </div>
              </div>

              {/* Mixed Content Warning */}
              <div className="flex items-start gap-2">
                <Info className="w-3.5 h-3.5 text-warn mt-0.5 shrink-0" />
                <p className="text-warn/80 text-[9px] leading-relaxed">
                  <strong>Mixed Content:</strong> Browsers block HTTP streams on
                  HTTPS pages. Use a Cloudflare Tunnel URL (HTTPS) when viewing
                  from Vercel, or open the app locally via{" "}
                  <code className="text-warn/70">http://localhost:3000</code>.
                </p>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span
              className={`text-[10px] transition-opacity ${
                saved ? "text-ok opacity-100" : "opacity-0"
              }`}
            >
              ✓ URL saved
            </span>
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="px-3 py-1.5 text-text-dim text-xs rounded border border-border hover:bg-panel-dark transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="px-4 py-1.5 text-white text-xs font-bold rounded bg-cyan hover:bg-cyan/80 transition-colors"
              >
                Save URL
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
