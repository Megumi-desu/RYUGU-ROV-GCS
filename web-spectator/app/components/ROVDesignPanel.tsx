"use client";

interface Props {
  pitch: number;
  roll: number;
  yaw: number;
}

/**
 * Displays the static ROV design image with coordinate axis labels
 * and live orientation readout.
 */
export default function ROVDesignPanel({ pitch, roll, yaw }: Props) {
  return (
    <div className="bg-panel border border-border rounded-md flex flex-col h-full overflow-hidden">
      {/* Title bar */}
      <div className="bg-border text-text-title text-[11px] font-bold tracking-wider px-2 py-1 uppercase shrink-0">
        ROV DESIGN
      </div>

      {/* ROV image */}
      <div className="flex-1 flex flex-col items-center justify-center min-h-0 bg-panel-dark px-3 py-2 gap-2">
        <img
          src="/rov_design.png"
          alt="ROV Design"
          className="max-h-48 w-full object-contain"
        />

        {/* Coordinate axes legend */}
        <div className="flex items-center gap-4 text-[10px] font-mono">
          <span style={{ color: "#e94560" }}>X — Forward</span>
          <span style={{ color: "#4caf50" }}>Y — Lateral</span>
          <span style={{ color: "#2196f3" }}>Z — Up</span>
        </div>
      </div>

      {/* State badge */}
      <div className="text-center text-text-dim text-[10px] py-1.5 border-t border-border shrink-0">
        STATE: P:{pitch.toFixed(0)}° R:{roll.toFixed(0)}° Y:{yaw.toFixed(0)}°
      </div>
    </div>
  );
}
