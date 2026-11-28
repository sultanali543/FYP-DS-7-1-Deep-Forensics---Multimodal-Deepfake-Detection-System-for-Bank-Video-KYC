import { useEffect, useRef, useState } from 'react';
import Icon from '../components/Icon.jsx';
import { Badge, Button, Notice, PageHeading } from '../components/UI.jsx';
import { formatSize, scorePercent, validateVideo } from '../lib/utils.js';
import { runBatch } from '../lib/batchQueue.js';
import { analysisService } from '../services/analysisService.js';
import { SCENARIOS } from '../mocks/analyses.js';

const MAX_BATCH = 20;
const labels = { ready: 'Ready', rejected: 'Check file', waiting: 'Waiting for slot', uploading: 'Uploading', queued: 'Queued', running: 'Analyzing', complete: 'Complete', failed: 'Failed', insufficient_evidence: 'Insufficient evidence' };

export default function BatchPage({ isDemo, health, onRecord, onOpen, onExport, onProgress }) {
  const input = useRef(null);
  const controller = useRef(null);
  const [rows, setRows] = useState([]);
  const [running, setRunning] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [scenario, setScenario] = useState('fake');
  const [message, setMessage] = useState('');

  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { onProgress(running ? 'BATCH ACTIVE' : rows.length ? `${rows.length} SELECTED` : 'BATCH READY'); }, [running, rows.length, onProgress]);

  function addFiles(files) {
    const selected = Array.from(files || []);
    if (!selected.length) return;
    if (running) return;
    setRows((current) => {
      const keys = new Set(current.map((row) => `${row.file.name}:${row.file.size}:${row.file.lastModified}`));
      const added = [];
      for (const file of selected) {
        if (current.length + added.length >= MAX_BATCH) break;
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (keys.has(key)) continue;
        keys.add(key);
        const error = validateVideo(file);
        added.push({ id: crypto.randomUUID(), file, status: error ? 'rejected' : 'ready', error, result: null });
      }
      return [...current, ...added];
    });
    setMessage(selected.length + rows.length > MAX_BATCH ? `A batch can contain up to ${MAX_BATCH} videos.` : '');
  }

  async function start() {
    if (running || (!isDemo && !health?.ready)) return;
    const items = rows.filter((row) => row.status === 'ready');
    if (!items.length) return;
    const abort = new AbortController();
    controller.current = abort;
    setRunning(true);
    setMessage('');
    try {
      await runBatch(items, {
        service: analysisService, scenario, signal: abort.signal,
        onUpdate: (id, patch) => setRows((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row)),
        onResult: onRecord,
      });
    } finally {
      controller.current = null;
      setRunning(false);
    }
  }

  const readyCount = rows.filter((row) => row.status === 'ready').length;
  const doneCount = rows.filter((row) => ['complete', 'failed', 'insufficient_evidence'].includes(row.status)).length;
  return <section className="batch-page">
    <PageHeading eyebrow="02 / BATCH WORKSTATION" title="Analyze a collection of sessions.">Select up to {MAX_BATCH} MP4 files. Each video receives its own analysis and result.</PageHeading>
    <Notice tone="amber">{isDemo ? 'Demo mode uses fixed sample scores for every selected video. No model inference occurs.' : 'Connected mode uses the local models. The backend currently processes one video at a time while later submissions wait in its queue.'}</Notice>
    <div className="batch-toolbar">
      <input ref={input} className="visually-hidden" type="file" accept="video/mp4,.mp4" multiple aria-label="Choose multiple MP4 videos" onChange={(event) => { addFiles(event.target.files); event.target.value = ''; }} />
      <div className={`batch-dropzone ${dragging ? 'dragging' : ''}`} onDragOver={(event) => event.preventDefault()} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={(event) => { event.preventDefault(); setDragging(false); }} onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }}>
        <Icon name="upload" size={31} /><div><strong>Drop multiple KYC videos here</strong><span>MP4 · 50 MB per file · maximum {MAX_BATCH} per batch</span></div>
        <Button variant="secondary" onClick={() => input.current?.click()} disabled={running}>Choose videos</Button>
      </div>
      <div className="batch-actions"><div><strong>{rows.length} selected</strong><span>{doneCount} finished · {readyCount} ready</span></div>{isDemo && <label>DEMO SCENARIO <select value={scenario} onChange={(event) => setScenario(event.target.value)} disabled={running}>{SCENARIOS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}<Button onClick={start} disabled={!readyCount || running || (!isDemo && !health?.ready)} icon="scan">{running ? 'Batch running…' : 'Start batch'}</Button></div>
      {message && <p className="batch-message" role="alert">{message}</p>}
    </div>
    <div className="batch-list-head"><h2>Batch queue</h2><div>{!running && rows.length > 0 && <button className="text-button" onClick={() => setRows([])}>Clear list</button>}{doneCount > 0 && <button className="text-button" onClick={() => onExport(rows.filter((row) => row.result).map((row) => row.result))}>Export results JSON</button>}</div></div>
    {rows.length === 0 ? <div className="batch-empty"><Icon name="video" size={32} /><strong>No videos selected</strong><span>Add MP4 files to prepare the queue.</span></div> : <div className="batch-list">{rows.map((row, index) => <article className="batch-row" key={row.id}><span className="batch-index">{String(index + 1).padStart(2, '0')}</span><span className="batch-file"><strong title={row.file.name}>{row.file.name}</strong><small>{formatSize(row.file.size)}{row.jobId ? ` · ${row.jobId}` : ''}{Number.isFinite(row.result?.elapsed_seconds) ? ` · ${row.result.elapsed_seconds}s` : ''}</small>{row.error && <em>{row.error}</em>}</span><Badge tone={row.status === 'complete' ? 'success' : row.status === 'failed' || row.status === 'rejected' ? 'danger' : row.status === 'insufficient_evidence' ? 'amber' : undefined}>{labels[row.status] || row.status}</Badge>{row.result?.visual?.score != null && <span className="batch-score">{scorePercent(row.result.visual.score)} <small>{row.result.visual.verdict}</small></span>}{row.result && <Button variant="secondary" onClick={() => onOpen(row.result)}>View result</Button>}{!running && ['ready', 'rejected'].includes(row.status) && <button className="icon-button" aria-label={`Remove ${row.file.name}`} onClick={() => setRows((current) => current.filter((item) => item.id !== row.id))}><Icon name="close" size={17} /></button>}</article>)}</div>}
    <p className="batch-footnote">Two submissions can be in flight. Processing speed depends on the backend worker and model hardware. Uploaded backend copies are deleted after each analysis; the source files stay on your computer.</p>
  </section>;
}
