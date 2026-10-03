import { useState, type ReactNode } from 'react';
import { CameraTile } from './CameraTile';

interface Props {
  printerId: number;
  printerName: string;
  connected: boolean;
  canViewCamera: boolean;
  cameraRotation?: number;
  children: ReactNode;
}

/** Browser-local presentation preference; never sends printer controls. */
export function PrinterCardPreview({ printerId, printerName, connected, canViewCamera, cameraRotation, children }: Props) {
  const key = `printerCardLivePreview:${printerId}`;
  const [live, setLive] = useState(() => {
    try { return localStorage.getItem(key) === 'true'; } catch { return false; }
  });
  const showLive = live && canViewCamera;
  const toggle = () => {
    const next = !showLive;
    setLive(next);
    try { localStorage.setItem(key, String(next)); } catch { /* Session-only if storage is blocked. */ }
  };
  return (
    <div className="relative w-[7.2rem] h-[7.2rem] max-[520px]:w-24 max-[520px]:h-24 shrink-0 overflow-hidden rounded-lg">
      {showLive ? (
        <CameraTile printerId={printerId} printerName={printerName} connected={connected}
          cameraRotation={cameraRotation} mode="live" snapshotIntervalMs={5000} compact />
      ) : children}
      {canViewCamera && (
        <button type="button" onClick={toggle} aria-pressed={showLive}
          aria-label={showLive ? 'Show print preview' : 'Show live webcam'}
          className="absolute bottom-1 left-1 right-1 z-10 rounded bg-black/80 px-1 py-1 text-[10px] font-medium text-[#fff] hover:bg-black focus-visible:outline focus-visible:outline-2 focus-visible:outline-bambu-green">
          {showLive ? 'Print preview' : 'Live webcam'}
        </button>
      )}
    </div>
  );
}
