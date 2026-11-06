# Deep Forensics working instructions

## Git workflow

The user wants development work committed on separate feature branches.

- Inspect the current branch, working tree, remotes, and applicable repository instructions before changing code.
- Work on a descriptive task branch such as `feature/frontend-polish`, `feature/visual-baseline`, `feature/backend-api`, or `fix/upload-validation`.
- Reuse the current branch when continuing the same task. Start unrelated work from the agreed base branch after checking its state.
- Preserve the user's uncommitted work. Never discard it or overwrite unrelated changes when preparing a branch.
- Commit meaningful, completed milestones after appropriate verification. Stage only the intended files and inspect the staged diff.
- Use the configured Git author identity; do not invent a name or email address.
- During authorized project work, the user has requested commits on task branches. Push those task branches when the GitHub repository and write access have been confirmed.
- Keep `main` as the integration branch. Do not merge into it, push changes directly to it, force-push, rewrite shared history, or change branch protection unless the user requests that action. A new empty repository may require a small initial foundation commit before feature branches can be compared.
- Report the branch name, commit identifier, verification, and whether a push succeeded. Never describe local commits as uploaded before checking the push result.
- This workflow applies while actively handling a project request. It does not authorize unattended monitoring of manual edits outside the current task.

## Files to keep out of Git

- Honor the root and frontend .gitignore files.
- Keep datasets, uploaded videos, extracted face crops, model weights, dependency folders, generated builds, credentials, and local environment values out of commits.
- Keep the academic Word reference documents local. They contain student contact information and are not required to run the code.
- Commit .env.example, dependency manifests, lockfiles, source, tests, and project setup documentation when relevant.
- Keep large experiment artifacts in the chosen cloud storage and track their configuration or manifest references instead.

## Current project state

- The frontend is a React, JavaScript/JSX, CSS, and Vite application under frontend/.
- Run npm test and npm run build from frontend/ for relevant application changes.
- The default app uses clearly labeled demo fixtures. Preserve that distinction until real inference is connected.
- Audio analysis, trained visual inference, Grad-CAM generation, cryptographic hashing, and digital signing are later implementation milestones.
