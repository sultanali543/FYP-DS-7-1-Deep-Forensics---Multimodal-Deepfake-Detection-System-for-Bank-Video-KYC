# Deep Forensics Git workflow

Use one feature branch for each meaningful task. The main branch holds the integrated project; ongoing implementation belongs on a task branch.

| Branch | Intended work |
| --- | --- |
| feature/frontend-demo | Existing sample frontend and its setup instructions |
| feature/frontend-polish | Later interface improvements |
| feature/visual-baseline | Data manifests, preprocessing, training, and evaluation code |
| feature/backend-api | FastAPI job handling and real inference |
| feature/frontend-api | Connecting the React interface to actual API results |
| feature/audio-baseline | Later acoustic spoof detection experiments |
| fix/descriptive-name | A focused bug fix |

## Each work session

1. Inspect Git status and confirm the appropriate branch.
2. Preserve existing manual edits and identify which changes belong to the task.
3. Implement a coherent milestone and run the relevant checks.
4. Review and stage only intended source and documentation files.
5. Commit with a descriptive message, such as `feat: connect visual analysis results`.
6. Push the task branch after the repository and write access have been confirmed.
7. Report the branch, commit, checks, and remote upload status.

Merge into main only after the user requests integration. Separate commits provide useful checkpoints within a branch; each individual edit does not need a new branch.

## GitHub connection

The project needs an agreed GitHub repository URL and authenticated write access. A new private repository is a suitable default for this research prototype. If an existing repository already contains work, inspect its history and branches before importing this local project.

The GitHub app connection and local Git authentication serve different parts of the workflow. Confirm the repository and push result rather than assuming that signing into one automatically configures the other.

Git author identity is already configured on this computer. Continue using the existing identity unless the user changes it. Do not ask the user to paste account passwords or access tokens into the chat.

## Storage and committed files

Track source, notebooks with reviewed outputs, manifests, small configuration files, dependency lockfiles, tests, and setup documentation. Review notebook outputs before committing because they can embed large images or private data.

The root .gitignore excludes datasets, uploaded media, face crops, model weights, dependency folders, builds, and local secrets. It keeps .env.example available for versioning. Academic Word reference files remain local.

Model training can run in Colab, with important artifacts backed up to the selected cloud storage. Git should hold experiment code and reproducibility metadata rather than the dataset itself.
