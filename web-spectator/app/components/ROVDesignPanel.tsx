"use client";

import { useRef, useEffect } from "react";

interface Props {
  pitch: number;
  roll: number;
  yaw: number;
}

const CANVAS_W = 320;
const CANVAS_H = 280;

/**
 * Draws an isometric ROV frame with orientation readout.
 * Uses Canvas 2D for the visualization.
 */
export default function ROVDesignPanel({ pitch, roll, yaw }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = CANVAS_W;
    const h = CANVAS_H;
    ctx.clearRect(0, 0, w, h);

    // ── Colors ────────────────────────────────────────────────────
    const bgColor = "#0d1b2a";
    const frameColor = "#1e3a5f";
    const frameStroke = "#0f3460";
    const accentColor = "#e94560";

    // Background
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, w, h);

    // ── Isometric projection ──────────────────────────────────────
    // Isometric angles: 30° from horizontal
    const cx = w / 2;
    const cy = h / 2 + 10;
    const isoAngle = Math.PI / 6; // 30°

    // ROV frame dimensions in "world" units
    const frameW = 140;
    const frameH = 80;
    const frameD = 30; // depth for 3D effect

    // Apply rotation from pitch/roll/yaw (simplified: tilt based on roll)
    const rollRad = (roll * Math.PI) / 180;
    const pitchRad = (pitch * Math.PI) / 180;

    // Simplified isometric transform: (x, y, z) → screen (sx, sy)
    // sx = cx + (x - y) * cos(30°)
    // sy = cy + (x + y) * sin(30°) - z
    const cos30 = Math.cos(isoAngle);
    const sin30 = Math.sin(isoAngle);

    function project(
      x: number,
      y: number,
      z: number
    ): [number, number] {
      // Apply roll rotation around X axis
      const ry = y * Math.cos(rollRad) - z * Math.sin(rollRad);
      const rz = y * Math.sin(rollRad) + z * Math.cos(rollRad);
      // Apply pitch rotation around Y axis
      const rx = x * Math.cos(pitchRad) + rz * Math.sin(pitchRad);
      const rz2 = -x * Math.sin(pitchRad) + rz * Math.cos(pitchRad);

      const sx = cx + (rx - ry) * cos30;
      const sy = cy + (rx + ry) * sin30 - rz2;
      return [sx, sy];
    }

    // ── Draw ROV frame (top face) ────────────────────────────────
    const hw = frameW / 2;
    const hh = frameH / 2;

    // Top face corners
    const topCorners = [
      project(-hw, -hh, frameD),
      project(hw, -hh, frameD),
      project(hw, hh, frameD),
      project(-hw, hh, frameD),
    ];

    // Bottom face corners
    const botCorners = [
      project(-hw, -hh, 0),
      project(hw, -hh, 0),
      project(hw, hh, 0),
      project(-hw, hh, 0),
    ];

    // Draw bottom face
    ctx.beginPath();
    ctx.moveTo(botCorners[0][0], botCorners[0][1]);
    for (let i = 1; i < 4; i++) {
      ctx.lineTo(botCorners[i][0], botCorners[i][1]);
    }
    ctx.closePath();
    ctx.fillStyle = "#0f2040";
    ctx.fill();
    ctx.strokeStyle = frameStroke;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Draw top face
    ctx.beginPath();
    ctx.moveTo(topCorners[0][0], topCorners[0][1]);
    for (let i = 1; i < 4; i++) {
      ctx.lineTo(topCorners[i][0], topCorners[i][1]);
    }
    ctx.closePath();
    ctx.fillStyle = frameColor;
    ctx.fill();
    ctx.strokeStyle = frameStroke;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw vertical edges
    ctx.strokeStyle = frameStroke;
    ctx.lineWidth = 1;
    for (let i = 0; i < 4; i++) {
      ctx.beginPath();
      ctx.moveTo(botCorners[i][0], botCorners[i][1]);
      ctx.lineTo(topCorners[i][0], topCorners[i][1]);
      ctx.stroke();
    }

    // ── Center accent dot ─────────────────────────────────────────
    const [cdx, cdy] = project(0, 0, frameD);
    ctx.beginPath();
    ctx.arc(cdx, cdy, 8, 0, Math.PI * 2);
    ctx.fillStyle = accentColor;
    ctx.fill();
    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 1;
    ctx.stroke();

    // ── Axis indicator (bottom-left) ──────────────────────────────
    const ax = 30;
    const ay = h - 35;
    const axisLen = 30;

    // X axis (forward — red/accent)
    drawAxisLine(ctx, ax, ay, axisLen, -Math.PI / 6, accentColor, "X");

    // Y axis (lateral — green)
    drawAxisLine(ctx, ax, ay, axisLen, Math.PI / 6, "#4caf50", "Y");

    // Z axis (up — blue)
    drawAxisLine(ctx, ax, ay, axisLen, -Math.PI / 2, "#2196f3", "Z");
  }, [pitch, roll, yaw]);

  return (
    <div className="bg-panel border border-border rounded-md flex flex-col h-full overflow-hidden">
      {/* Title bar */}
      <div className="bg-border text-text-title text-[11px] font-bold tracking-wider px-2 py-1 uppercase shrink-0">
        ROV DESIGN
      </div>

      {/* Canvas */}
      <div className="flex-1 flex items-center justify-center min-h-0 bg-panel-dark">
        <canvas
          ref={canvasRef}
          width={CANVAS_W}
          height={CANVAS_H}
          className="max-w-full max-h-full"
        />
      </div>

      {/* State badge */}
      <div className="text-center text-text-dim text-[10px] py-1.5 border-t border-border shrink-0">
        STATE: P:{pitch.toFixed(0)}° R:{roll.toFixed(0)}° Y:{yaw.toFixed(0)}°
      </div>
    </div>
  );
}

function drawAxisLine(
  ctx: CanvasRenderingContext2D,
  ox: number,
  oy: number,
  len: number,
  angle: number,
  color: string,
  label: string
) {
  const dx = len * Math.cos(angle);
  const dy = len * Math.sin(angle);

  ctx.beginPath();
  ctx.moveTo(ox, oy);
  ctx.lineTo(ox + dx, oy + dy);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.stroke();

  // Arrowhead
  const tipX = ox + dx;
  const tipY = oy + dy;
  const arrowLen = 6;
  const perpAngle = angle - Math.PI / 2;
  ctx.beginPath();
  ctx.moveTo(tipX, tipY);
  ctx.lineTo(
    tipX - arrowLen * Math.cos(angle) + arrowLen * 0.5 * Math.cos(perpAngle),
    tipY - arrowLen * Math.sin(angle) + arrowLen * 0.5 * Math.sin(perpAngle)
  );
  ctx.lineTo(
    tipX - arrowLen * Math.cos(angle) - arrowLen * 0.5 * Math.cos(perpAngle),
    tipY - arrowLen * Math.sin(angle) - arrowLen * 0.5 * Math.sin(perpAngle)
  );
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.fill();

  // Label
  ctx.fillStyle = color;
  ctx.font = "bold 9px monospace";
  ctx.textAlign = "center";
  ctx.fillText(
    label,
    tipX + 10 * Math.cos(angle),
    tipY + 10 * Math.sin(angle) + 3
  );
}
