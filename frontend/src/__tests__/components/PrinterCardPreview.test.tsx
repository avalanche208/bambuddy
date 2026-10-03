import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import { render } from '../utils';
import { PrinterCardPreview } from '../../components/PrinterCardPreview';

const props = { printerId: 42, printerName: 'Workshop', connected: true, canViewCamera: true };
let stored: Record<string, string>;
beforeEach(() => {
  stored = {};
  vi.mocked(localStorage.getItem).mockImplementation(key => stored[key] ?? null);
  vi.mocked(localStorage.setItem).mockImplementation((key, value) => { stored[key] = value; });
  vi.spyOn(global, 'fetch').mockResolvedValue(new Response(null, { status: 200 }));
});
afterEach(() => vi.restoreAllMocks());

async function settle() { await act(async () => {}); }

describe('PrinterCardPreview', () => {
  it('defaults to preview and opens a stream only after toggling', async () => {
    render(<PrinterCardPreview {...props}><span>Model preview</span></PrinterCardPreview>);
    await settle();
    expect(screen.getByText('Model preview')).toBeInTheDocument();
    expect(screen.queryByAltText('Workshop')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Show live webcam' }));
    expect(screen.getByAltText('Workshop')).toHaveAttribute('src', expect.stringContaining('/42/camera/stream'));
    expect(stored['printerCardLivePreview:42']).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'Show print preview' }));
    expect(screen.getByText('Model preview')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith('/api/v1/printers/42/camera/stop', expect.any(Object));
  });
  it('restores preferences for the specific printer', async () => {
    stored['printerCardLivePreview:42'] = 'true';
    render(<><PrinterCardPreview {...props}>First</PrinterCardPreview><PrinterCardPreview {...props} printerId={43}>Second</PrinterCardPreview></>);
    await settle();
    expect(screen.getByAltText('Workshop')).toBeInTheDocument();
    expect(screen.getByText('Second')).toBeInTheDocument();
  });
  it('does not start a stored live view without camera permission', async () => {
    stored['printerCardLivePreview:42'] = 'true';
    render(<PrinterCardPreview {...props} canViewCamera={false}>Model preview</PrinterCardPreview>);
    await settle();
    expect(screen.getByText('Model preview')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.queryByAltText('Workshop')).not.toBeInTheDocument();
  });
  it('does not request an offline printer stream and can return to preview', async () => {
    stored['printerCardLivePreview:42'] = 'true';
    render(<PrinterCardPreview {...props} connected={false}>Model preview</PrinterCardPreview>);
    await settle();
    expect(screen.queryByAltText('Workshop')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Show print preview' }));
    expect(screen.getByText('Model preview')).toBeInTheDocument();
  });
});
