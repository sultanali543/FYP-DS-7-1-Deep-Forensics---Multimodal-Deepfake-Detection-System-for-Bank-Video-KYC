export const SCENARIOS = [
  { id: 'fake', label: 'High visual risk', verdict: 'FAKE', score: 0.86, description: 'Explore a sample result flagged for visual manipulation.' },
  { id: 'suspicious', label: 'Needs review', verdict: 'SUSPICIOUS', score: 0.48, description: 'Explore a sample result that needs human review.' },
  { id: 'real', label: 'Low visual risk', verdict: 'REAL', score: 0.12, description: 'Explore a sample result with a low visual manipulation score.' },
  { id: 'no-face', label: 'Insufficient evidence', description: 'Test the response when no usable face is available.' },
  { id: 'failure', label: 'Processing error', description: 'Test the failure message and retry flow.' },
];

export const STAGES = [
  { id: 'queued', label: 'Session queued', detail: 'Preparing the analysis workspace.' },
  { id: 'validating', label: 'Validate video', detail: 'Checking the input and session details.' },
  { id: 'extracting', label: 'Extract facial frames', detail: 'Preparing face regions for the visual pipeline.' },
  { id: 'analyzing', label: 'Run visual analysis', detail: 'Evaluating the visual manipulation signal.' },
  { id: 'reporting', label: 'Prepare findings', detail: 'Organizing results for review and reporting.' },
];

export function makeMockResult({ id, scenario, source, created_at }) {
  const fixture = SCENARIOS.find((item) => item.id === scenario);
  if (!fixture) throw new Error('Choose a valid demonstration scenario.');
  const base = {
    id, mode: 'demo', scope: 'visual_only', created_at, source,
    audio: { status: 'not_implemented', score: null },
    evidence: [], sha256: null, report_available: false,
  };
  if (scenario === 'failure') return { ...base, status: 'failed', stage: 'analyzing', error: 'The example processing worker could not finish this session. Retry or choose another demo scenario.' };
  if (scenario === 'no-face') return { ...base, status: 'insufficient_evidence', stage: 'complete', reason: 'No usable face was found in this sample scenario. Choose a clip with a clear, well-lit face and try again.' };
  return {
    ...base, status: 'complete', stage: 'complete',
    visual: { status: 'complete', verdict: fixture.verdict, score: fixture.score, model_version: null },
  };
}
