# Story 7.5: GDPR Data Inventory + Anonymization Audit — PII Mapping and Hive Memory Data Flow

Status: ready-for-dev

**GitHub Issue:** [#51](https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/51)
**Epic:** Epic 7 — Security & Trust Foundation
**Priority:** Medium — required before Phase 2 multi-hotel rollout and any EU live data processing

## Story

As the Data Controller (Aetherix / Ivan de Murard),
I want a complete, documented inventory of all personal data processed by the system with verified technical controls,
So that Aetherix can legally operate with EU hotel data, respond to data subject requests, and demonstrate GDPR compliance to Apaleo and hotel partners.

## Acceptance Criteria

1. **Given** the full codebase and DB schema, **When** the audit is complete, **Then** `docs/GDPR-DATA-INVENTORY.md` exists listing every data category (data type, legal basis, storage location, retention period, PII classification).
2. **Given** the PMS ingestion pipeline (`pms_sync.py`, `data_transformer.py`), **When** raw PMS data enters, **Then** a code audit confirms all guest PII (name, email, phone, passport) is stripped/hashed before DB write. An automated test verifies this: synthetic PII payload → zero PII in resulting DB records.
3. **Given** manager phone numbers used as webhook sender IDs, **When** stored in DB or logs, **Then** they are stored as SHA-256 hashes only. Raw phone-to-hash mapping exists only in encrypted Supabase Auth profile. Verified by automated test.
4. **Given** the Phase 3 Hive Memory design, **When** documented, **Then** `docs/GDPR-DATA-INVENTORY.md` describes: aggregation functions applied, min group size (≥5 properties, k-anonymity model), opt-out mechanism per hotel, no single-hotel attribution possible from Hive data.
5. **Given** operational data in Supabase, **When** retention policy is implemented, **Then** a scheduled job deletes/archives data per policy: anomaly records (2yr), recommendation records (2yr), action logs (5yr), raw PMS sync data (90d), manager preferences (until deletion request).
6. **Given** a GDPR data subject access/deletion request, **When** submitted, **Then** `docs/GDPR-DATA-INVENTORY.md` contains a documented procedure for identifying, exporting, and deleting all records for that subject including cascade from `operational_memory`.

## Tasks / Subtasks

- [ ] Task 1: Data inventory audit (AC: #1)
  - [ ] List all Supabase tables and columns — classify each as PII / quasi-PII / operational
  - [ ] Determine legal basis for each data category (legitimate interest / contract / consent)
  - [ ] Write `docs/GDPR-DATA-INVENTORY.md` (template in Dev Notes below)

- [ ] Task 2: NFR3 technical verification (AC: #2)
  - [ ] Audit `pms_sync.py` and `data_transformer.py` — confirm PII stripping logic is present
  - [ ] Write `pytest` test: inject synthetic PMS payload with PII → assert no PII fields in resulting DB row
  - [ ] Document which fields are stripped vs hashed

- [ ] Task 3: Manager PII audit (AC: #3)
  - [ ] Check `action_logger.py`, `notification.py`, `whatsapp_service.py` — confirm phone stored as hash
  - [ ] Write test: phone number entered → DB record contains hash, not raw value

- [ ] Task 4: Hive Memory anonymization design doc (AC: #4)
  - [ ] Write Hive Memory section in `docs/GDPR-DATA-INVENTORY.md`
  - [ ] Define k-anonymity model (min group size: 5 hotels minimum before any pattern is published to Hive)
  - [ ] Define opt-out mechanism (env/DB flag per hotel)

- [ ] Task 5: Data retention implementation (AC: #5)
  - [ ] Define retention periods in config
  - [ ] Implement Supabase `pg_cron` job or FastAPI APScheduler task for data cleanup
  - [ ] Test cleanup job in staging

- [ ] Task 6: Data subject rights procedure (AC: #6)
  - [ ] Write access/erasure procedure in `docs/GDPR-DATA-INVENTORY.md`
  - [ ] Add `DPO_EMAIL` to `.env.example`

## Dev Notes

### GDPR-DATA-INVENTORY.md Template Structure
```markdown
# Aetherix GDPR Data Inventory

## Data Controller
Name: Ivan de Murard / Aetherix
DPO Contact: [DPO_EMAIL]

## Data Categories

| Category | Fields | Legal Basis | Storage | Retention | PII Level |
|----------|--------|-------------|---------|-----------|-----------|
| Hotel operational data | occupancy counts, revenue aggregates | Legitimate interest | Supabase | 2 years | Non-PII |
| Manager identity | hashed phone, email | Contract | Supabase Auth | Until deletion | Pseudo-PII |
| PMS sync raw data | reservation counts (no guest details) | Legitimate interest | Supabase | 90 days | Non-PII |
| Action logs | manager decisions (hashed ID) | Legitimate interest | Supabase | 5 years | Pseudo-PII |
...

## Hive Memory Anonymization Model
...

## Data Subject Rights Procedure
...
```

### Aetherix GDPR Role
- Aetherix = **Data Processor** (processes hotel guest data on behalf of the hotel, who is the Data Controller)
- Exception: manager contact data — Aetherix is the Data Controller for this
- This distinction must be stated in the Data Processing Agreement (DPA) with hotel clients

### PMS Data — PII to Strip
Fields to strip before DB write (not store at all):
- Guest name, email, phone, passport/ID number, nationality, loyalty program ID
Fields to keep (operational, non-PII):
- Reservation count, check-in/check-out dates (aggregated), room category, rate category

## References

- NFR3 definition: `docs/bmad/_bmad-output/planning-artifacts/epics.md`
- PMS sync: `backend/app/services/pms_sync.py`, `data_transformer.py`
- Hive Memory design: `CLAUDE.md` §Architecture mémoire cognitive
- GDPR EU: https://gdpr-info.eu/
- GitHub Issue: https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/51

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
