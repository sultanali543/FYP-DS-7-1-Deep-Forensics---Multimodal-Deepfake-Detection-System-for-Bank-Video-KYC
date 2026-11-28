import { useState } from 'react';
import Icon from './Icon.jsx';

export function ProcessingStreams({ isDemo, audioReady }) {
  return <section className="stream-workflow" aria-label="Two analysis channels">
    <div className="stream-workflow-head"><span>DUAL-STREAM WORKFLOW</span><small>{isDemo ? 'SIMULATED STAGES' : 'SERVER-REPORTED STAGES'}</small></div>
    <div className="stream-split"><span>RECORDED VIDEO</span><span className="split-line" /><span>VISUAL + AUDIO</span></div>
    <div className="stream-panels"><article className="stream-panel visual-stream"><div className="stream-panel-heading"><Icon name="scan" size={21} /><span>MODULE A / VISUAL FORENSICS</span></div><div className="stream-visual"><div className="stream-frame"><span className="stream-sweep" /><Icon name="scan" size={54} /></div></div><p>{isDemo ? 'Illustrative face-frame pipeline. The demo does not analyze a video.' : 'Face frames are checked by the local visual model. Face boxes and Grad-CAM are not yet provided as evidence.'}</p></article><article className="stream-panel audio-stream"><div className="stream-panel-heading"><Icon name="audio" size={21} /><span>MODULE B / ACOUSTIC FORENSICS</span></div><div className="stream-wave" aria-hidden="true">{Array.from({ length: 38 }, (_, index) => <span key={index} style={{ height: `${14 + ((index * 37 + index * index * 11) % 65)}%` }} />)}</div><p>{isDemo ? 'Illustrative audio visualization. The demo does not analyze a voice.' : audioReady ? 'The server checks usable audio with the installed speech model. This graphic is illustrative.' : 'Audio model is not installed. This graphic is illustrative.'}</p></article></div>
  </section>;
}

function localEvidenceUrl(value) {
  if (typeof value !== 'string') return null;
  if (/^data:image\/(png|jpeg|webp);base64,[a-z0-9+/=]+$/i.test(value)) return value;
  if (value.startsWith('/') && !value.startsWith('//')) return value;
  return null;
}

export function EvidenceInspector({ result }) {
  const [index, setIndex] = useState(0);
  const [opacity, setOpacity] = useState(55);
  const frames = Array.isArray(result.evidence) ? result.evidence.filter((item) => localEvidenceUrl(item?.image_url)) : [];
  const frame = frames[Math.min(index, frames.length - 1)];
  const baseImage = localEvidenceUrl(frame?.base_image_url);
  const overlayReady = Boolean(baseImage && frame?.kind === 'grad_cam');
  const spectrogram = localEvidenceUrl(result.audio?.spectrogram_url);
  return <section className="inspector-section"><div className="inspector-heading"><div><span className="command-kicker">FORENSIC INSPECTOR / EXPERIMENTAL</span><h2>Inspect each signal separately.</h2></div><span className="inspector-scope">{result.mode === 'demo' ? 'SAMPLE SESSION' : 'LOCAL ANALYSIS'}</span></div><div className="inspector-grid"><article className="inspector-panel"><div className="inspector-panel-head"><span><Icon name="scan" size={19} /> VISUAL / FRAME EVIDENCE</span><small>{frames.length} FRAME IMAGES</small></div><div className="inspector-canvas">{frame ? <>{overlayReady && <img src={baseImage} alt="Source face frame" />}<img src={localEvidenceUrl(frame.image_url)} alt={frame.caption || 'Model evidence frame'} style={{ opacity: overlayReady ? opacity / 100 : 1, position: overlayReady ? 'absolute' : 'relative' }} /></> : <div className="inspector-empty"><Icon name="scan" size={44} /><strong>No frame images supplied</strong><span>{result.mode === 'demo' ? 'Sample sessions contain no image evidence.' : 'The current backend returns scores, without RetinaFace boxes or Grad-CAM heatmaps.'}</span></div>}</div><div className="inspector-controls"><label htmlFor="frame-scrub">FRAME <input id="frame-scrub" type="range" min="0" max={Math.max(0, frames.length - 1)} value={Math.min(index, Math.max(0, frames.length - 1))} onChange={(event) => setIndex(Number(event.target.value))} disabled={frames.length < 2} /></label><label htmlFor="heat-opacity">HEATMAP <input id="heat-opacity" type="range" min="0" max="100" value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} disabled={!overlayReady} /></label></div></article><article className="inspector-panel"><div className="inspector-panel-head"><span><Icon name="audio" size={19} /> AUDIO / SPECTRAL EVIDENCE</span><small>{result.audio?.status === 'complete' ? 'MODEL SCORE AVAILABLE' : 'NO AUDIO SCORE'}</small></div><div className="inspector-canvas">{spectrogram ? <img src={spectrogram} alt="Audio spectrogram supplied by the analysis server" /> : <div className="inspector-empty"><Icon name="audio" size={44} /><strong>No spectrogram supplied</strong><span>Audio scores may be available above. Spectral evidence is a future backend output.</span></div>}</div><p className="inspector-note">Visual and audio scores are independent. No calibrated combined verdict is available.</p></article></div></section>;
}
