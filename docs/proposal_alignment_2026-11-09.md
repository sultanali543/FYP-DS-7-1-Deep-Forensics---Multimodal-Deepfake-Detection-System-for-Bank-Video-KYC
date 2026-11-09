# Proposal alignment and next milestones — 9 November 2026

Source reviewed: local `Template -  04 - Proposal  Plan.docx`, version 2.0 (20 October 2026). This checklist concerns the implemented software; it does not change the approved proposal or claim that a research target has already been met.

## Current position

The first **single-modality reference baselines** are trained and usable in the local app. The visual baseline is a frozen ResNet18 feature extractor with a trained logistic classifier on the 400-video DFDC sample. The audio baseline uses 128-band log-mel features with a trained histogram gradient boosting classifier on ASVspoof 2019 LA train/dev. These are legitimate, measured starting points, but they differ materially from the proposal's target backbones and the **multimodal baseline is not complete**: no calibrated fusion rule or paired audio-video benchmark has been evaluated.

| Proposal requirement | Current evidence | Status |
| --- | --- | --- |
| Responsive upload UI, FastAPI queue, local processing, scoped cleanup | `frontend/`, `backend/`; MP4 uploads run real models and temporary backend copies are deleted | Implemented locally |
| Visual: 10–15 FPS, RetinaFace, fine-tuned EfficientNet-B4/Inception, Grad-CAM | Up to 12 sampled frames per video, YuNet, frozen ResNet18 features plus logistic head; no Grad-CAM | Prototype only |
| Audio: 16 kHz, 128-band log-mel, pretrained spoof backbone | MP4 audio resampled to 16 kHz, 128-band log-mel features summarized for a CPU classifier; no pretrained spoof backbone | Prototype only |
| Three-way REAL / SUSPICIOUS / FAKE **combined** decision | Separate visual and audio predictions; no validated fusion output. Current prominent badge describes the visual channel | Missing |
| FakeAVCeleb paired four-category fusion benchmark | No FakeAVCeleb data or paired validation/test results | Missing |
| FF++ and larger DFDC visual robustness checks | 400-video DFDC sample only; no FF++ training/evaluation | Missing |
| Independent ASVspoof evaluation and channel robustness | 2019 LA train/dev only; audio scores are development-set model-selection metrics | Missing |
| FAR/FRR/EER, calibration, banking risk thresholds | Balanced accuracy/AUC and confusion matrices recorded; no complete banking operating-point study | Partial |
| SHA-256 hash of raw uploaded video, signed PDF, heatmaps | Browser print/JSON summary only; no upload hash, signature, or heatmaps | Missing |
| Containerized local GPU deployment | Local CPU app; no container or university GPU deployment | Missing |

The visual [held-out sample result](../ml/experiments/dfdc_sample_cpu_2026-11-06.md) was 91.1% accuracy on 79 analyzable videos, with **4 false alarms among 15 known-real videos**. A separate [stock-video diagnostic](../ml/experiments/external_video_44639_2026-11-06.md) also produced a high FAKE score, but the clip's true label is not independently certified. The audio [development result](../audio/experiments/asvspoof2019_la_cpu_2026-11-09.md) was 97.31% balanced accuracy after selecting the model and threshold on that same split. Neither number is a validated multimodal or bank Video-KYC performance figure.

## Meaning of a real video flagged FAKE

This is a possible **false alarm** (a genuine video flagged as manipulated). If the source is not independently authenticated, it remains an observed model disagreement rather than a confirmed error. The visual baseline's small sample and domain shift make false alarms plausible. The current score is an experimental classifier output, not a calibrated probability of forgery.

Do not raise or lower the existing threshold to make one known clip read REAL. Raising the FAKE threshold can reduce false alarms while increasing missed fakes, which is especially consequential in KYC. Preserve the existing checkpoint and test report. Collect an independent, labeled diagnostic set with real and fake examples; inspect face crops, occlusion, blur, compression, frame scores, and audio status. Fit any revised model and select thresholds using training/validation data only, then report a fresh held-out test set without retuning it.

With fake as the positive class, **false acceptance** means a fake is accepted as REAL; **false rejection/false alarm** means a genuine clip is blocked or sent to review. Both should be reported, along with coverage and the number of clips routed to human review. If SUSPICIOUS routes to review, it is not an automatic REAL acceptance.

## Proposed combined-decision design

The proposal says REAL requires both channels to look natural, SUSPICIOUS covers borderline scores and contradictions, and FAKE covers strong evidence of manipulation in either channel. Implement this as a transparent rule with separately versioned visual and audio scores, two validated risk bands per channel, and explicit missing-channel handling. A conservative **candidate** policy for evaluation is:

| Evidence | Candidate workflow outcome |
| --- | --- |
| Both channels available and below their low-risk bands | REAL / low observed manipulation signal; identity is still unverified |
| Scores disagree, either score is borderline, or evidence quality is weak | SUSPICIOUS → human review; never auto-accept |
| Strong manipulation signal under a validated high-specificity rule | FAKE → human review/block |
| Required visual or audio evidence unavailable | INSUFFICIENT EVIDENCE → retry or human review |

This is a specification for a future experiment, **not a deployed or calibrated final verdict**. The precise low/high thresholds and the meaning of “strong” must be selected on paired validation data, with explicit limits on fake acceptance and genuine false alarms. An isolated high visual score should not automatically become a definitive combined FAKE label while the current visual model has documented false alarms. At the same time, fake-video/real-audio and real-video/fake-audio cases must never be accepted as REAL. The official [FakeAVCeleb source](https://sites.google.com/view/fakeavcelebdash-lab/download) is the proposal's primary resource for these four combinations. Keep identities and source clips grouped across train, validation, and test.

## Ordered work

1. **Clarify the current UI and report.** Label the prominent badge as a visual-only finding, display the audio result separately, and state that no combined verdict has been calibrated. Preserve original scores and thresholds.
2. **Build a verified paired evaluation subset.** Obtain official FakeAVCeleb access and its labels, select manageable clips from all four audio/video combinations, and fix identity-disjoint train/validation/test membership before scoring. Record the dataset license and provenance. Do not tune on held-out test clips.
3. **Investigate the visual false alarms.** Collect a separate set of genuinely verified real clips and labeled fakes, including compression and lighting variation. Review preprocessing and per-frame behavior, then compare a stronger fine-tuned vision model on the university GPU. Keep the original CPU checkpoint as a baseline.
4. **Evaluate and strengthen audio.** Freeze the current model and score the official ASVspoof 2019/2021 evaluation partition. Report EER and class-specific errors; then test compressed or noisy audio. A pretrained voice-spoof backbone is a later comparison, not a property of the current model.
5. **Implement and calibrate fusion.** Use paired validation data to choose risk bands and rule precedence. Evaluate each FakeAVCeleb category and the combined REAL/SUSPICIOUS/FAKE decision on a fresh test split. Report false acceptance, false rejection, review rate, missing-channel rate, and confidence intervals.
6. **Add proposal deliverables.** Generate Grad-CAM from a suitable vision backbone, hash the raw upload before cleanup, and produce a signed PDF with model/data versions, scores, evidence references, and signature verification. Then package and test local container/GPU deployment.

Model changes and thresholds should be documented as new experiments and feature branches. Avoid claiming that a REAL model label authenticates a person or that an experimental FAKE score proves tampering.
