"use client";

import { Map } from "lucide-react";

interface Props {
  heading: number;
  poolSize?: number;
}

export default function TrajectoryPanel({ heading, poolSize = 5 }: Props) {
  return (
    <div className="bg-panel border border-border rounded-md p-3 flex flex-col items-center justify-center gap-2 h-full">
      <span className="text-text-dim text-[10px] uppercase tracking-wider">
        Trajectory Map
      </span>

      {/* Placeholder pool map */}
      <div className="relative w-full max-w-[200px] aspect-square border border-dashed border-border rounded flex items-center justify-center">
        <Map className="w-10 h-10 text-text-dim/40" />
        {/* Heading arrow */}
        <div
          className="absolute w-0.5 h-8 bg-cyan origin-bottom"
          style={{
            left: "50%",
            bottom: "50%",
            transform: `translateX(-50%) rotate(${-heading}deg)`,
          }}
        />
        <div className="absolute bottom-1 right-1 text-[9px] text-text-dim/60">
          {poolSize.toFixed(0)}×{poolSize.toFixed(0)}m
        </div>
      </div>

      <span className="text-text-dim text-[10px] tabular-nums">
        HDG: {heading.toFixed(1)}°
      </span>
    </div>
  );
}
