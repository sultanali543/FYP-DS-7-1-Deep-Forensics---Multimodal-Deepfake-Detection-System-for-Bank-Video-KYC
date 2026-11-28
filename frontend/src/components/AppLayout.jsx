import Icon from './Icon.jsx';

export default function AppLayout({ children, view, isDemo, health, historyCount, busy, onNavigate, onHelp }) {
  const section = view === 'overview' ? 'overview' : view === 'history' ? 'history' : 'upload';
  const status = isDemo ? 'DEMO / NO INFERENCE' : health?.ready ? 'LOCAL MODELS READY' : 'LOCAL MODELS UNAVAILABLE';
  return <div className="app-shell command-shell">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <aside className="sidebar">
      <button className="brand" onClick={() => { if (!busy) onNavigate('overview'); }} aria-label="Deep Forensics overview"><span className="brand-symbol"><Icon name="shield" size={24} /></span><span>DEEP<span className="brand-accent">FORENSICS</span><small>VERIFICATION INTELLIGENCE</small></span></button>
      <div className="workspace-label"><span className="workspace-avatar"><Icon name="lock" size={16} /></span><div>SECURE WORKSPACE<small>{isDemo ? 'Browser demonstration' : 'Local workstation'}</small></div><span className="workspace-pin" /></div>
      <p className="nav-caption">OPERATIONS</p>
      <nav aria-label="Main navigation">
        <button className={`nav-item ${section === 'overview' ? 'active' : ''}`} disabled={busy} onClick={() => onNavigate('overview')} aria-current={section === 'overview' ? 'page' : undefined}><Icon name="grid" size={18} />Overview</button>
        <button className={`nav-item ${section === 'upload' ? 'active' : ''}`} disabled={busy} onClick={() => onNavigate('upload')} aria-current={section === 'upload' ? 'page' : undefined}><Icon name="scan" size={18} />Live workstation<span className="nav-arrow">↗</span></button>
        <button className={`nav-item ${section === 'history' ? 'active' : ''}`} disabled={busy} onClick={() => onNavigate('history')} aria-current={section === 'history' ? 'page' : undefined}><Icon name="history" size={18} />Recent sessions<span className="nav-count">{historyCount}</span></button>
      </nav>
      <div className="sidebar-bottom"><div className="prototype-card"><span className="prototype-orbit"><Icon name="shield" size={24} /></span><span className="prototype-kicker">SYSTEM NOTICE</span><h3>Evidence before certainty.</h3><p>Model scores are research signals. Human review remains essential for high-stakes decisions.</p><span className="prototype-version">RESEARCH PROTOTYPE <span>v0.1</span></span></div><button className="help-button" onClick={onHelp}><Icon name="help" size={18} />Project & workflow guide<Icon name="arrow" size={15} /></button></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="topbar-location"><span className="topbar-mark">DF</span><div><span className="topbar-overline">DEEP FORENSICS / WORKSPACE</span><strong>{view === 'overview' ? 'Command overview' : view === 'processing' ? 'Analysis in progress' : view === 'results' ? 'Session findings' : view === 'history' ? 'Recent sessions' : 'Verification workstation'}</strong></div></div><div className="topbar-actions"><span className={`telemetry-status ${health?.ready && !isDemo ? 'connected' : ''}`}><span />{status}</span><button className="icon-button" onClick={onHelp} aria-label="Open project guide"><Icon name="help" size={19} /></button></div></header>
      <div className="telemetry-bar" aria-label="Local system status"><span><i />DEPLOYMENT: {isDemo ? 'BROWSER DEMO' : 'LOCAL HOST'}</span><span><i />DATA: {isDemo ? 'NO SERVER UPLOAD' : 'LOCAL WORKSTATION'}</span><span><i />GPU: NOT REPORTED</span><span><i />QUEUE: {busy ? 'ANALYSIS ACTIVE' : 'SINGLE JOB'}</span></div>
      <main id="main-content" tabIndex={-1}>{children}</main>
      <footer className="app-footer"><span>© DEEP FORENSICS <span className="footer-dot">/</span> MULTIMODAL VERIFICATION RESEARCH</span><span>{isDemo ? 'DEMO / SAMPLE DATA' : 'LOCAL / EXPERIMENTAL MODELS'}</span></footer>
    </div>
  </div>;
}
