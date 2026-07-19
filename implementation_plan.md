# Implementation Plan: Deterministic Knowledge Delta Engine Refactor

This plan details the complete refactoring of the Knowledge Delta Engine of the AIIP project. The engine is being transformed into a deterministic state-difference and field-level merge engine, fully aligned with the strict production constraints:
- **No confidence estimation, thresholds, or probabilistic logic** within the Delta Engine.
- **Deterministic source precedence** using integer priorities loaded directly from `sources.yaml`.
- **Field-level merging** of records (incoming missing fields are always merged; conflicting fields respect precedence).
- **Entity Fingerprints** calculated via SHA-256 hashes of stable entity properties.
- **Auditable log structure** (`ChangeHistory`) and structured merge result object (`DeltaResult`).

---

## Proposed Changes

### 1. Source Precedence Configuration

#### [MODIFY] [sources.yaml](file:///c:/Users/jishn/OneDrive/Desktop/Jishnu/AI%20Signal/src/config/sources.yaml)
- Add integer precedence levels directly under the `precedence` property for each source config.
- Example mapping:
  - `arxiv`: `precedence: 100` (Official API)
  - `yc_companies`: `precedence: 90` (Structured JSON)
  - `github_trending_ai`: `precedence: 70` (Rule-Based HTML)
  - `techcrunch_ai` / `product_hunt`: `precedence: 50` (LLM Extraction)

#### [MODIFY] [registry.py](file:///c:/Users/jishn/OneDrive/Desktop/Jishnu/AI%20Signal/src/config/registry.py)
- Update `SourceConfig` schema to support the new integer `precedence: int = Field(50, ge=0, le=100)` field.

---

### 2. Common Schemas & Configurations

#### [MODIFY] [schemas.py](file:///c:/Users/jishn/OneDrive/Desktop/Jishnu/AI%20Signal/src/pipeline/schemas.py)
- **BaseEntity**: Add `entity_fingerprint: Optional[str] = None` and `content_hash: Optional[str] = None`.
- **ChangeHistory**: Restructure to represent deterministic audits:
  - `entity_id`: `str`
  - `entity_type`: `str`
  - `operation`: `str` (one of `INSERT`, `UPDATE`, `MERGE`, `SKIP`)
  - `changed_fields`: `list[str]`
  - `old_values`: `dict[str, Any]`
  - `new_values`: `dict[str, Any]`
  - `source`: `str`
  - `source_priority`: `int`
  - `timestamp`: `datetime`
  - `observed_at`: `datetime`
  - `updated_at`: `datetime`
  - `change_reason`: `str`
  - *Ensure all references to `confidence` are removed.*

#### [MODIFY] [config.py](file:///c:/Users/jishn/OneDrive/Desktop/Jishnu/AI%20Signal/src/config/config.py)
- Remove `DELTA_CONFIDENCE_THRESHOLD` setting completely from `Settings` loader and validator.

---

### 3. Knowledge Delta Engine

#### [MODIFY] [engine.py](file:///c:/Users/jishn/OneDrive/Desktop/Jishnu/AI%20Signal/src/delta/engine.py)
- Define `DeltaResult` as a Pydantic model:
  ```python
  from typing import Literal, list
  from pydantic import BaseModel

  class DeltaResult(BaseModel):
      action: Literal["INSERT", "UPDATE", "MERGE", "SKIP"]
      changed_fields: list[str]
      reason: str
      existing_priority: int
      incoming_priority: int
      fingerprint_changed: bool
  ```
- Implement **Entity Fingerprint**:
  - Calculate `SHA-256` of canonical name, entity type, content dictionary (excluding unstable dates/times/IDs), stable metadata, and content hash.
- Implement **Deterministic Merge Rules** for field conflicts:
  - **Missing field in database**: Always merge/add.
  - **Identical values**: Skip.
  - **Conflict**: Incoming priority wins.
  - **Lists**: Order-preserving union merge: `list(dict.fromkeys(existing + incoming))`.
  - **Numeric fields**: Replace only if incoming priority is strictly higher.
  - **URLs**: Normalize (strip protocol, trailing slashes, lowercase) before comparison.
  - **Publication Date**: Keep earliest date: `min(existing_date, incoming_date)`.
  - **Observed time**: Always update to latest: `max(existing_obs, incoming_obs)`.
- Commit updates and write `ChangeHistory` records containing precise old vs new values.

---

### 4. Verification Suite

#### [MODIFY] [main.py](file:///c:/Users/jishn/OneDrive/Desktop/Jishnu/AI%20Signal/src/main.py)
- Refactor the verification tests to cover all deterministic merge cases:
  1. **Initial Insertion**: Ingest a new entity from a source with priority `80`.
  2. **Fingerprint Match**: Ingest the same entity again and verify that it results in `SKIP` with no DB update or change logs.
  3. **Conflict Rejection (Lower Priority)**: Attempt to overwrite a field value using a source with priority `50`. Verify that the conflicting field is protected and not overwritten.
  4. **Missing Field Insertion (Lower Priority)**: Add a missing field in the incoming payload from a source with priority `50`. Verify that the missing field is merged.
  5. **Conflict Success (Higher Priority)**: Overwrite a field value using a source with priority `100`. Verify that the value is successfully updated.
  6. **List Union Merging**: Verify that lists merge using order-preserving union logic.
  7. **URL Normalization**: Verify that URLs containing differing trailing slashes or protocols (e.g. `https://openai.com` vs `http://openai.com/`) are treated as identical.
  8. **Publication Date Retention**: Verify that the earliest publication date is preserved.
  9. **ChangeHistory Audit Logging**: Verify that the generated log records are correct and do not contain any confidence fields.

---

## Verification Plan

### Automated Run
- Run `python -m src.main` and verify that the console outputs demonstrate full compliance with the deterministic merge workflow.
