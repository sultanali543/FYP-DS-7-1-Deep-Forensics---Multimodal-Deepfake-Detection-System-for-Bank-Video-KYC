import { Notice } from './UI.jsx';

export default function WorkflowGuide({ isDemo, audioReady = false }) {
  return <div className="guide-content">
    <p className="eyebrow">DEEP FORENSICS / RESEARCH PROTOTYPE</p>
    <h3>{isDemo ? 'Explore the demonstration workflow.' : 'Run the trained models on your laptop.'}</h3>
    <ol>
      <li><strong>Choose a video.</strong><span>{isDemo ? 'Use an MP4 or try a fixed example.' : 'Use an MP4 up to 50 MB and 60 seconds, with one clearly visible face. 1080p is recommended.'}</span></li>
      <li><strong>{isDemo ? 'Choose a demo scenario.' : 'Start analysis.'}</strong><span>{isDemo ? 'The scenario determines the sample result.' : 'The local Python backend checks face frames and, when available, the audio track using saved models.'}</span></li>
      <li><strong>Review and export.</strong><span>Read the available model results, inspect frame coverage, export JSON, or print an unsigned summary.</span></li>
    </ol>
    <Notice>{isDemo ? 'Demo scores are fixed examples. Open START_APP.cmd to run the trained model.' : 'Experimental baseline: false alarms and missed fakes are possible. REAL does not verify identity, and FAKE is a model prediction, not proof of manipulation.'}</Notice>
    <p>{isDemo ? 'Audio detection is unavailable in demo mode.' : audioReady ? 'Audio detection is enabled for videos with a usable audio track.' : 'The audio checkpoint is not installed here.'} Grad-CAM, video fingerprints, and digital signatures are not implemented.</p>
    {!isDemo && <p className="guide-small">The backend deletes its uploaded copy after analysis, including failed attempts. Your original file stays on your computer. Results remain in server memory until it closes and in this browser tab’s recent sessions. Keep the app window open while using it.</p>}
  </div>;
}
