export const MAX_FILE_SIZE = 50 * 1024 * 1024;

export function validateLiveMetadata({ duration, width, height }) {
  if (!Number.isFinite(duration) || duration <= 0) return 'This video has no readable duration.';
  if (duration > 60) return 'Choose a clip up to 60 seconds for this CPU prototype.';
  if (width * height > 3840 * 2160 || Math.max(width, height) > 4096) return 'Choose a video at 4K resolution or smaller; 1080p is recommended.';
  return null;
}

export function validateVideo(file) {
  if (!file) return 'Choose an MP4 video to continue.';
  if (!file.size) return 'This file is empty. Choose another video.';
  if (file.size > MAX_FILE_SIZE) return 'This video exceeds the 50 MB prototype limit.';
  if (!/\.mp4$/i.test(file.name) || (file.type && !['video/mp4', 'application/mp4'].includes(file.type))) {
    return 'Choose an MP4 video. Other formats are not supported in this prototype.';
  }
  return null;
}

export function formatSize(size) {
  if (!Number.isFinite(size)) return 'Example record';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return 'No video attached';
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
}

export function formatDate(date) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(date));
}

export function scorePercent(score) {
  return Number.isFinite(score) ? `${Math.round(score * 100)}%` : 'Unavailable';
}

export function validateResult(result) {
  if (!result || typeof result.id !== 'string' || !result.id || !['demo', 'live'].includes(result.mode)) {
    throw new Error('The analysis service returned an invalid result.');
  }
  if (!['visual_only', 'multimodal'].includes(result.scope)) throw new Error('The analysis scope is missing.');
  if (result.status !== 'complete') return result;
  const visual = result.visual;
  if (!visual || visual.status !== 'complete' || !Number.isFinite(visual.score) || visual.score < 0 || visual.score > 1 || !['REAL', 'SUSPICIOUS', 'FAKE'].includes(visual.verdict)) {
    throw new Error('The analysis service returned an incomplete visual result.');
  }
  return result;
}

export function readHistory(storage) {
  try {
    const records = JSON.parse(storage.getItem('deep-forensics.history.v1') || '[]');
    return Array.isArray(records) ? records.filter((record) => {
      try { return ['complete', 'insufficient_evidence', 'failed'].includes(validateResult(record).status) && record.source && typeof record.source.name === 'string' && !Number.isNaN(Date.parse(record.created_at)); }
      catch { return false; }
    }).slice(0, 20) : [];
  } catch { return []; }
}

export function writeHistory(storage, records) {
  try { storage.setItem('deep-forensics.history.v1', JSON.stringify(records.slice(0, 20))); return true; }
  catch { return false; }
}
