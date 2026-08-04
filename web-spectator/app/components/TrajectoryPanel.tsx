"use client";

import { useRef, useEffect, useCallback } from "react";

interface Props {
  heading: number;
  posX?: number;
  posY?: number;
  posDist?: number;
  poolSize?: number;
}

const CANVAS_W = 340;
const CANVAS_H = 340;

/**
 * 2D top-down trajectory map on Canvas.
 * - Dashed pool boundary (5m × 5m)
 * - Red breadcrumb path trail connecting historical (x, y) points
 * - White current-position dot
 * - Cyan heading vector arrow
 * - Readout: X, Y, HDG, DIST
 */
export default function TrajectoryPanel({
  heading,
  posX = 0,
  posY = 0,
  posDist = 0,
  poolSize = 5,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const historyRef = useRef<{ x: number; y: number }[]>([]);

  // Append new position to history (dedup very close points)
  const prevRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const prev = prevRef.current;
    const dx = prev ? posX - prev.x : 999;
    const dy = prev ? posY - prev.y : 999;
    if (prev === null || Math.abs(dx) > 0.01 || Math.abs(dy) > 0.01) {
      historyRef.current.push({ x: posX, y: posY });
      if (historyRef.current.length > 2000) {
        historyRef.current = historyRef.current.slice(-2000);
      }
      prevRef.current = { x: posX, y: posY };
    }
  }, [posX, posY]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = CANVAS_W;
    const H = CANVAS_H;
    const margin = 28;

    ctx.clearRect(0, 0, W, H);

    // ── Background ──────────────────────────────────────────────────
    ctx.fillStyle = "#0d1b2a";
    ctx.fillRect(0, 0, W, H);

    // ── Coordinate mapping ──────────────────────────────────────────
    const plotW = W - margin * 2;
    const plotH = H - margin * 2;
    const scaleX = plotW / poolSize;
    const scaleY = plotH / poolSize;

    function toScreenX(wx: number) {
      return margin + wx * scaleX;
    }
    function toScreenY(wy: number) {
      return margin + plotH - wy * scaleY; // invert Y (screen Y goes down, world Y goes up)
    }

    // ── Pool boundary (dashed) ──────────────────────────────────────
    ctx.strokeStyle = "#0f3460";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(
      toScreenX(0),
      toScreenY(poolSize),
      plotW,
      plotH
    );
    ctx.setLineDash([]);

    // ── Grid lines ──────────────────────────────────────────────────
    ctx.strokeStyle = "rgba(15, 52, 96, 0.3)";
    ctx.lineWidth = 0.5;
    for (let i = 1; i < poolSize; i++) {
      // Vertical
      ctx.beginPath();
      ctx.moveTo(toScreenX(i), toScreenY(0));
      ctx.lineTo(toScreenX(i), toScreenY(poolSize));
      ctx.stroke();
      // Horizontal
      ctx.beginPath();
      ctx.moveTo(toScreenX(0), toScreenY(i));
      ctx.lineTo(toScreenX(poolSize), toScreenY(i));
      ctx.stroke();
    }

    // ── Axis labels ─────────────────────────────────────────────────
    ctx.fillStyle = "#7a8a99";
    ctx.font = "9px monospace";
    ctx.textAlign = "center";
    for (let i = 0; i <= poolSize; i++) {
      ctx.fillText(`${i}`, toScreenX(i), toScreenY(0) + 14);
      ctx.fillText(`${i}`, toScreenX(0) - 16, toScreenY(i) + 3);
    }

    // ── Breadcrumb path (red trail) ─────────────────────────────────
    const history = historyRef.current;
    if (history.length > 0) {
      // Draw the path line
      ctx.beginPath();
      const firstPt = history[0];
      ctx.moveTo(toScreenX(firstPt.x), toScreenY(firstPt.y));
      for (let i = 1; i < history.length; i++) {
        ctx.lineTo(toScreenX(history[i].x), toScreenY(history[i].y));
      }
      ctx.strokeStyle = "#e94560";
      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
      ctx.stroke();
    }

    // ── Current position (white dot) ────────────────────────────────
    const sx = toScreenX(posX);
    const sy = toScreenY(posY);

    // Glow
    ctx.beginPath();
    ctx.arc(sx, sy, 8, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255, 255, 255, 0.3)";
    ctx.fill();

    // Dot
    ctx.beginPath();
    ctx.arc(sx, sy, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.strokeStyle = "#e94560";
    ctx.lineWidth = 1;
    ctx.stroke();

    // ── Heading arrow (cyan) ────────────────────────────────────────
    // Convert heading: 0°=East (→ screen right), CCW positive on map
    // Screen: 0°=right, 90°=up
    const headingRad = (heading * Math.PI) / 180;
    const arrowLen = 18;
    const tipX = sx + arrowLen * Math.cos(headingRad);
    const tipY = sy - arrowLen * Math.sin(headingRad); // invert Y for screen

    ctx.beginPath();
    ctx.moveTo(sx, sy);
    ctx.lineTo(tipX, tipY);
    ctx.strokeStyle = "#00BFFF";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.stroke();

    // Arrowhead
    const headLen = 6;
    const headAngle = 0.5;
    const a1 = headingRad - Math.PI + headAngle;
    const a2 = headingRad - Math.PI - headAngle;
    ctx.beginPath();
    ctx.moveTo(tipX, tipY);
    ctx.lineTo(
      tipX + headLen * Math.cos(a1),
      tipY - headLen * Math.sin(a1)
    );
    ctx.lineTo(
      tipX + headLen * Math.cos(a2),
      tipY - headLen * Math.sin(a2)
    );
    ctx.closePath();
    ctx.fillStyle = "#00BFFF";
    ctx.fill();
  }, [heading, posX, posY, poolSize]);

  useEffect(() => {
    draw();
  }, [draw]);

  // Reset history when pool size changes (component remount)
  useEffect(() => {
    historyRef.current = [];
    prevRef.current = null;
  }, []);

  return (
    <div className="bg-panel border border-border rounded-md flex flex-col h-full overflow-hidden">
      {/* Title */}
      <div className="bg-border text-text-title text-[11px] font-bold tracking-wider px-2 py-1 uppercase shrink-0">
        TRAJECTORY MAP
      </div>

      {/* Canvas + readout row */}
      <div className="flex flex-1 min-h-0">
        {/* Canvas */}
        <div className="flex-[3] flex items-center justify-center bg-panel-dark min-h-0">
          <canvas
            ref={canvasRef}
            width={CANVAS_W}
            height={CANVAS_H}
            className="max-w-full max-h-full"
          />
        </div>

        {/* Right sidebar — readouts */}
        <div className="flex-[1] flex flex-col justify-center gap-2 px-2 py-2 border-l border-border min-w-[90px]">
          {/* Position */}
          <div className="text-text-dim text-[10px] leading-tight">
            <span className="block text-[8px] uppercase tracking-wider">Position</span>
            <span className="text-text text-xs tabular-nums">
              X: {posX.toFixed(1)}m
            </span>
            <br />
            <span className="text-text text-xs tabular-nums">
              Y: {posY.toFixed(1)}m
            </span>
          </div>

          {/* Heading */}
          <div className="text-cyan text-[10px] leading-tight">
            <span className="block text-[8px] uppercase tracking-wider">Heading</span>
            <span className="text-xs tabular-nums font-bold">
              {heading.toFixed(1)}°
            </span>
          </div>

          {/* Distance */}
          <div className="text-text-dim text-[10px] leading-tight">
            <span className="block text-[8px] uppercase tracking-wider">Distance</span>
            <span className="text-text text-xs tabular-nums">
              {posDist.toFixed(2)}m
            </span>
          </div>

          {/* Pool size */}
          <div className="text-text-dim/60 text-[9px] mt-1">
            {poolSize.toFixed(0)}×{poolSize.toFixed(0)}m
          </div>
        </div>
      </div>
    </div>
  );
}
