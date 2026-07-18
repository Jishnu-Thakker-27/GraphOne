"""
Hybrid Extraction Engine.

Handles rule-based HTML parsing, JSON-LD metadata extraction,
and API parsing, outputting raw dictionary data that matches Pydantic entity schemas.
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from loguru import logger

from src.pipeline.schemas import ExtractionStrategy

class HybridExtractionEngine:
    """Orchestrates structured parsing for API, JSON-LD, and Custom Rules."""

    @classmethod
    def extract(cls, source_name: str, content: str, strategy: ExtractionStrategy) -> List[Dict[str, Any]]:
        """
        Extracts structured records from raw content based on the selected strategy.
        Returns a list of raw dicts that represent the extracted entities.
        """
        logger.info(f"Starting hybrid extraction | Source: {source_name} | Strategy: {strategy.value}")
        
        try:
            if strategy == ExtractionStrategy.JSON_API:
                return cls.extract_json_api(source_name, content)
            elif strategy == ExtractionStrategy.JSON_LD:
                return cls.extract_json_ld(source_name, content)
            elif strategy == ExtractionStrategy.RULE_BASED:
                return cls.extract_rule_based(source_name, content)
            else:
                logger.warning(f"Strategy {strategy.value} not supported by Hybrid Extraction Engine (routes to LLM instead)")
                return []
        except Exception as e:
            logger.error(f"Extraction failed | Source: {source_name} | Error: {e}")
            return []

    @classmethod
    def extract_json_api(cls, source_name: str, content: str) -> List[Dict[str, Any]]:
        """Parses structured API responses (JSON or XML)."""
        entities = []
        if source_name == "arxiv":
            try:
                soup = BeautifulSoup(content, "xml")
                entries = soup.find_all("entry")
                for entry in entries:
                    title_elem = entry.find("title")
                    title_text = title_elem.text.strip() if title_elem else "Unknown Title"
                    
                    authors = [
                        author.find("name").text.strip()
                        for author in entry.find_all("author")
                        if author.find("name")
                    ]
                    
                    id_elem = entry.find("id")
                    paper_url = id_elem.text.strip() if id_elem else ""
                    
                    published_elem = entry.find("published")
                    published_date = datetime.now(timezone.utc)
                    if published_elem:
                        try:
                            published_date = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
                        except ValueError:
                            pass
                        
                    entities.append({
                        "recordType": "RESEARCH_PAPER",
                        "content": {
                            "title": title_text,
                            "authors": authors,
                            "paper_url": paper_url,
                            "published_date": published_date,
                            "github_url": None,
                            "github_stars": None
                        }
                    })
                logger.info(f"API Extractor completed | Source: {source_name} | Extracted {len(entities)} papers")
            except Exception as e:
                logger.error(f"Failed to parse arXiv Atom feed XML: {e}")
        return entities

    @classmethod
    def extract_json_ld(cls, source_name: str, content: str) -> List[Dict[str, Any]]:
        """Extracts and maps JSON-LD blocks from HTML content."""
        entities = []
        try:
            soup = BeautifulSoup(content, "html.parser")
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string.strip())
                    if not data:
                        continue
                    
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        entity = cls._map_schema_item_to_entity(item)
                        if entity:
                            entities.append(entity)
                except Exception as ex:
                    logger.debug(f"Skipping malformed JSON-LD block: {ex}")
            logger.info(f"JSON-LD Extractor completed | Source: {source_name} | Extracted {len(entities)} entities")
        except Exception as e:
            logger.error(f"Failed to extract JSON-LD: {e}")
        return entities

    @classmethod
    def extract_rule_based(cls, source_name: str, content: str) -> List[Dict[str, Any]]:
        """Parses HTML using custom rules matched to the source name."""
        entities = []
        if source_name == "github_trending_ai":
            try:
                soup = BeautifulSoup(content, "html.parser")
                articles = soup.find_all("article", class_="Box-row")
                for article in articles:
                    h2 = article.find("h2", class_="h3")
                    if not h2 or not h2.a:
                        continue
                    
                    name_raw = h2.a.text.strip().replace(" ", "").replace("\n", "")
                    parts = name_raw.split("/")
                    repo_name = parts[1] if len(parts) > 1 else name_raw
                    
                    # Try to extract description
                    desc_elem = article.find("p", class_="col-9")
                    desc = desc_elem.text.strip() if desc_elem else ""
                    
                    # We map github repo as Product
                    entities.append({
                        "recordType": "PRODUCT",
                        "content": {
                            "startupName": repo_name,
                            "pricingModel": "FREE"
                        }
                    })
                logger.info(f"Rule-based Extractor completed | Source: {source_name} | Extracted {len(entities)} products")
            except Exception as e:
                logger.error(f"GitHub Trending rule-based parsing failed: {e}")
        return entities

    @classmethod
    def _map_schema_item_to_entity(cls, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Maps a JSON-LD schema item to a canonical entity dict format."""
        schema_type = item.get("@type", "")
        if not schema_type:
            return None
            
        # Map Organization -> Startup
        if schema_type in ("Organization", "Corporation", "LocalBusiness"):
            emp_count = None
            employees = item.get("numberOfEmployees")
            if isinstance(employees, dict):
                emp_count = employees.get("value")
            elif isinstance(employees, (int, str)):
                try:
                    emp_count = int(employees)
                except ValueError:
                    pass
                    
            return {
                "recordType": "STARTUP",
                "content": {
                    "entityName": item.get("name", "Unknown Startup"),
                    "data": {
                        "employeeCount": emp_count
                    }
                }
            }
            
        # Map Product -> Product
        elif schema_type in ("Product", "SoftwareApplication"):
            pricing = "FREE"
            offers = item.get("offers")
            if offers:
                pricing = "PAID"
                if isinstance(offers, dict):
                    price = offers.get("price")
                    if price == 0 or price == "0":
                        pricing = "FREE"
                    
            return {
                "recordType": "PRODUCT",
                "content": {
                    "startupName": item.get("name", "Unknown Product"),
                    "pricingModel": pricing
                }
            }

        # Map ScholarlyArticle -> ResearchPaper
        elif schema_type in ("ScholarlyArticle", "MedicalScholarlyArticle"):
            authors_raw = item.get("author", [])
            if isinstance(authors_raw, dict):
                authors = [authors_raw.get("name", "")]
            elif isinstance(authors_raw, list):
                authors = [
                    a.get("name", "") if isinstance(a, dict) else str(a)
                    for a in authors_raw
                ]
            else:
                authors = [str(authors_raw)]
                
            published_str = item.get("datePublished", "")
            published_date = datetime.now(timezone.utc)
            if published_str:
                try:
                    published_date = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                except ValueError:
                    pass
                    
            return {
                "recordType": "RESEARCH_PAPER",
                "content": {
                    "title": item.get("name") or item.get("headline") or "Unknown Title",
                    "authors": [a for a in authors if a],
                    "paper_url": item.get("url") or "",
                    "github_url": None,
                    "github_stars": None,
                    "published_date": published_date
                }
            }
            
        return None
