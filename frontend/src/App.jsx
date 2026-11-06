import { useCallback, useEffect, useRef, useState } from 'react';
import AppLayout from './components/AppLayout.jsx';
import { Button, Modal, Notice } from './components/UI.jsx';
import ReportView from './components/ReportView.jsx';
import UploadPage from './pages/UploadPage.jsx';
import ProcessingPage from './pages/ProcessingPage.jsx';
import ResultsPage from './pages/ResultsPage.jsx';
import HistoryPage from './pages/HistoryPage.jsx';
import { analysisService } from './services/analysisService.js';
import { readHistory, writeHistory, validateVideo } from './lib/utils.js';

function saveDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function App() {
  const [view, setView] = useState('upload');
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [source, setSource] = useState(null);
  const [ready, setReady] = useState(false);
  const [fileError, setFileError] = useState(null);
  const [scenario, setScenario] = useState('fake');
  const [active, setActive] = useState(null);
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [previewAnalysisId, setPreviewAnalysisId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [reportOpen, setReportOpen] = useState(false);
  const [appError, setAppError] = useState(null);
  const [history, setHistory] = useState(() => { try { return readHistory(window.sessionStorage); } catch { return []; } });
  const startController = useRef(null);
  const reportController = useRef(null);
  const fileRef = useRef(file);
  fileRef.current = file;

  useEffect(() => {
    if (!file) { setPreviewUrl(null); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => { try { writeHistory(window.sessionStorage, history); } catch { /* The current session still works when storage is unavailable. */ } }, [history]);
  useEffect(() => () => { startController.current?.abort(); reportController.current?.abort(); }, []);
  useEffect(() => {
    document.title = `${view === 'results' ? 'Analysis results' : view === 'history' ? 'Recent sessions' : view === 'processing' ? 'Processing' : 'New analysis'} · Deep Forensics`;
    window.scrollTo(0, 0);
    document.getElementById('main-content')?.focus({ preventScroll: true });
  }, [view]);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let timer;
    let stopped = false;
    function finish(data) {
      const record = { ...data, source: data.source || active.source, created_at: data.created_at || active.created_at };
      setResult(record);
      setHistory((old) => [record, ...old.filter((entry) => entry.id !== record.id)].slice(0, 20));
      setActive(null); setView('results');
    }
    async function poll() {
      try {
        const data = await analysisService.getAnalysis(active.id, { signal: controller.signal });
        if (stopped) return;
        setProgress(data);
        if (['complete', 'failed', 'insufficient_evidence'].includes(data.status)) finish(data);
        else timer = setTimeout(poll, 650);
      } catch (error) {
        if (stopped || error.name === 'AbortError') return;
        finish({ id: active.id, status: 'failed', mode: analysisService.isDemo ? 'demo' : 'live', scope: 'visual_only', error: error.message, audio: { status: 'not_implemented', score: null }, evidence: [] });
      }
    }
    poll();
    return () => { stopped = true; clearTimeout(timer); controller.abort(); analysisService.releaseAnalysis(active.id); };
  }, [active]);

  function resetUpload() {
    startController.current?.abort();
    setSubmitting(false); setActive(null); setProgress(null); setResult(null); setAppError(null); setFile(null); setSource(null); setReady(false); setFileError(null); setPreviewAnalysisId(null); setView('upload');
  }

  function selectFile(nextFile) {
    const error = validateVideo(nextFile);
    setReady(false); setSource(null); setFileError(error); setResult(null); setPreviewAnalysisId(null);
    setFile(error ? null : nextFile);
  }

  const invalidatePreview = useCallback((message) => { setReady(false); setFileError(message); }, []);

  async function startAnalysis(example = false) {
    if (submitting || active) return;
    if (!example && (!file || !ready || fileError)) return;
    const selectedSource = example ? { kind: 'example', name: 'Example verification session', size: null, duration: null } : { kind: 'upload', name: file.name, size: file.size, duration: source.duration, width: source.width, height: source.height };
    const selectedFile = file;
    if (example) { setFile(null); setSource(null); setReady(false); setFileError(null); }
    const controller = new AbortController();
    startController.current = controller;
    setSubmitting(true); setAppError(null);
    try {
      const created = await analysisService.createAnalysis(example ? null : selectedFile, { scenario, source: selectedSource, signal: controller.signal });
      if (controller.signal.aborted) return;
      setActive({ id: created.id, source: selectedSource, created_at: new Date().toISOString() });
      setPreviewAnalysisId(created.id); setProgress({ stage: 'queued' }); setResult(null); setView('processing');
    } catch (error) { if (error.name !== 'AbortError') setAppError(error.message); }
    finally { if (startController.current === controller) { setSubmitting(false); startController.current = null; } }
  }

  function navigate(nextView) {
    if (nextView === 'upload') resetUpload();
    else { setAppError(null); setView(nextView); }
  }

  async function downloadBackendReport() {
    if (downloading || !result) return;
    const controller = new AbortController(); reportController.current = controller;
    setDownloading(true); setAppError(null);
    try { const blob = await analysisService.downloadReport(result.id, { signal: controller.signal }); saveDownload(blob, `${result.id}-report.pdf`); }
    catch (error) { if (error.name !== 'AbortError') setAppError(error.message); }
    finally { setDownloading(false); reportController.current = null; }
  }

  function retryAnalysis() {
    if (result?.source.kind === 'example') startAnalysis(true);
    else if (file && ready) startAnalysis(false);
    else resetUpload();
  }

  const isDemo = analysisService.isDemo;
  const busy = !!active || submitting;
  return <>
    <AppLayout {...{ view, isDemo, busy }} historyCount={history.length} onNavigate={navigate} onHelp={() => setHelpOpen(true)}>
      {appError && <div className="app-error"><Notice tone="danger" icon="warning">{appError}</Notice><button className="text-button" onClick={() => setAppError(null)}>Dismiss</button></div>}
      {view === 'upload' && <UploadPage {...{ isDemo, scenario, setScenario, file, source, ready, submitting }} url={previewUrl} error={fileError} onSelect={selectFile} onReady={(metadata) => { if (fileRef.current !== file) return; setSource(metadata); setReady(true); setFileError(null); }} onInvalid={invalidatePreview} onRemove={() => { setFile(null); setSource(null); setReady(false); setFileError(null); }} onStart={() => startAnalysis(false)} onExample={() => startAnalysis(true)} />}
      {view === 'processing' && active && <ProcessingPage {...{ active, progress, isDemo }} onLeave={() => { setActive(null); setProgress(null); setView('upload'); }} />}
      {view === 'results' && result && <ResultsPage {...{ result, downloading }} previewUrl={previewAnalysisId === result.id ? previewUrl : null} onNew={resetUpload} onRetry={retryAnalysis} onReport={() => setReportOpen(true)} onJson={() => saveDownload(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }), `${result.id}-result.json`)} onBackendReport={downloadBackendReport} />}
      {view === 'history' && <HistoryPage records={history} onOpen={(record) => { setResult(record); setAppError(null); setView('results'); }} onClear={() => setHistory([])} onNew={resetUpload} />}
    </AppLayout>
    {helpOpen && <Modal title="About this workspace" onClose={() => setHelpOpen(false)} footer={<Button onClick={() => setHelpOpen(false)}>Back to workspace</Button>}><div className="guide-content"><p className="eyebrow">DEEP FORENSICS / RESEARCH PROTOTYPE</p><h3>A workspace for reviewing video verification sessions.</h3><p>The proposed system combines facial manipulation detection, audio spoof detection, explainability, and forensic reporting. This frontend lets you explore that workflow before model integration.</p><ol><li><strong>Choose a video or an example.</strong><span>MP4 previews work locally. Examples have no attached video.</span></li><li><strong>Select a demo scenario.</strong><span>Completed, uncertain, insufficient-evidence, and failure outcomes can all be explored.</span></li><li><strong>Review and export.</strong><span>Inspect the result, export JSON, or print a clearly labeled sample report.</span></li></ol><Notice>Demo scores are fixed fixtures. Audio detection, Grad-CAM, cryptographic fingerprints, and digital signing are not implemented.</Notice><p className="guide-small">To connect FastAPI later, set VITE_USE_MOCKS=false and configure VITE_API_BASE_URL. The frontend README describes the expected endpoints.</p></div></Modal>}
    {reportOpen && result && <Modal title={result.mode === 'demo' ? 'Sample report preview' : 'Analysis summary'} onClose={() => setReportOpen(false)} footer={<><Button variant="secondary" onClick={() => setReportOpen(false)}>Close</Button><Button icon="print" onClick={() => window.print()}>Print / Save PDF</Button></>}><ReportView result={result} /></Modal>}
    {result?.status === 'complete' && <div className="print-report"><ReportView result={result} /></div>}
  </>;
}
