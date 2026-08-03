"use client";

import { Compass } from "lucide-react";

interface Props {
  pitch: number;
  roll: number;
  heading: number;
}

function compassLabel(deg: number): string {
  const dirs: [number, string][] = [
    [0, "E"], [45, "NE"], [90, "N"], [135, "NW"],
    [180, "W"], [225, "SW"], [270, "S"], [315, "SE"],
  ];
  const d = ((deg % 360) + 360) % 360;
  let best = dirs[0];
  for (const dir of dirs) {
    const diff = Math.min(Math.abs(d - dir[0]), 360 - Math.abs(d - dir[0]));
    const bestDiff = Math.min(Math.abs(d - best[0]), 360 - Math.abs(d - best[0]));
    if (diff < bestDiff) best = dir;
  }
  return best[1];
}

export default function AttitudePanel({ pitch, roll, heading }: Props) {
  const label = compassLabel(heading);

  return (
    <div className="bg-panel border border-border rounded-md p-3 flex flex-col items-center justify-center gap-2 h-full">
      <span className="text-text-dim text-[10px] uppercase tracking-wider">
        Attitude &amp; Heading
      </span>

      {/* Artificial horizon placeholder + data */}
      <div className="flex items-center gap-4">
        {/* Pitch/Roll */}
        <div className="flex flex-col items-center gap-1">
          <div
            className="w-20 h-20 rounded-full border-2 border-border bg-panel-dark flex items-center justify-center relative overflow-hidden"
            style={{
              transform: `rotate(${roll}deg)`,
            }}
          >
            <div
              className="absolute left-0 right-0 h-0.5 bg-cyan transition-transform duration-150"
              style={{ transform: `translateY(${pitch * 1.5}px)` }}
            />
            <div className="w-2 h-2 bg-cyan rounded-full z-10" />
          </div>
          <div className="flex gap-3 text-[10px] text-text-dim">
            <span>P: {pitch.toFixed(1)}°</span>
            <span>R: {roll.toFixed(1)}°</span>
          </div>
        </div>

        {/* Compass heading */}
        <div className="flex flex-col items-center gap-1">
          <div className="relative w-20 h-20">
            <Compass className="w-20 h-20 text-cyan/30 absolute" />
            <div
              className="absolute inset-0 flex items-center justify-center"
              style={{ transform: `rotate(${-heading}deg)` }}
            >
              <div className="w-0.5 h-6 bg-cyan rounded-full origin-bottom translate-y-[-8px]" />
            </div>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-white text-sm font-bold tabular-nums">
                {heading.toFixed(0)}°
              </span>
            </div>
          </div>
          <span className="text-cyan text-xs font-semibold">{label}</span>
        </div>
      </div>
    </div>
  );
}
