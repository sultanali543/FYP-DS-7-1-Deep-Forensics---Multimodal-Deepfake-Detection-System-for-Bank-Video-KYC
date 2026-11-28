import test from 'node:test';
import assert from 'node:assert/strict';
import { runBatch } from '../src/lib/batchQueue.js';

test('batch keeps two jobs in flight and preserves each real result', async () => {
  const items = [1, 2, 3, 4].map((id) => ({ id, file: { name: `${id}.mp4`, size: 100 } }));
  const updates = new Map();
  const results = [];
  let active = 0;
  let peak = 0;
  const service = {
    async createAnalysis(file) { active++; peak = Math.max(peak, active); return { id: file.name }; },
    async getAnalysis(id) { await new Promise((resolve) => setTimeout(resolve, 5)); active--; return { id, status: 'complete', visual: { score: 0.2 } }; },
    releaseAnalysis() {},
  };
  await runBatch(items, { service, onUpdate: (id, patch) => updates.set(id, { ...updates.get(id), ...patch }), onResult: (result) => results.push(result), pollDelay: 1 });
  assert.equal(peak, 2);
  assert.equal(results.length, 4);
  assert.deepEqual([...updates.values()].map((row) => row.status), ['complete', 'complete', 'complete', 'complete']);
  assert.equal(results[0].source.kind, 'upload');
});

test('one failed upload does not stop the remaining videos', async () => {
  const statuses = new Map();
  const service = {
    async createAnalysis(file) { if (file.name === 'bad.mp4') throw new Error('Upload rejected'); return { id: file.name }; },
    async getAnalysis(id) { return { id, status: 'insufficient_evidence' }; },
    releaseAnalysis() {},
  };
  await runBatch(['bad.mp4', 'good.mp4'].map((name) => ({ id: name, file: { name, size: 100 } })), { service, onUpdate: (id, patch) => statuses.set(id, { ...statuses.get(id), ...patch }), onResult() {} });
  assert.equal(statuses.get('bad.mp4').status, 'failed');
  assert.equal(statuses.get('good.mp4').status, 'insufficient_evidence');
});

test('queue-full response waits and retries without inventing a result', async () => {
  let attempts = 0;
  const updates = [];
  const service = {
    async createAnalysis() { if (++attempts === 1) throw Object.assign(new Error('Queue full'), { status: 429 }); return { id: 'job' }; },
    async getAnalysis() { return { id: 'job', status: 'complete' }; },
    releaseAnalysis() {},
  };
  await runBatch([{ id: 1, file: { name: 'clip.mp4', size: 100 } }], { service, onUpdate: (_id, patch) => updates.push(patch.status), onResult() {}, retryDelay: 1 });
  assert.equal(attempts, 2);
  assert.ok(updates.includes('waiting'));
  assert.equal(updates.at(-1), 'complete');
});
