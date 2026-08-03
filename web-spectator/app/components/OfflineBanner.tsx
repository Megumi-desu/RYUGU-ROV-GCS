"use client";

interface Props {
  online: boolean;
}

export default function OfflineBanner({ online }: Props) {
  if (online) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-error/90 text-white text-center py-2 text-sm font-semibold tracking-wider backdrop-blur-sm">
      🔴 OFFLINE / GCS DISCONNECTED
    </div>
  );
}
