"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { supabase } from "@/lib/supabase";

export interface TelemetryStatus {
  online: boolean;
  armed: boolean;
  mode: string;
}

export interface TelemetryMetrics {
  depth: number;
  depth_raw: number;
  altitude: number;
  heading: number;
  pitch: number;
  roll: number;
  yaw: number;
  voltage: number;
  pos_x: number;
  pos_y: number;
  pos_dist: number;
}

export interface TelemetryQR {
  side: string;
  valid: boolean;
  text: string;
  logs: string[];
}

export interface TelemetryPayload {
  event: string;
  timestamp: number;
  status: TelemetryStatus;
  metrics: TelemetryMetrics;
  qr: TelemetryQR;
}

const HEARTBEAT_TIMEOUT_MS = 3000;
const CHANNEL = "realtime";
const EVENT = "telemetry";

const EMPTY_METRICS: TelemetryMetrics = {
  depth: 0,
  depth_raw: 0,
  altitude: 0,
  heading: 0,
  pitch: 0,
  roll: 0,
  yaw: 0,
  voltage: 0,
  pos_x: 0,
  pos_y: 0,
  pos_dist: 0,
};

const EMPTY_QR: TelemetryQR = {
  side: "",
  valid: false,
  text: "",
  logs: [],
};

const EMPTY_STATUS: TelemetryStatus = {
  online: false,
  armed: false,
  mode: "MANUAL",
};

export function useTelemetry() {
  const [payload, setPayload] = useState<TelemetryPayload>({
    event: EVENT,
    timestamp: 0,
    status: EMPTY_STATUS,
    metrics: EMPTY_METRICS,
    qr: EMPTY_QR,
  });
  const [online, setOnline] = useState(false);
  const lastSeenRef = useRef<number>(0);

  // ── Update the online flag every 1 s ────────────────────────────────
  const tickOnline = useCallback(() => {
    const now = Date.now();
    const alive = lastSeenRef.current > 0 && now - lastSeenRef.current < HEARTBEAT_TIMEOUT_MS;
    setOnline(alive);
  }, []);

  // ── Subscribe to Supabase Realtime Broadcast ────────────────────────
  useEffect(() => {
    const channel = supabase.channel(CHANNEL);

    channel
      .on("broadcast", { event: EVENT }, (msg: { payload: TelemetryPayload }) => {
        lastSeenRef.current = Date.now();
        setPayload(msg.payload);
        setOnline(true);
      })
      .subscribe((status: string) => {
        if (status === "SUBSCRIBED") {
          console.log("[useTelemetry] subscribed to", CHANNEL);
        }
        if (status === "CHANNEL_ERROR") {
          console.warn("[useTelemetry] channel error — will auto-reconnect");
        }
      });

    // Heartbeat: check online state every second
    const heartbeat = setInterval(tickOnline, 1000);

    return () => {
      clearInterval(heartbeat);
      supabase.removeChannel(channel);
    };
  }, [tickOnline]);

  return {
    payload,
    online,
    status: online ? payload.status : { ...EMPTY_STATUS, online: false },
    metrics: payload.metrics,
    qr: payload.qr ?? EMPTY_QR,
  };
}
