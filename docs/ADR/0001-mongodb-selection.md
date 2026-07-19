# ADR 0001: MongoDB Selection for Primary Document Storage

## Status
Accepted

## Context
The AIIP ingestion pipeline processes unstructured and semi-structured entities scraped from various AI directories, job boards, and research databases. The fields representing these entities are dynamic and change often based on source layout updates.

## Decision
We select MongoDB as our primary document storage. It supports flexible document structures, permitting nested fields (e.g., `content.data.employeeCount` or `content.github_stars`) to be written or modified without predefined SQL schema migrations.

## Consequences
- **Pros**: Dynamic typing, easy integration with Pydantic model serialization (`model_dump()`), fast indexing on canonical entity name keys.
- **Cons**: Lack of strict transactional relational constraints across collections, which will be mitigated by our application-level Fuzzy Entity Resolver and Pydantic validation.
