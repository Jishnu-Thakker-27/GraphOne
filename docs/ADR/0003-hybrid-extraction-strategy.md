# ADR 0003: Hybrid Strategy Selection for Payload Extraction

## Status
Accepted

## Context
Crawling thousands of entities using LLMs alone is highly expensive and subject to rate limits. Many sites already expose API endpoints or structured schema data (like JSON-LD).

## Decision
We implement a hybrid extraction engine with a dynamic selector routing as follows:
1. Use **Rule-Based Parsing** if the source defines custom parsers or APIs.
2. Check for **JSON-LD Schema** in page HTML; parse it directly if present.
3. Fall back to **LLM extraction** using a tiered model fallback chain (Gemini 2.5 Flash -> Groq Llama 3.1 -> DeepSeek) if no structured format exists.

## Consequences
- Minimizes token consumption and latency.
- Ensures resilience through automated failovers.
