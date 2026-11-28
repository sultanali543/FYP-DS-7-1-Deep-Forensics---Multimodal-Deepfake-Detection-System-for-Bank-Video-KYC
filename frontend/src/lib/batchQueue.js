const terminal = new Set(['complete', 'failed', 'insufficient_evidence']);

function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(new DOMException('Cancelled', 'AbortError')); return; }
    const timer = setTimeout(done, ms);
    function done() { signal?.removeEventListener('abort', cancel); resolve(); }
    function cancel() { clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')); }
    signal?.addEventListener('abort', cancel, { once: true });
  });
}

export async function runBatch(items, { service, scenario, onUpdate, onResult, signal, concurrency = 2, pollDelay = 1500, retryDelay = 2000 }) {
  let next = 0;
  const workers = Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    while (next < items.length && !signal?.aborted) {
      const item = items[next++];
      const source = { kind: 'upload', name: item.file.name, size: item.file.size, duration: null };
      let jobId;
      try {
        onUpdate(item.id, { status: 'uploading', error: null });
        let created;
        const queueDeadline = Date.now() + 180000;
        while (!created) {
          try { created = await service.createAnalysis(item.file, { scenario, source, signal }); break; }
          catch (error) {
            if (error.status !== 429 || Date.now() >= queueDeadline) throw error;
            onUpdate(item.id, { status: 'waiting', error: 'Backend queue full; waiting for a free slot.' });
            await wait(retryDelay, signal);
            onUpdate(item.id, { status: 'uploading', error: null });
          }
        }
        jobId = created.id;
        onUpdate(item.id, { status: 'queued', jobId });
        while (!signal?.aborted) {
          const data = await service.getAnalysis(jobId, { signal });
          if (terminal.has(data.status)) {
            const result = { ...data, source: data.source || source, created_at: data.created_at || new Date().toISOString() };
            onUpdate(item.id, { status: data.status, result });
            onResult(result);
            break;
          }
          onUpdate(item.id, { status: data.status, stage: data.stage });
          await wait(pollDelay, signal);
        }
      } catch (error) {
        if (error.name === 'AbortError') return;
        onUpdate(item.id, { status: 'failed', error: error.message || 'Analysis failed.' });
      } finally {
        if (jobId) service.releaseAnalysis(jobId);
      }
    }
  });
  await Promise.all(workers);
}
