import { STAGES, makeMockResult, SCENARIOS } from '../mocks/analyses.js';
import { validateResult } from '../lib/utils.js';

export function createAnalysisService({ useMocks = true, baseUrl = 'http://127.0.0.1:8000', fetcher = globalThis.fetch, now = () => Date.now(), stageDuration = 950 } = {}) {
  const jobs = new Map();
  const api = baseUrl.replace(/\/+$/, '');
  const jobPath = (id) => `${api}/api/analyses/${encodeURIComponent(id)}`;

  async function request(url, options = {}) {
    let response;
    try { response = await fetcher(url, options); }
    catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new Error('The analysis server is unavailable. Check that the backend is running and try again.');
    }
    if (!response.ok) {
      let message = `The server could not complete the request (${response.status}).`;
      try { const payload = await response.json(); if (typeof payload.detail === 'string') message = payload.detail; } catch { /* Keep the readable status message. */ }
      throw new Error(message);
    }
    return response;
  }

  return {
    isDemo: useMocks,
    async getHealth({ signal } = {}) {
      const response = await request(`${api}/api/health`, { signal });
      const health = await response.json();
      if (health.service !== 'deep-forensics' || typeof health.ready !== 'boolean') throw new Error('This server is not the Deep Forensics backend.');
      return health;
    },
    async createAnalysis(file, { scenario = 'fake', source, signal } = {}) {
      signal?.throwIfAborted();
      if (useMocks) {
        if (!SCENARIOS.some((item) => item.id === scenario)) throw new Error('Choose a valid demonstration scenario.');
        const id = `DF-${globalThis.crypto.randomUUID().slice(0, 8).toUpperCase()}`;
        jobs.set(id, { id, scenario, source, started: now(), created_at: new Date(now()).toISOString() });
        return { id, status: 'queued' };
      }
      if (!file) throw new Error('Select a video before starting a live analysis.');
      const body = new FormData();
      body.append('file', file);
      const response = await request(`${api}/api/analyses`, { method: 'POST', body, signal });
      const result = await response.json();
      if (typeof result.id !== 'string' || !result.id) throw new Error('The server did not return an analysis ID.');
      return result;
    },
    async getAnalysis(id, { signal } = {}) {
      signal?.throwIfAborted();
      if (useMocks) {
        const job = jobs.get(id);
        if (!job) throw new Error('This demonstration session is no longer available. Start another analysis.');
        const index = Math.floor(Math.max(0, now() - job.started) / stageDuration);
        if ((job.scenario === 'failure' && index >= 3) || index >= STAGES.length) return makeMockResult(job);
        return { id, mode: 'demo', scope: 'visual_only', status: index === 0 ? 'queued' : 'running', stage: STAGES[Math.min(index, STAGES.length - 1)].id };
      }
      const response = await request(jobPath(id), { signal });
      const result = await response.json();
      if (result.id !== id || !['queued', 'running', 'complete', 'failed', 'insufficient_evidence'].includes(result.status)) throw new Error('The server returned an invalid analysis status.');
      return validateResult({ ...result, mode: 'live' });
    },
    releaseAnalysis(id) { jobs.delete(id); },
    async downloadReport(id, { signal } = {}) {
      if (useMocks) throw new Error('Use the printable sample report in Demo mode.');
      const response = await request(`${jobPath(id)}/report`, { signal });
      return response.blob();
    },
  };
}

const env = import.meta.env ?? {};
export function serviceConfig(environment) {
  // START_APP builds in live mode and serves the UI and API on the same origin.
  return {
    useMocks: environment.MODE === 'live' ? false : environment.VITE_USE_MOCKS !== 'false',
    baseUrl: environment.MODE === 'live' ? '/' : environment.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  };
}
export const analysisService = createAnalysisService(serviceConfig(env));
