import { useState } from 'react';
import Icon from '../components/Icon.jsx';
import { Button } from '../components/UI.jsx';

const modules = [
  { index: '01', title: 'Visual forensics', detail: 'Face-frame screening in the connected app when the visual model is ready.', icon: 'scan', state: 'CONNECTED MODE' },
  { index: '02', title: 'Acoustic forensics', detail: 'Speech spoof screening when the audio model and a usable track are available.', icon: 'audio', state: 'WHEN INSTALLED' },
  { index: '03', title: 'Decision fusion', detail: 'Paired-data calibration and three-way verdicts are planned.', icon: 'grid', state: 'RESEARCH STAGE' },
  { index: '04', title: 'Evidence record', detail: 'JSON export and an unsigned printable summary are available.', icon: 'file', state: 'PARTIAL' },
];

const presets = [
  { id: 'real', number: '01', label: 'Authentic KYC session', note: 'Sample low visual signal' },
  { id: 'fake', number: '02', label: 'Face-swap attack', note: 'Sample high visual signal' },
  { id: 'suspicious', number: '03', label: 'Cloned voice mismatch', note: 'Concept preview; no paired audio result' },
];

export default function OverviewPage({ isDemo, health, onEnter, onPreset }) {
  const [pointer, setPointer] = useState({ x: 50, y: 50 });
  return <div className="command-overview">
    <section className="command-hero" onPointerMove={(event) => {
      const bounds = event.currentTarget.getBoundingClientRect();
      setPointer({ x: Math.round((event.clientX - bounds.left) / bounds.width * 100), y: Math.round((event.clientY - bounds.top) / bounds.height * 100) });
    }} style={{ '--pointer-x': `${pointer.x}%`, '--pointer-y': `${pointer.y}%` }}>
      <div className="hero-grid" aria-hidden="true" />
      <div className="hero-orb hero-orb-one" aria-hidden="true" />
      <div className="hero-orb hero-orb-two" aria-hidden="true" />
      <div className="hero-content">
        <span className="command-kicker"><span className="kicker-line" /> DEEP FORENSICS / INTELLIGENCE WORKSPACE</span>
        <h1>See beyond<br /><span>the surface.</span></h1>
        <p className="hero-lead">Multimodal deepfake screening for recorded Video-KYC sessions. Separate visual and acoustic findings, presented with clear evidence scope.</p>
        <div className="hero-actions"><Button onClick={onEnter} icon="scan">Open verification workstation</Button><span className="hero-mode">{isDemo ? 'DEMONSTRATION MODE' : health?.ready ? 'LOCAL MODELS READY' : 'LOCAL MODELS UNAVAILABLE'}</span></div>
        <div className="hero-proof"><div><strong>02</strong><span>MODEL CHANNELS</span></div><div><strong>01</strong><span>LOCAL WORKSTATION</span></div><div><strong>00</strong><span>CLOUD UPLOADS</span></div></div>
      </div>
      <div className="hero-console" aria-label="Analysis pipeline illustration">
        <div className="console-top"><span><span className="console-live-dot" /> SYSTEM ARCHITECTURE</span><span className="mono">DF / 001</span></div>
        <div className="console-video"><div className="console-scanline" /><span className="console-corner top-left"/><span className="console-corner top-right"/><span className="console-corner bottom-left"/><span className="console-corner bottom-right"/><Icon name="scan" size={78} /><span className="console-center-label">VISUAL STREAM</span></div>
        <div className="console-streams"><span><Icon name="scan" size={17} /> FACE FRAMES <b>→</b> VISUAL SCORE</span><span><Icon name="audio" size={17} /> AUDIO TRACK <b>→</b> SPOOF SCORE</span></div>
        <p>Illustrative workflow · live results appear after an actual upload.</p>
      </div>
    </section>
    <section className="overview-strip" aria-label="Current capabilities"><span><Icon name="lock" size={16} />LOCAL PROCESSING</span><span><Icon name="shield" size={16} />TEMPORARY UPLOAD CLEANUP</span><span><Icon name="file" size={16} />EXPORTABLE SUMMARY</span><span><Icon name="warning" size={16} />RESEARCH PROTOTYPE</span></section>
    <section className="overview-section"><div className="overview-section-head"><div><span className="command-kicker">WORKFLOW / 01</span><h2>One video. Two independent signals.</h2><p>Start a real analysis in the connected app, or explore clearly labeled sample states in demo mode.</p></div><Button variant="secondary" onClick={onEnter} icon="arrow">Go to workstation</Button></div><div className="preset-grid">{presets.map((item) => <button key={item.id} className="preset-card" onClick={() => onPreset(item.id)}><span className="preset-number">{item.number} / {isDemo ? 'DEMO PRESET' : 'RESEARCH SCENARIO'}</span><span className="preset-icon"><Icon name={item.id === 'real' ? 'shield' : item.id === 'fake' ? 'scan' : 'audio'} size={27} /></span><strong>{item.label}</strong><small>{item.note}</small><span className="preset-action">{isDemo ? 'OPEN SAMPLE SETUP' : 'OPEN WORKSTATION'} <Icon name="arrow" size={16} /></span></button>)}</div></section>
    <section className="overview-section"><div className="overview-section-head"><div><span className="command-kicker">PLATFORM / 02</span><h2>Designed for careful review.</h2><p>Current capabilities and planned research modules stay visibly distinct.</p></div></div><div className="architecture-grid">{modules.map((item) => <article className="architecture-card" key={item.index}><div className="architecture-top"><span>{item.index} / MODULE</span><Icon name={item.icon} size={21} /></div><h3>{item.title}</h3><p>{item.detail}</p><span className="architecture-state">{item.state}</span></article>)}</div></section>
  </div>;
}
