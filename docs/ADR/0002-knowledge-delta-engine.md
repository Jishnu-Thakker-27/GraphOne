# ADR 0002: Deterministic Precedence Merge Engine for Knowledge Delta Tracking

## Status
Accepted

## Context
Instead of overwriting MongoDB documents on every ingestion run, the pipeline must trace changes to entities. A probabilistic or confidence-based updating system introduces noise and non-explainable decisions.

## Decision
We implement a fully deterministic Knowledge Delta Engine based on:
1. **Source Precedence**: Numeric source precedence levels loaded from configuration rules (e.g., official APIs = 100, LLM extracts = 40). Higher priority overrides conflicting fields. Lower priority fills in missing fields only.
2. **Stable Entity Fingerprinting**: SHA-256 signatures generated from sorted stable entity content keys to bypass processing of unchanged duplicate crawled payloads.
3. **Change History Audits**: A clean state-transition log logging `changed_fields`, `old_values`, and `new_values`.

## Consequences
- No confidence-based score mapping.
- Order-preserving list unions (`list(dict.fromkeys(existing + incoming))`).
- Earliest date wins for publication dates, and protocol-agnostic URL comparisons.
