"use client";

import { Shield, ShieldOff, Battery, Gauge } from "lucide-react";

interface Props {
  armed: boolean;
  mode: string;
  voltage: number;
}

const MODE_COLORS: Record<string, string> = {
  MANUAL: "#4caf50",
  STABILIZE: "#2196f3",
  "DEPTH HOLD": "#00bcd4",
  AUTONOMOUS: "#ff9800",
  "E-STOP": "#f44336",
};

export default function StatusPanel({ armed, mode, voltage }: Props) {
  const modeColor = MODE_COLORS[mode] ?? "#607d8b";

  return (
    <div className="bg-panel border border-border rounded-md p-3 flex flex-col gap-3 h-full">
      <span className="text-text-dim text-[10px] uppercase tracking-wider text-center">
        System Status
      </span>

      {/* Armed badge */}
      <div className="flex items-center justify-center gap-2">
        {armed ? (
          <Shield className="w-5 h-5 text-ok" />
        ) : (
          <ShieldOff className="w-5 h-5 text-text-dim" />
        )}
        <span
          className={`text-sm font-bold ${armed ? "text-ok" : "text-text-dim"}`}
        >
          {armed ? "ARMED" : "DISARMED"}
        </span>
      </div>

      {/* Flight mode */}
      <div
        className="text-center text-xs font-bold px-3 py-1.5 rounded border self-center"
        style={{ color: modeColor, borderColor: modeColor }}
      >
        {mode}
      </div>

      {/* Voltage */}
      <div className="flex items-center justify-center gap-2">
        <Battery className="w-4 h-4 text-cyan" />
        <span className="text-text text-sm tabular-nums">
          {voltage.toFixed(1)} V
        </span>
      </div>

      {/* Yaw */}
      <div className="flex items-center justify-center gap-2">
        <Gauge className="w-4 h-4 text-text-dim" />
        <span className="text-text-dim text-xs">Sensors active</span>
      </div>
    </div>
  );
}
