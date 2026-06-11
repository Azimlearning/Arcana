'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

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
  status: 'parsing' | 'embedding' | 'ready' | 'failed';
  error?: string | null;
}

type UploadPhase = 'idle' | 'uploading' | 'error';

const STATUS_LABEL: Record<IngestedDoc['status'], string> = {
  parsing: 'Parsing…',
  embedding: 'Embedding…',
  ready: 'Ready',
  failed: 'Failed',
};

const STATUS_COLOR: Record<IngestedDoc['status'], string> = {
  parsing:   'text-amber-600',
  embedding: 'text-blue-600',
  ready:     'text-ink-softer',
  failed:    'text-red-500',
};

export function SourcesPanel() {
  const [docs, setDocs] = useState<IngestedDoc[]>([]);
  const [phase, setPhase] = useState<UploadPhase>('idle');

  // Populate the list with previously ingested docs on mount.
  // GET /docs lists all docs in the shared store regardless of session.
  useEffect(() => {
    fetch(`${API_BASE}/docs`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { docs: Array<{ docId: string; title: string; status: string }> } | null) => {
        if (!data) return;
        const allDocs = data.docs.map((d) => ({
          docId: d.docId,
          title: d.title,
          chunkCount: 0,
          status: d.status as IngestedDoc['status'],
        }));
        setDocs(allDocs);
      })
      .catch(() => {
        // Network error on mount — panel stays empty until user uploads.
      });
  }, []);
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
      const data = (await res.json()) as { docId: string; title: string; chunkCount: number; status?: string };
      setDocs((prev) => {
        const rest = prev.filter((d) => d.docId !== data.docId);
        return [{ docId: data.docId, title: data.title, chunkCount: data.chunkCount, status: (data.status as IngestedDoc['status']) ?? 'ready' }, ...rest];
      });
      setPhase('idle');
    } catch (e) {
      setPhase('error');
      setErrorMsg((e as Error).message);
    }
  }, []);

  // FR-ING-08: retry a failed ingestion using stored bytes on the server.
  const retry = useCallback(async (doc: IngestedDoc) => {
    setDocs((prev) =>
      prev.map((d) =>
        d.docId === doc.docId ? { ...d, status: 'embedding' as const, error: null } : d,
      ),
    );
    try {
      const res = await fetch(
        `${API_BASE}/ingest/retry/${encodeURIComponent(doc.docId)}`,
        { method: 'POST' },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      const data = (await res.json()) as { docId: string; title: string; chunkCount: number; status?: string };
      setDocs((prev) =>
        prev.map((d) =>
          d.docId === data.docId
            ? { ...d, status: (data.status as IngestedDoc['status']) ?? 'ready', chunkCount: data.chunkCount }
            : d,
        ),
      );
    } catch (e) {
      setDocs((prev) =>
        prev.map((d) =>
          d.docId === doc.docId
            ? { ...d, status: 'failed' as const, error: (e as Error).message }
            : d,
        ),
      );
    }
  }, []);

  // While a doc is in-progress, poll every 2 s until it reaches a terminal state.
  useEffect(() => {
    const inProgress = docs.filter((d) => d.status === 'parsing' || d.status === 'embedding');
    if (inProgress.length === 0) return;

    const timer = setInterval(async () => {
      const updates = await Promise.all(
        inProgress.map(async (doc) => {
          try {
            const r = await fetch(`${API_BASE}/docs/${doc.docId}`);
            if (!r.ok) return null;
            return (await r.json()) as { docId: string; status: string; chunkCount?: number; error?: string };
          } catch {
            return null;
          }
        }),
      );
      setDocs((prev) =>
        prev.map((doc) => {
          const u = updates.find((x) => x?.docId === doc.docId);
          if (!u) return doc;
          return { ...doc, status: u.status as IngestedDoc['status'], error: u.error ?? null };
        }),
      );
    }, 2000);

    return () => clearInterval(timer);
  }, [docs]);

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
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-ink truncate" title={doc.title}>
                  {doc.title}
                </div>
                <div className={`text-xs mt-0.5 flex items-center gap-1.5 ${STATUS_COLOR[doc.status]}`}>
                  {(doc.status === 'parsing' || doc.status === 'embedding') && (
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                  )}
                  <span>
                    {doc.status === 'ready' && doc.chunkCount > 0
                      ? `${doc.chunkCount} chunks indexed`
                      : STATUS_LABEL[doc.status]}
                  </span>
                </div>
                {doc.status === 'failed' && doc.error && (
                  <p className="text-xs text-red-500 mt-1 leading-snug">{doc.error}</p>
                )}
              </div>
              {doc.status === 'failed' && (
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <button
                    onClick={() => void retry(doc)}
                    className="text-xs font-medium text-blue-500 hover:text-blue-700 transition-colors"
                    title="Retry ingestion"
                  >
                    Retry
                  </button>
                  <button
                    onClick={() => setDocs((prev) => prev.filter((d) => d.docId !== doc.docId))}
                    className="text-xs text-ink-softer hover:text-red-500 transition-colors"
                    title="Dismiss"
                  >
                    ✕
                  </button>
                </div>
              )}
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
