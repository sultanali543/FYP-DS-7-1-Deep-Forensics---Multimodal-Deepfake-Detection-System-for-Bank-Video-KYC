import test from 'node:test';
import assert from 'node:assert/strict';
import { createAnalysisService, serviceConfig } from '../src/services/analysisService.js';
import { validateVideo, validateLiveMetadata, validateResult, readHistory, writeHistory, MAX_FILE_SIZE } from '../src/lib/utils.js';

test('connected build always uses the same-origin live backend; demos remain explicit', () => {
  assert.deepEqual(serviceConfig({ MODE: 'live', VITE_USE_MOCKS: 'true', VITE_API_BASE_URL: 'http://wrong' }), { useMocks: false, baseUrl: '/' });
  assert.equal(serviceConfig({}).useMocks, true);
  assert.equal(serviceConfig({ VITE_USE_MOCKS: 'false' }).useMocks, false);
});

test('local backend readiness is checked and unknown servers are rejected', async () => {
  const service = createAnalysisService({ useMocks: false, baseUrl: '/', fetcher: async (url) => {
    assert.equal(url, '/api/health');
    return Response.json({ service: 'deep-forensics', ready: true, model_version: 'test' });
  } });
  assert.equal((await service.getHealth()).model_version, 'test');
  const wrong = createAnalysisService({ fetcher: async () => Response.json({ ready: true }) });
  await assert.rejects(wrong.getHealth(), /not the Deep Forensics backend/);
});

test('CPU video duration and resolution limits are explained before upload', () => {
  assert.equal(validateLiveMetadata({ duration: 60, width: 1920, height: 1080 }), null);
  assert.match(validateLiveMetadata({ duration: 61, width: 640, height: 480 }), /60 seconds/);
  assert.match(validateLiveMetadata({ duration: 5, width: 7680, height: 4320 }), /4K/);
});

test('live insufficient evidence and model errors retain their actual status without a verdict', async () => {
  for (const status of ['insufficient_evidence', 'failed']) {
    const service = createAnalysisService({ useMocks: false, fetcher: async () => Response.json({ id: 'job', scope: 'visual_only', status, reason: 'No usable evidence', upload_deleted: true }) });
    const result = await service.getAnalysis('job');
    assert.equal(result.status, status);
    assert.equal(result.visual, undefined);
    assert.equal(result.upload_deleted, true);
  }
});

const source = { kind: 'example', name: 'Example session', size: null, duration: null };

test('upload validation rejects unusable inputs and accepts browser MP4 metadata', () => {
  assert.ok(validateVideo(null));
  assert.ok(validateVideo({ name: 'empty.mp4', size: 0, type: 'video/mp4' }));
  assert.ok(validateVideo({ name: 'large.mp4', size: MAX_FILE_SIZE + 1, type: 'video/mp4' }));
  assert.ok(validateVideo({ name: 'document.mp4', size: 50, type: 'application/pdf' }));
  assert.equal(validateVideo({ name: 'session.MP4', size: 1000, type: '' }), null);
});

test('demo advances through stages and preserves unavailable audio and evidence', async () => {
  let elapsed = 0;
  const service = createAnalysisService({ now: () => elapsed, stageDuration: 100 });
  const job = await service.createAnalysis(null, { source, scenario: 'fake' });
  assert.equal((await service.getAnalysis(job.id)).status, 'queued');
  elapsed = 250;
  assert.equal((await service.getAnalysis(job.id)).stage, 'extracting');
  elapsed = 500;
  const result = await service.getAnalysis(job.id);
  assert.equal(result.visual.verdict, 'FAKE');
  assert.equal(result.mode, 'demo');
  assert.equal(result.audio.score, null);
  assert.equal(result.audio.status, 'not_implemented');
  assert.equal(result.sha256, null);
  assert.deepEqual(result.evidence, []);
  assert.equal(validateResult(result), result);
});

test('demo scenarios do not derive predictions from an uploaded filename', async () => {
  const service = createAnalysisService({ stageDuration: 0.001 });
  const first = await service.createAnalysis({ name: 'real.mp4' }, { source, scenario: 'fake' });
  const second = await service.createAnalysis({ name: 'fake.mp4' }, { source, scenario: 'fake' });
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.deepEqual((await service.getAnalysis(first.id)).visual, (await service.getAnalysis(second.id)).visual);
});

test('insufficient evidence never receives a REAL verdict', async () => {
  let elapsed = 0;
  const service = createAnalysisService({ now: () => elapsed, stageDuration: 1 });
  const job = await service.createAnalysis(null, { source, scenario: 'no-face' });
  elapsed = 10;
  const result = await service.getAnalysis(job.id);
  assert.equal(result.status, 'insufficient_evidence');
  assert.equal(result.visual, undefined);
  assert.ok(result.reason);
});

test('a failed demo job terminates and a released job cannot keep polling', async () => {
  let elapsed = 0;
  const service = createAnalysisService({ now: () => elapsed, stageDuration: 1 });
  const job = await service.createAnalysis(null, { source, scenario: 'failure' });
  elapsed = 3;
  assert.equal((await service.getAnalysis(job.id)).status, 'failed');
  service.releaseAnalysis(job.id);
  await assert.rejects(service.getAnalysis(job.id), /no longer available/);
});

test('live API failure remains a failure without a mock result', async () => {
  const service = createAnalysisService({ useMocks: false, fetcher: async () => { throw new TypeError('Failed to fetch'); } });
  await assert.rejects(service.createAnalysis(new Blob(['video']), { source }), /server is unavailable/);
});

test('live requests upload FormData and validate the returned analysis', async () => {
  const requests = [];
  const service = createAnalysisService({ useMocks: false, baseUrl: 'http://localhost:8000/', fetcher: async (url, options) => {
    requests.push({ url, options });
    return Response.json(options?.method === 'POST' ? { id: 'job/1', status: 'queued' } : { id: 'job/1', scope: 'visual_only', status: 'complete', visual: { status: 'complete', score: 0.2, verdict: 'REAL' }, audio: { status: 'not_implemented', score: null } });
  } });
  const job = await service.createAnalysis(new Blob(['video']), { source });
  const result = await service.getAnalysis(job.id);
  assert.ok(requests[0].options.body instanceof FormData);
  assert.equal(requests[0].options.headers, undefined);
  assert.equal(requests[1].url, 'http://localhost:8000/api/analyses/job%2F1');
  assert.equal(result.mode, 'live');
});

test('malformed completed API results are rejected instead of showing a safe verdict', async () => {
  const service = createAnalysisService({ useMocks: false, fetcher: async () => Response.json({ id: 'broken', scope: 'visual_only', status: 'complete', visual: { status: 'complete', score: 0, verdict: 'APPROVED' } }) });
  await assert.rejects(service.getAnalysis('broken'), /incomplete visual result/);
});

test('aborted requests preserve AbortError for polling cleanup', async () => {
  const controller = new AbortController(); controller.abort();
  const service = createAnalysisService();
  await assert.rejects(service.createAnalysis(null, { source, signal: controller.signal }), { name: 'AbortError' });
});

test('broken browser history is ignored and storage denial does not crash the app', () => {
  assert.deepEqual(readHistory({ getItem: () => '{broken' }), []);
  assert.deepEqual(readHistory({ getItem: () => JSON.stringify([{ id: 'invalid' }]) }), []);
  assert.equal(writeHistory({ setItem: () => { throw new Error('denied'); } }, []), false);
});
