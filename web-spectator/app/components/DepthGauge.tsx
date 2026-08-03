"use client";

interface Props {
  depth: number;
  maxDepth?: number;
}

export default function DepthGauge({ depth, maxDepth = 1.5 }: Props) {
  const pct = Math.min(100, Math.max(0, (depth / maxDepth) * 100));

  const zoneColor =
    depth < 0.7 ? "#4caf50" : depth < 0.85 ? "#ff9800" : "#f44336";
  const zoneLabel =
    depth < 0.7 ? "SAFE" : depth < 0.85 ? "WARN" : "CRIT";

  return (
    <div className="bg-panel border border-border rounded-md flex items-center justify-center gap-3 p-3 h-full">
      {/* Vertical gauge */}
      <div className="relative w-14 h-full max-h-[200px] bg-panel-dark border border-border rounded overflow-hidden">
        <div
          className="absolute bottom-0 left-0 right-0 transition-all duration-200"
          style={{
            height: `${pct}%`,
            background: `linear-gradient(to top, #4caf50 0%, #ffc107 55%, #f44336 100%)`,
          }}
        />
      </div>

      {/* Readout */}
      <div className="flex flex-col items-start gap-1">
        <span className="text-white text-2xl font-bold tabular-nums">
          {depth.toFixed(2)} m
        </span>
        <span className="text-xs font-bold" style={{ color: zoneColor }}>
          ZONE: {zoneLabel}
        </span>
        <span className="text-[10px] text-warn">WARN: 0.70m</span>
        <span className="text-[10px] text-error">CRIT: 0.85m</span>
      </div>
    </div>
  );
}
