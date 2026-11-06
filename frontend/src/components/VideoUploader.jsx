import { useEffect, useRef, useState } from 'react';
import Icon from './Icon.jsx';
import { Button } from './UI.jsx';
import { formatSize, formatDuration } from '../lib/utils.js';

export default function VideoUploader({ file, url, source, error, ready, isDemo = true, onSelect, onReady, onInvalid, onRemove }) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const dragDepth = useRef(0);
  useEffect(() => {
    if (!file || ready || error || !url) return;
    const timeout = setTimeout(() => onInvalid('The video preview could not load. Try another MP4 encoded for browser playback.'), 12000);
    return () => clearTimeout(timeout);
  }, [file, url, ready, error, onInvalid]);

  function receiveFiles(files) {
    if (files.length > 1) { onInvalid('Choose one video at a time.'); return; }
    if (files[0]) onSelect(files[0]);
  }

  return <div className="upload-body">
    <input ref={input} id="video-file" className="visually-hidden" tabIndex={-1} type="file" accept="video/mp4,.mp4" aria-label="Choose an MP4 verification video" onChange={(event) => { receiveFiles(event.target.files); event.target.value = ''; }} />
    {file && url ? <div className="selected-video"><div className="video-preview"><video key={url} src={url} controls playsInline preload="metadata" onLoadedMetadata={(event) => { const video = event.currentTarget; if (!Number.isFinite(video.duration) || video.duration <= 0) onInvalid('This video has no readable duration. Choose another MP4.'); else onReady({ duration: video.duration, width: video.videoWidth, height: video.videoHeight }); }} onError={() => onInvalid('This video cannot be played in your browser. Try an MP4 with H.264 video encoding.')} /><span className="preview-label">SOURCE VIDEO</span></div><div className="selected-file"><span className="file-symbol"><Icon name="video" size={21} /></span><div className="file-description"><strong title={file.name}>{file.name}</strong><span>{formatSize(file.size)} <span>·</span> {ready ? formatDuration(source?.duration) : error ? 'Preview unavailable' : 'Loading preview…'}</span></div><button className="icon-button" onClick={onRemove} aria-label="Remove selected video"><Icon name="close" size={18} /></button></div><button className="text-button replace-button" onClick={() => input.current.click()}>Choose a different video<Icon name="refresh" size={14} /></button></div> : <div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragEnter={(event) => { event.preventDefault(); dragDepth.current += 1; setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => { event.preventDefault(); dragDepth.current -= 1; if (dragDepth.current <= 0) setDragging(false); }} onDrop={(event) => { event.preventDefault(); dragDepth.current = 0; setDragging(false); receiveFiles(event.dataTransfer.files); }}><div className="upload-orbit"><span/><span/><span className="upload-icon"><Icon name="upload" size={29} /></span></div><h3>{dragging ? 'Drop your video here' : 'Drop a verification video here'}</h3><p>or choose a file from your computer</p><Button variant="secondary" icon="plus" onClick={() => input.current.click()}>Choose video</Button><div className="upload-constraints"><span>MP4 format</span><span>Up to 50 MB</span><span>One video at a time</span></div></div>}
    {error && <div className="field-error" role="alert"><Icon name="warning" size={16} /><span>{error}</span></div>}
    <p className="upload-privacy"><Icon name="lock" size={14} />{isDemo ? 'Videos stay in this browser in Demo mode.' : 'Analysis runs on your laptop. The backend deletes its copy afterward; your original stays untouched.'}</p>
  </div>;
}
