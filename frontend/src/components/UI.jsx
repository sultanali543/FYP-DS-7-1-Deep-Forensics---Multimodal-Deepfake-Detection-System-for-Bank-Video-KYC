import { useEffect, useRef } from 'react';
import Icon from './Icon.jsx';

export function Button({ children, icon, variant = 'primary', className = '', ...props }) {
  return <button type="button" className={`button button-${variant} ${className}`} {...props}>{icon && <Icon name={icon} size={17} />}{children}</button>;
}

export function Badge({ children, tone = 'neutral', dot = false }) {
  return <span className={`badge badge-${tone}`}>{dot && <span className="status-dot" />}{children}</span>;
}

export function VerdictBadge({ verdict, status }) {
  if (status === 'failed') return <Badge tone="danger">Processing failed</Badge>;
  if (status === 'insufficient_evidence') return <Badge tone="warning">Insufficient evidence</Badge>;
  const tones = { REAL: 'success', SUSPICIOUS: 'warning', FAKE: 'danger' };
  return <Badge tone={tones[verdict] || 'neutral'} dot>{verdict || 'Unavailable'}</Badge>;
}

export function PageHeading({ eyebrow, title, children, action }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{children && <p className="page-description">{children}</p>}</div>{action && <div className="heading-action">{action}</div>}</div>;
}

export function Notice({ children, tone = 'info', icon = 'info' }) {
  return <div className={`notice notice-${tone}`} role={tone === 'danger' ? 'alert' : 'note'}><Icon name={icon} size={18} /><div>{children}</div></div>;
}

export function Modal({ title, children, onClose, footer }) {
  const dialog = useRef(null);
  useEffect(() => {
    dialog.current.showModal();
    const element = dialog.current;
    return () => element.close();
  }, []);
  return <dialog ref={dialog} className="modal" onCancel={(event) => { event.preventDefault(); onClose(); }} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}><div className="modal-header"><h2>{title}</h2><button className="icon-button" type="button" aria-label="Close dialog" onClick={onClose}><Icon name="close" /></button></div><div className="modal-body">{children}</div>{footer && <div className="modal-footer">{footer}</div>}</dialog>;
}
