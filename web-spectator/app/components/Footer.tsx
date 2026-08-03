"use client";

interface Props {
  online: boolean;
  mode: string;
  armed: boolean;
  voltage: number;
}

function Led({ color }: { color: string }) {
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
      style={{ backgroundColor: color }}
    />
  );
}

function Sep() {
  return <span className="text-border text-sm mx-1">|</span>;
}

export default function Footer({ online, mode, armed, voltage }: Props) {
  const connColor = online ? "#4caf50" : "#f44336";
  const bar30Color = online ? "#4caf50" : "#f44336";
  const battColor = voltage > 0 ? "#4caf50" : "#607d8b";
  const modeColor =
    mode === "E-STOP" ? "#f44336"
    : mode === "AUTONOMOUS" ? "#ff9800"
    : "#4caf50";

  return (
    <footer className="h-9 bg-panel-dark border-t border-border flex items-center px-3 gap-0 shrink-0">
      <Led color={modeColor} />
      <span className="text-text-dim text-[10px] ml-1">MODE: {mode}</span>
      <Sep />
      <Led color={connColor} />
      <span className="text-text-dim text-[10px] ml-1">
        CONNECTION: {online ? "ONLINE" : "OFFLINE"}
      </span>
      <Sep />
      <Led color={bar30Color} />
      <span className="text-text-dim text-[10px] ml-1">
        BAR30: {online ? "OK" : "OFFLINE"}
      </span>
      <Sep />
      <Led color={battColor} />
      <span className="text-text-dim text-[10px] ml-1">
        BATT: {voltage > 0 ? `${voltage.toFixed(1)}V` : "OFFLINE"}
      </span>
      <Sep />
      <Led color="#607d8b" />
      <span className="text-text-dim text-[10px] ml-1">GAMEPAD: —</span>
      <Sep />
      <Led color={online ? "#4caf50" : "#f44336"} />
      <span className="text-text-dim text-[10px] ml-1">
        IMU: {online ? "OK" : "OFFLINE"}
      </span>
      <Sep />
      <Led color="#607d8b" />
      <span className="text-text-dim text-[10px] ml-1">LOG: IDLE</span>
    </footer>
  );
}
