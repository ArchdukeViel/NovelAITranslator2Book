# Checkpoint footprint evidence

Run/design evidence: `pac-8a109a5ad1cd`
Scope: isolated disposable runtime fixture; no production checkpoint or
canonical content was changed

## Measurement

The local fixture used one synthetic chapter with repetitive raw and
translated text so the measurement is reproducible but is not a production
content-size estimate. The existing checkpoint shape was measured as
`legacy-copy-v1` because it stores raw, translated, and state copies together:

- Serialized envelope: 38,746 bytes.
- Compressed serialized envelope: 701 bytes.
- Raw copy: 22,782 bytes.
- Translated copy: 15,168 bytes.
- State copy: 257 bytes.
- Candidate reference-only envelope: 514 bytes.
- Checkpoint writes: 1; rewrites: 0.
- Recovery reads: 1; recovery bytes: 38,746.
- Restore result: successful.
- Retention age at measurement: 0.127 seconds.
- Canonical/external writes: 0.

The reference-only candidate contains bounded state, hashes, identifiers, and
exact artifact references but no raw or translated body. The test exercises
the existing local restore contract and confirms the old copy-shaped envelope
still restores successfully.

## Decision

The byte measurement identifies a potential duplicate-content reduction, but
compaction is not enabled. No operator-approved duplicate-byte,
recovery-read, or retention threshold exists, and a versioned migration or
runtime rewrite would require a separate approval. The evidence-backed action
is therefore a no-op/retain decision: preserve the existing envelope and
restore behavior until thresholds and a reference-only migration contract are
approved. The local test does not claim PostgreSQL/R2 hosted behavior.

## Verification

- `tools\pytest.ps1 backend/tests/test_checkpoint_manager.py backend/tests/test_translation_resume_contract.py -q` - exit 0; 12 passed in 5.23s.
- `tools\pytest.ps1 backend/tests/test_checkpoint_footprint.py -q -s` - exit 0; 1 passed in 2.98s and emitted the sanitized measurement above.
- Focused Ruff over `backend/tests/test_checkpoint_footprint.py` - exit 0; all checks passed.
- `tools\pyright.ps1` - exit 0; 0 errors, 0 warnings, 0 informations.
- `graphify update . --no-cluster` - exit 0; graph refreshed successfully.
