# Story 7.6: Secrets Management Runbook — Key Rotation Procedure for All Providers

Status: ready-for-dev

**GitHub Issue:** [#52](https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/52)
**Epic:** Epic 7 — Security & Trust Foundation
**Priority:** Medium — establish before first external pilot

## Story

As a System Administrator,
I want a documented, tested runbook for rotating every API key and secret used by Aetherix,
So that in the event of a credential leak, I can revoke and replace all affected keys within 30 minutes without service interruption.

## Acceptance Criteria

1. **Given** all external service integrations, **When** the inventory is complete, **Then** `docs/SECRETS-RUNBOOK.md` exists listing every secret: provider, type, env var name, owner, rotation frequency, last rotation date.
2. **Given** each secret in the inventory, **When** the runbook is written, **Then** it provides step-by-step rotation instructions: how to generate new credential, update env var without restart (hot-swap), verify new credential, revoke old credential, estimated downtime.
3. **Given** `ANTHROPIC_API_KEY`, `TWILIO_AUTH_TOKEN`, and Supabase anon key, **When** rotation is executed, **Then** new key is tested in staging first, rotation completes with zero 5xx errors during the procedure. Verified by executing in staging.
4. **Given** a suspected credential leak, **When** incident detected, **Then** runbook provides an "Incident Response" section: immediate revocation steps, git history scanning for leaked key, communication checklist, 30-minute containment target.
5. **Given** the git repository, **When** a developer commits, **Then** a pre-commit hook (`detect-secrets`) scans for credential patterns. Commits with high-entropy strings or key patterns are blocked. Setup documented in `CONTRIBUTING.md` or README dev setup section.
6. **Given** PMS API keys (Story 2.1 AES-256 encryption), **When** audited, **Then** AES-256 is confirmed for all PMS credentials. The encryption key (`ENCRYPTION_KEY` or `AUTH_SECRET`) is itself only in env vars and has its own rotation procedure.

## Tasks / Subtasks

- [ ] Task 1: Complete secrets inventory (AC: #1)
  - [ ] Audit all env vars in all `.env.example` files (root, backend, frontend)
  - [ ] Create `docs/SECRETS-RUNBOOK.md` with inventory table

- [ ] Task 2: Write per-provider rotation procedures (AC: #2)
  - [ ] Anthropic API key rotation steps
  - [ ] Supabase (URL, anon key, service key) rotation steps
  - [ ] Twilio (Account SID + Auth Token) rotation steps
  - [ ] Apaleo OAuth2 (client ID + secret) rotation steps
  - [ ] Redis/Upstash rotation steps
  - [ ] Mistral API key rotation steps
  - [ ] PredictHQ API key rotation steps
  - [ ] OpenWeatherMap API key rotation steps
  - [ ] SendGrid API key rotation steps
  - [ ] JWT `AUTH_SECRET` rotation steps (high blast radius — invalidates all sessions — document carefully)

- [ ] Task 3: Test zero-downtime rotation for critical keys (AC: #3)
  - [ ] Execute Anthropic key rotation in staging — verify zero 5xx
  - [ ] Execute Twilio auth token rotation in staging — verify zero 5xx
  - [ ] Document actual downtime observed for each

- [ ] Task 4: Incident response procedure (AC: #4)
  - [ ] Write "Incident Response" section in `docs/SECRETS-RUNBOOK.md`
  - [ ] Include: revoke → scan git history → assess blast radius → communicate
  - [ ] Include git scanning command (see Dev Notes)

- [ ] Task 5: Pre-commit secret scanning (AC: #5)
  - [ ] Install `detect-secrets`: `pip install detect-secrets`
  - [ ] Generate baseline: `detect-secrets scan > .secrets.baseline`
  - [ ] Add `.pre-commit-config.yaml` hook
  - [ ] Document setup in README dev section or `CONTRIBUTING.md`

- [ ] Task 6: Verify AES-256 for PMS credentials (AC: #6)
  - [ ] Locate AES-256 encryption implementation from Story 2.1
  - [ ] Confirm it covers all PMS credentials, not only the first integration
  - [ ] Add `ENCRYPTION_KEY` rotation procedure to runbook

## Dev Notes

### Secrets Inventory Table Format
```markdown
| Provider | Type | Env Var | Owner | Rotation Frequency | Last Rotated |
|----------|------|---------|-------|-------------------|--------------|
| Anthropic | API Key | ANTHROPIC_API_KEY | Dev | 90 days | YYYY-MM-DD |
| Supabase | URL | SUPABASE_URL | Dev | On compromise | YYYY-MM-DD |
| Supabase | Anon Key | SUPABASE_KEY | Dev | 90 days | YYYY-MM-DD |
| Twilio | Auth Token | TWILIO_AUTH_TOKEN | Dev | 90 days | YYYY-MM-DD |
| Apaleo | OAuth2 Client Secret | APALEO_CLIENT_SECRET | Dev | Annual | YYYY-MM-DD |
| Upstash | Redis URL (with token) | REDIS_URL | Dev | 90 days | YYYY-MM-DD |
| Mistral | API Key | MISTRAL_API_KEY | Dev | 90 days | YYYY-MM-DD |
| JWT | Auth Secret | AUTH_SECRET | Dev | On compromise (session-breaking) | YYYY-MM-DD |
...
```

### Git History Scan for Leaked Credentials
```bash
# Check if a specific string was ever committed
git log -S "ANTHROPIC_API_KEY" --all --oneline

# Scan with truffleHog (comprehensive)
pip install trufflehog
trufflehog git file://. --only-verified

# With detect-secrets
detect-secrets scan --all-files
```

### detect-secrets Setup
```bash
pip install detect-secrets
detect-secrets scan > .secrets.baseline
# Add to .pre-commit-config.yaml:
# repos:
# - repo: https://github.com/Yelp/detect-secrets
#   rev: v1.4.0
#   hooks:
#   - id: detect-secrets
#     args: ['--baseline', '.secrets.baseline']
```

### Managed Vault Evaluation
Consider for Phase 1+:
- **Infisical** (free tier): Python SDK, native Render/Fly.io integration, secrets versioning
- **Doppler** (free tier): env var injection, team access controls, audit log
- **GitHub Secrets**: sufficient for CI/CD, not for runtime production secrets

### AUTH_SECRET Rotation Warning
Rotating `AUTH_SECRET` (JWT signing key) immediately invalidates ALL active user sessions. Plan for:
1. Notify managers in advance (maintenance window)
2. Update env var
3. Restart FastAPI process (required for JWT signing key)
4. Accept that all users will need to re-login

## References

- Story 2.1 (AES-256 PMS keys): `docs/bmad/_bmad-output/implementation-artifacts/2-1-establish-pms-api-connection-and-auth.md`
- Config: `backend/app/core/config.py`
- All env vars: `.env.example` (root), `backend/.env.example`, `frontend/.env.example`
- GitHub Issue: https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/52

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
