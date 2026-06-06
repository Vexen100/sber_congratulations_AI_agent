# Merge report: frontend-polish onto react-new-base-backend

## Summary

- Integration branch: `merge/frontend-polish-onto-react-new-base-backend`
- Backend source of truth: `react-new-base-backend` at `ec6d6e3`
- Frontend source of truth: `frontend-polish` at `0e700cd`
- Merge base: `ff690976683146b2bad3bd553956de9f89b64769`
- Backup branch before merge: `backup/pre-merge-20260606-122453`

The merge was performed from the updated backend base with `git merge --no-commit --no-ff frontend-polish`. The merge used domain-aware resolution: backend/API/project-planner logic stayed authoritative from `react-new-base-backend`, while React layout, UI styling, frontend build settings, and static UI assets came from `frontend-polish`.

## Manual Conflict Decisions

- `frontend/src/pages/ProjectPlannerPage.tsx`: preserved backend additions for PPTX export, Reference Pack listing/preview/validation/install, backend API client usage, and project-planner type coverage.
- `frontend/src/pages/ProjectPlannerPage.tsx`: preserved frontend-polish layout with the new hero, input shell, stage shell, `InfoHint`, and polished form sections.
- `frontend/src/pages/ProjectPlannerPage.tsx`: merged selected-run actions so both `Скачать DOCX` and `Скачать PPTX` remain available in the polished result header.
- `frontend/src/pages/ProjectPlannerPage.tsx`: localized visible backend-added labels such as warnings, assumptions, confidence, facts, and suggested filename.

## Integration Decisions

- `frontend/vite.config.ts`: enabled `build.manifest` so production builds emit `frontend/dist/.vite/manifest.json` for hashed asset auditing.
- `backend/app/frontend.py`: kept the existing explicit SPA allowlist and static asset serving model; localized the missing-build fallback page.
- `.gitignore`: kept frontend generated build artifacts ignored and removed duplicate `*.tsbuildinfo`.
- `README.md`: updated the React production route list to include `/project-planner`.

## Domain Preservation

- Backend API, AI/LLM/project-planner modules, tests, requirements, scripts, and generated export logic remain from `react-new-base-backend`.
- React app shell, UI polish, `InfoHint`, frontend package metadata, frontend TS configs, and CSS/static UI assets came from `frontend-polish`.
- No backend secret names or private env values were added to frontend public config.
- No Jinja template tree was found in the repository; React serving is handled by FastAPI static hosting and explicit SPA route registration.

## Residual Risks

- The repository has no Playwright/Cypress/e2e suite, so deep-link/browser flows were not automatically exercised beyond frontend build and backend route tests.
- No Dockerfile or Compose config exists in the repository, so container smoke checks were not applicable.
- The project uses raw SQL migration files rather than Alembic in this tree; no Alembic dry-run was available.
- CI workflow updates were intentionally left out of this branch because the available GitHub credential cannot push workflow-file changes without `workflow` scope.
- `npm ci` reports 2 moderate npm audit findings in the current dependency graph.
