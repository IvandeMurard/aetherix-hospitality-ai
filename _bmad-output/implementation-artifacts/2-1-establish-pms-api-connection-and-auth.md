# Story 2.1: Establish Apaleo PMS API Connection & Auth

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a System Administrator,
I want to securely use the pre-configured Apaleo API credentials for my property,
so that Aetherix can authenticate with the PMS securely (NFR4).

## Acceptance Criteria

1. **Secure Transmission:** When a manager provides an API key/token in the Next.js dashboard, it is transmitted securely to the FastAPI backend.
2. **Encryption at Rest:** The API credentials must be encrypted at rest using AES-256 in the Supabase database.
3. **Decryption and Connectivity:** The FastAPI backend can retrieve and decrypt the key to establish a successful ping (health check) to the PMS sandbox (Mews/Apaleo).
4. **Validation:** Unauthorized or invalid credentials should return a clear, compliant error message (RFC 7807).

## Tasks / Subtasks

- [x] Verify existing Apaleo Credentials in environment/database (AC: 1)
- [ ] Implement Encryption Utility for back-channel safety (AC: 2)
  - [ ] Use `cryptography` library (Fernet or AES-GCM) for AES-256 encryption.
- [ ] Refine Apaleo API Client (AC: 3)
  - [ ] Ensure `ApaleoClient` uses Client Credentials flow for back-channel sync correctly.
- [ ] Develop Connection Test Endpoint (AC: 3)
  - [ ] `GET /api/v1/pms/test`: Ping Apaleo sandbox to verify connection.
- [ ] Error Handling (AC: 4)
  - [ ] Implement RFC 7807 compliant error responses for auth failures.

## Dev Notes

### Relevant Architecture Patterns
- **Fat Backend Philosophy:** All heavy lifting (encryption, API calls) happens in the FastAPI backend.
- **Tenant Isolation:** Use RLS in Supabase to ensure credentials are only accessible by the property's owner. [Source: docs/ARCHITECTURE.md#L658]
- **Shared Error Handling:** Standardized Problem Details (RFC 7807). [Source: docs/ARCHITECTURE.md#L61]

### Source Tree Components
- `fastapi-backend/app/services/pms/`: New package for PMS integration.
- `fastapi-backend/app/core/security.py`: Add encryption utilities.
- `fastapi-backend/app/api/pms.py`: API endpoints for PMS configuration.

### Technical Specifics
- **Mews Auth:** Requires `ClientToken` and `AccessToken`. Headers: `Content-Type: application/json`.
- **Apaleo Auth:** Requires `ClientID` and `ClientSecret`. OAuth 2.0 endpoint: `https://identity.apaleo.com/connect/token`.
- **Encryption:** Use `AES-GCM` for authenticated encryption to ensure both confidentiality and integrity.

## References
- [ARCHITECTURE.md](file:///c:/Users/IVAN/Documents/fb-agent-mvp/docs/ARCHITECTURE.md)
- [EPICS.md](file:///c:/Users/IVAN/Documents/fb-agent-mvp/_bmad-output/planning-artifacts/epics.md#L152)
- [Mews Connector API Docs](https://mews.com/connector-api-docs)
- [Apaleo Identity API Docs](https://apaleo.dev/docs/identity)

## Dev Agent Record

### Agent Model Used
Claude 3.5 Sonnet (via Antigravity)

### Status Update
Ultimate context engine analysis completed - comprehensive developer guide created. Status set to ready-for-dev.
