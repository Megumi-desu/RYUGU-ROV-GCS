"use client";

import { useEffect, useState } from "react";

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function formatClock(): string {
  const d = new Date();
  const day = DAYS[d.getDay()];
  const dom = String(d.getDate()).padStart(2, "0");
  const mon = MONTHS[d.getMonth()];
  const year = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${day}  ${dom} ${mon} ${year}    ${hh}:${mm}:${ss}`;
}

interface Props {
  online: boolean;
}

export default function TopBar({ online }: Props) {
  const [clock, setClock] = useState(formatClock());

  useEffect(() => {
    const id = setInterval(() => setClock(formatClock()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="h-[52px] bg-panel-dark border-b border-border flex items-center px-2 gap-2 shrink-0">
      {/* Logos */}
      <div className="flex items-center gap-1.5 ml-1">
        <img src="/logo_ub.png" alt="UB" className="h-9 w-9 object-contain" />
        <img src="/logo_team.png" alt="RYUGU" className="h-9 w-9 object-contain" />
      </div>

      {/* Team / Univ / Competition */}
      <span className="text-accent font-bold text-sm tracking-wide ml-1">RYUGU</span>
      <span className="text-border text-sm">|</span>
      <span className="text-text text-[13px]">Universitas Brawijaya</span>
      <span className="text-border text-sm">|</span>
      <span className="text-cyan font-bold text-[12px]">KKI 2026</span>

      <div className="flex-1" />

      {/* Connection badge */}
      <span
        className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
          online
            ? "bg-ok/20 text-ok border-ok/30"
            : "bg-error/20 text-error border-error/30"
        }`}
      >
        {online ? "🟢 LIVE" : "🔴 OFFLINE"}
      </span>

      {/* Clock */}
      <span className="text-text-dim font-mono text-xs mr-2 min-w-[210px] text-right">
        {clock}
      </span>

      {/* KKI Logo */}
      <img src="/logo_kki.png" alt="KKI" className="h-9 w-9 object-contain mr-1" />
    </header>
  );
}
