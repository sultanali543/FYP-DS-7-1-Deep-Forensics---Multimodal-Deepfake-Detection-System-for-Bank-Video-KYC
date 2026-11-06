import { useState } from 'react';
import Icon from './Icon.jsx';
import { Badge, Modal } from './UI.jsx';

function EvidenceImage({ item, onOpen }) {
  const [failed, setFailed] = useState(false);
  return <button className="evidence-thumbnail" onClick={() => onOpen(item)} disabled={failed}>{failed ? <span className="image-failed">Image unavailable</span> : <img src={item.image_url} alt={item.caption || 'Analysis evidence frame'} onError={() => setFailed(true)} loading="lazy" />}<span>{item.caption || (item.kind === 'grad_cam' ? 'Model attribution' : 'Analyzed frame')}</span>{item.timestamp != null && <small>{Number(item.timestamp).toFixed(1)}s</small>}</button>;
}

export default function EvidenceGallery({ items = [] }) {
  const [selected, setSelected] = useState(null);
  const usable = Array.isArray(items) ? items.filter((item) => typeof item.image_url === 'string' && item.image_url) : [];
  return <section className="card evidence-card"><div className="card-heading"><div><Icon name="image" size={18} /><h2>Visual evidence</h2></div><Badge>{usable.length} images</Badge></div>{usable.length ? <><div className="evidence-gallery">{usable.map((item, index) => <EvidenceImage key={item.id || index} item={item} onOpen={setSelected} />)}</div><p className="evidence-caption">Attribution images show model attention; they do not prove exact manipulation boundaries.</p></> : <div className="empty-evidence"><span className="empty-icon"><Icon name="image" size={25} /></span><div><h3>Evidence images are not available.</h3><p>This version does not generate face-frame images or Grad-CAM overlays. Frame scores from live analyses are included in the JSON export.</p><span>Source previews are not forensic findings.</span></div></div>}{selected && <Modal title={selected.caption || 'Analysis evidence'} onClose={() => setSelected(null)}><img className="expanded-evidence" src={selected.image_url} alt={selected.caption || 'Analysis evidence frame'} /></Modal>}</section>;
}
