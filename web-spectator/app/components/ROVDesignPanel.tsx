"use client";

import { useRef, useEffect } from "react";

interface Props {
  pitch: number;
  roll: number;
  yaw: number;
}

const AXIS_CANVAS_W = 200;
const AXIS_CANVAS_H = 60;

/**
 * Displays the static ROV design image with a vector-drawn coordinate
 * axis indicator and live orientation readout.
 */
export default function ROVDesignPanel({ pitch, roll, yaw }: Props) {
  const axisCanvasRef = useRef<HTMLCanvasElement>(null);

  // Draw vector axis lines
  useEffect(() => {
    const canvas = axisCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = AXIS_CANVAS_W;
    const h = AXIS_CANVAS_H;
    ctx.clearRect(0, 0, w, h);

    // Origin near bottom-center
    const ox = w / 2;
    const oy = h - 10;
    const len = 28;

    // X — forward (upper-right at ~30°)
    drawAxis(ctx, ox, oy, len, -Math.PI / 6, "#e94560", "X");
    // Y — lateral (lower-right at ~30°)
    drawAxis(ctx, ox, oy, len, Math.PI / 6, "#4caf50", "Y");
    // Z — up (straight up)
    drawAxis(ctx, ox, oy, len, -Math.PI / 2, "#2196f3", "Z");
  }, []);

  return (
    <div className="bg-panel border border-border rounded-md flex flex-col h-full overflow-hidden">
      {/* Title bar */}
      <div className="bg-border text-text-title text-[11px] font-bold tracking-wider px-2 py-1 uppercase shrink-0">
        ROV DESIGN
      </div>

      {/* Content — image + axes */}
      <div className="flex-1 flex flex-col items-center justify-center min-h-0 bg-panel-dark px-2 py-1 gap-1 overflow-hidden">
        {/* ROV image — constrained to not overflow */}
        <img
          src="/rov_design.png"
          alt="ROV Design"
          className="w-auto h-auto max-h-[55%] max-w-[90%] object-contain shrink"
        />

        {/* Vector axis indicator */}
        <canvas
          ref={axisCanvasRef}
          width={AXIS_CANVAS_W}
          height={AXIS_CANVAS_H}
          className="shrink-0"
          style={{ maxWidth: "100%", maxHeight: `${AXIS_CANVAS_H}px` }}
        />
      </div>

      {/* State badge */}
      <div className="text-center text-text-dim text-[10px] py-1.5 border-t border-border shrink-0">
        STATE: P:{pitch.toFixed(0)}° R:{roll.toFixed(0)}° Y:{yaw.toFixed(0)}°
      </div>
    </div>
  );
}

/** Draw a single colored arrow from (ox, oy) in direction `angle` (radians). */
function drawAxis(
  ctx: CanvasRenderingContext2D,
  ox: number,
  oy: number,
  len: number,
  angle: number,
  color: string,
  label: string,
) {
  const dx = len * Math.cos(angle);
  const dy = len * Math.sin(angle);
  const tipX = ox + dx;
  const tipY = oy + dy;

  // Axis line
  ctx.beginPath();
  ctx.moveTo(ox, oy);
  ctx.lineTo(tipX, tipY);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.stroke();

  // Arrowhead
  const headLen = 5;
  const perp = angle - Math.PI / 2;
  ctx.beginPath();
  ctx.moveTo(tipX, tipY);
  ctx.lineTo(
    tipX - headLen * Math.cos(angle) + headLen * 0.4 * Math.cos(perp),
    tipY - headLen * Math.sin(angle) + headLen * 0.4 * Math.sin(perp),
  );
  ctx.lineTo(
    tipX - headLen * Math.cos(angle) - headLen * 0.4 * Math.cos(perp),
    tipY - headLen * Math.sin(angle) - headLen * 0.4 * Math.sin(perp),
  );
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();

  // Label
  ctx.fillStyle = color;
  ctx.font = "bold 9px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const labelOffX = 10 * Math.cos(angle);
  const labelOffY = 10 * Math.sin(angle);
  ctx.fillText(label, tipX + labelOffX, tipY + labelOffY);
}
