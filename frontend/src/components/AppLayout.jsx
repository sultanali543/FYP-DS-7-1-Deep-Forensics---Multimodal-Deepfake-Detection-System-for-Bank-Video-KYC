import Icon from './Icon.jsx';
import { Badge } from './UI.jsx';

export default function AppLayout({ children, view, isDemo, historyCount, busy, onNavigate, onHelp }) {
  const active = view === 'history' ? 'history' : 'upload';
  return <div className="app-shell">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <aside className="sidebar">
      <a className="brand" href="#" onClick={(event) => { event.preventDefault(); if (!busy) onNavigate('upload'); }} aria-label="Deep Forensics home"><span className="brand-symbol"><Icon name="shield" size={25} /></span><span>Deep Forensics<small>VERIFICATION WORKSPACE</small></span></a>
      <div className="workspace-label"><span className="workspace-avatar">DF</span><div>Research workspace<small>Local development</small></div><Icon name="lock" size={14} /></div>
      <p className="nav-caption">WORKSPACE</p>
      <nav aria-label="Main navigation">
        <button className={`nav-item ${active === 'upload' ? 'active' : ''}`} disabled={busy} onClick={() => onNavigate('upload')} aria-current={active === 'upload' ? 'page' : undefined}><Icon name="scan" size={19} />New analysis<Icon name="plus" size={16} /></button>
        <button className={`nav-item ${active === 'history' ? 'active' : ''}`} disabled={busy} onClick={() => onNavigate('history')} aria-current={active === 'history' ? 'page' : undefined}><Icon name="history" size={19} />Recent sessions<span className="nav-count">{historyCount}</span></button>
      </nav>
      <div className="sidebar-bottom"><div className="prototype-card"><span className="prototype-orbit"><Icon name="shield" size={24} /></span><h3>Built for careful review.</h3><p>Visual findings, clear scope, and an evidence record in one workspace.</p><span className="prototype-version">RESEARCH PROTOTYPE <span>v0.1</span></span></div><button className="help-button" onClick={onHelp}><Icon name="help" size={18} />Project & workflow guide<Icon name="external" size={14} /></button><div className="sidebar-user"><span className="user-avatar">DF</span><div>Project team<small>Deep Forensics · FYP</small></div><span className="online-dot" /></div></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><Icon name="grid" size={16} /><span>Workspace</span><Icon name="chevron" size={12} /><strong>{view === 'history' ? 'Recent sessions' : view === 'results' ? 'Analysis results' : view === 'processing' ? 'Processing' : 'New analysis'}</strong></div><div className="topbar-actions"><Badge tone={isDemo ? 'amber' : 'success'} dot>{isDemo ? 'Demo mode' : 'Live API'}</Badge><span className="topbar-divider"/><button className="icon-button" onClick={onHelp} aria-label="Open project guide"><Icon name="help" size={19} /></button><span className="top-avatar">DF</span></div></header>
      <main id="main-content" tabIndex={-1}>{children}</main>
      <footer className="app-footer"><span>Deep Forensics <span className="footer-dot">·</span> Multimodal verification research</span><span><span className="status-dot" />{isDemo ? 'Local demo service' : 'Backend API configured'}</span></footer>
    </div>
  </div>;
}
