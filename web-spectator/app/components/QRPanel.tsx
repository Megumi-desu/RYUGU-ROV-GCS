"use client";

import { Shield, ShieldOff } from "lucide-react";
import type { TelemetryQR } from "@/hooks/useTelemetry";

interface Props {
  armed: boolean;
  mode: string;
  voltage: number;
  qr: TelemetryQR;
}

const SIDES = ["A", "B", "C", "D"];

const MODE_COLORS: Record<string, string> = {
  MANUAL: "#4caf50",
  STABILIZE: "#2196f3",
  "DEPTH HOLD": "#00bcd4",
  AUTONOMOUS: "#ff9800",
  "E-STOP": "#f44336",
};

export default function QRPanel({ armed, mode, voltage, qr }: Props) {
  const modeColor = MODE_COLORS[mode] ?? "#607d8b";
  const activeSide = qr.side || "";
  const isValid = qr.valid;
  const rawText = qr.text || "—";
  const logs = qr.logs ?? [];

  return (
    <div className="bg-panel border border-border rounded-md flex flex-col h-full overflow-hidden">
      {/* Title bar */}
      <div className="bg-border text-text-title text-[11px] font-bold tracking-wider px-2 py-1 uppercase shrink-0">
        QR CODE & STATUS
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 gap-1.5 p-2.5 overflow-y-auto min-h-0">
        {/* QR Snapshot Image or Team Logo fallback */}
        <div className="flex items-center justify-center shrink-0">
          {qr.image ? (
            <img
              src={`data:image/jpeg;base64,${qr.image}`}
              alt="Scanned QR Snapshot"
              className="w-full h-32 object-contain rounded border border-border bg-panel-dark"
            />
          ) : (
            <img
              src="/logo_team.png"
              alt="RYUGU"
              className="h-24 object-contain opacity-80"
            />
          )}
        </div>

        {/* SIDE label */}
        <span className="text-text-dim text-[9px] uppercase tracking-wider text-center">
          SIDE
        </span>

        {/* Side value — large */}
        <span className="text-accent text-3xl font-bold text-center leading-none">
          {activeSide || "—"}
        </span>

        {/* Valid / Invalid badge */}
        {activeSide ? (
          <span
            className={`text-center text-xs font-bold px-3 py-0.5 rounded border self-center ${
              isValid
                ? "text-ok border-ok/30 bg-ok/10"
                : "text-error border-error/30 bg-error/10"
            }`}
          >
            {isValid ? "VALID" : "INVALID"}
          </span>
        ) : (
          <span className="text-text-dim text-xs font-bold text-center">
            AWAITING SCAN
          </span>
        )}

        {/* A/B/C/D side indicators */}
        <div className="flex justify-center gap-2">
          {SIDES.map((s) => (
            <div
              key={s}
              className="w-9 h-9 flex items-center justify-center text-xs font-bold rounded-md border transition-colors"
              style={{
                color: s === activeSide ? "#ffffff" : undefined,
                backgroundColor:
                  s === activeSide ? "#e94560" : "transparent",
                borderColor:
                  s === activeSide ? "#e94560" : undefined,
              }}
            >
              {s}
            </div>
          ))}
        </div>

        {/* Armed / Disarmed + Mode */}
        <div className="flex items-center justify-center gap-2">
          {armed ? (
            <Shield className="w-4 h-4 text-ok" />
          ) : (
            <ShieldOff className="w-4 h-4 text-text-dim" />
          )}
          <span
            className={`text-xs font-bold ${armed ? "text-ok" : "text-text-dim"}`}
          >
            {armed ? "ARMED" : "DISARMED"}
          </span>
        </div>

        <div
          className="text-center text-[10px] font-bold px-3 py-1 rounded border self-center"
          style={{ color: modeColor, borderColor: modeColor }}
        >
          {mode}
        </div>

        {/* Voltage */}
        <div className="text-center text-text text-xs tabular-nums">
          {voltage.toFixed(1)} V
        </div>

        {/* LAST RAW DATA */}
        <span className="text-text-dim text-[9px] uppercase tracking-wider">
          LAST RAW DATA
        </span>
        <div className="bg-panel-dark border border-border rounded p-1.5 min-h-[2rem]">
          <p className="text-text-dim font-mono text-[10px] break-all leading-tight">
            {rawText.length > 50 ? rawText.slice(0, 50) + "…" : rawText}
          </p>
        </div>

        {/* STATUS LOG */}
        <span className="text-text-dim text-[9px] uppercase tracking-wider">
          STATUS LOG
        </span>
        <div className="bg-panel-dark border border-border rounded p-1.5 flex-1 min-h-[60px] overflow-y-auto">
          {logs.length > 0 ? (
            logs.slice(0, 5).map((entry, i) => (
              <p
                key={i}
                className="font-mono text-[9px] leading-relaxed"
                style={{
                  color: entry.includes("OK") || entry.includes("ONLINE")
                    ? "#4caf50"
                    : entry.includes("NG") || entry.includes("OFFLINE") || entry.includes("LOST")
                      ? "#f44336"
                      : "#7a8a99",
                }}
              >
                {entry}
              </p>
            ))
          ) : (
            <p className="font-mono text-[9px] text-text-dim leading-relaxed">—</p>
          )}
        </div>

        {/* E-STOP button (visual only — no function on web) */}
        <div className="flex justify-center shrink-0">
          <div className="w-[90px] h-[90px] rounded-full bg-[#7f0000] border-[3px] border-[#c62828] flex items-center justify-center">
            <span className="text-white text-[10px] font-bold text-center leading-tight">
              EMERGENCY<br />STOP
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
