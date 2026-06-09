'use client';

import { useCallback, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);

interface IngestedDoc {
  docId: string;
  title: string;
  chunkCount: number;
}

type UploadPhase = 'idle' | 'uploading' | 'error';

export function SourcesPanel() {
  const [docs, setDocs] = useState<IngestedDoc[]>([]);
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = useCallback(async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setPhase('error');
      setErrorMsg('Only PDF files are supported.');
      return;
    }
    setPhase('uploading');
    setErrorMsg(null);

    const form = new FormData();
    form.append('file', file);
    form.append('notebook_id', 'demo');

    try {
      const res = await fetch(`${API_BASE}/ingest`, { method: 'POST', body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { docId: string; title: string; chunkCount: number };
      setDocs((prev) => {
        const rest = prev.filter((d) => d.docId !== data.docId);
        return [{ docId: data.docId, title: data.title, chunkCount: data.chunkCount }, ...rest];
      });
      setPhase('idle');
    } catch (e) {
      setPhase('error');
      setErrorMsg((e as Error).message);
    }
  }, []);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    e.target.value = '';
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void upload(file);
  };

  return (
    <aside className="h-full flex flex-col border-r border-line bg-paper">
      <div className="px-4 py-3 border-b border-line">
        <h2 className="font-display text-lg text-ink">Sources</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Drop zone */}
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload a PDF — click or drag and drop"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => phase !== 'uploading' && inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && phase !== 'uploading' && inputRef.current?.click()}
          className={[
            'rounded-lg border-2 border-dashed p-5 text-center transition-colors cursor-pointer select-none',
            dragging
              ? 'border-accent bg-accent/5'
              : 'border-line hover:border-accent/60 hover:bg-accent/5',
            phase === 'uploading' ? 'pointer-events-none opacity-60' : '',
          ].join(' ')}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={onFileChange}
          />
          {phase === 'uploading' ? (
            <p className="text-sm text-ink-soft animate-pulse">Ingesting…</p>
          ) : (
            <>
              <p className="text-sm font-medium text-ink">Upload a PDF</p>
              <p className="text-xs text-ink-softer mt-1">Click or drag &amp; drop</p>
            </>
          )}
        </div>

        {/* Error feedback */}
        {phase === 'error' && errorMsg && (
          <div className="flex items-start gap-2 rounded-md bg-red-50 border border-red-200 px-3 py-2">
            <p className="text-xs text-red-600 flex-1">{errorMsg}</p>
            <button
              className="text-xs text-red-400 hover:text-red-600 shrink-0"
              onClick={() => setPhase('idle')}
            >
              ✕
            </button>
          </div>
        )}

        {/* Ingested docs */}
        {docs.map((doc) => (
          <Card key={doc.docId} className="p-3 text-sm">
            <div className="font-medium text-ink truncate" title={doc.title}>
              {doc.title}
            </div>
            <div className="text-xs text-ink-softer mt-1">
              {doc.chunkCount > 0 ? `${doc.chunkCount} chunks indexed` : 'Indexed'}
            </div>
          </Card>
        ))}

        {/* Empty prompt */}
        {docs.length === 0 && phase !== 'uploading' && (
          <p className="text-xs text-ink-softer text-center pt-2">
            Upload a PDF to get started.
          </p>
        )}
      </div>
    </aside>
  );
}
