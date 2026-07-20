"""
Lightweight Pipeline Metrics Tracker.

Collects, updates, and reports run-time operational metrics for the pipeline.

Validation counters (incremented by main.py after each pipeline stage):
  records_crawled    — raw extraction output, before any validation filter
  records_validated  — records that passed Pydantic schema + URL + artifact checks
  records_rejected   — records discarded by EntityValidator
  duplicates_skipped — Delta Engine SKIP where fingerprint matched (identical content)
  conflicts_skipped  — Delta Engine SKIP where lower-priority source values were rejected
  records_exported   — final row counts per entity category after CSV/Excel export
"""

import time
from typing import Any, Dict, Optional
from loguru import logger

class PipelineMetricsCollector:
    """Singleton-based tracker for ingestion pipeline metrics."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PipelineMetricsCollector, cls).__new__(cls)
            cls._instance._init_metrics()
        return cls._instance

    def _init_metrics(self) -> None:
        self.records_crawled: int = 0
        self.records_validated: int = 0
        self.records_rejected: int = 0
        # Delta Engine SKIP — fingerprint unchanged: identical record already in DB
        self.duplicates_skipped: int = 0
        # Delta Engine SKIP — content changed but incoming source priority is lower
        self.conflicts_skipped: int = 0
        self.delta_updates: int = 0
        self.github_api_calls: int = 0
        self.github_cache_hits: int = 0
        self.github_cache_misses: int = 0
        self.llm_calls: int = 0
        self.llm_cache_hits: int = 0
        self.llm_cache_misses: int = 0
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        # Per-category exported record counts populated after export completes
        self.records_exported: Dict[str, int] = {}

    def start_timer(self) -> None:
        """Starts the pipeline processing timer."""
        self.start_time = time.time()
        self.end_time = 0.0

    def stop_timer(self) -> None:
        """Stops the pipeline processing timer."""
        self.end_time = time.time()

    def increment(self, metric_name: str, count: int = 1) -> None:
        """Increments a metric by the specified count."""
        if hasattr(self, metric_name):
            setattr(self, metric_name, getattr(self, metric_name) + count)
        else:
            logger.warning(f"Attempted to increment non-existent metric: {metric_name}")

    def set_exported(self, dataframes: Optional[Dict] = None) -> None:
        """
        Records the final exported row count per entity category.

        Accepts the dict returned by DataExporter.generate_dataframes().
        Keys are sheet names (e.g. 'Startups', 'Products'); values are DataFrames.
        Only non-empty DataFrames are recorded.
        """
        if not dataframes:
            return
        self.records_exported = {
            sheet: len(df)
            for sheet, df in dataframes.items()
            if df is not None and len(df) > 0
        }

    def increment_exported(self, category: str, count: int) -> None:
        """Increments the exported count for a single category."""
        self.records_exported[category] = self.records_exported.get(category, 0) + count

    def get_processing_time(self) -> float:
        """Calculates total processing duration in seconds."""
        if self.start_time == 0.0:
            return 0.0
        t = self.end_time if self.end_time > 0.0 else time.time()
        return t - self.start_time

    def get_metrics(self) -> Dict[str, Any]:
        """Returns a dict containing current metrics."""
        return {
            "records_crawled": self.records_crawled,
            "records_validated": self.records_validated,
            "records_rejected": self.records_rejected,
            "duplicates_skipped": self.duplicates_skipped,
            "conflicts_skipped": self.conflicts_skipped,
            "delta_updates": self.delta_updates,
            "records_exported": dict(self.records_exported),
            "github_api_calls": self.github_api_calls,
            "github_cache_hits": self.github_cache_hits,
            "github_cache_misses": self.github_cache_misses,
            "llm_calls": self.llm_calls,
            "llm_cache_hits": self.llm_cache_hits,
            "llm_cache_misses": self.llm_cache_misses,
            "processing_time": round(self.get_processing_time(), 2)
        }

    def log_summary(self) -> None:
        """Logs a formatted pipeline summary at the end of every ingestion run."""
        m = self.get_metrics()
        W = 32  # column width for aligned output
        sep = "=" * W
        logger.info(sep)
        logger.info("  PIPELINE SUMMARY")
        logger.info(sep)
        logger.info(f"  {'Records Crawled':<22}: {m['records_crawled']}")
        logger.info(f"  {'Records Validated':<22}: {m['records_validated']}")
        logger.info(f"  {'Records Rejected':<22}: {m['records_rejected']}")
        logger.info(f"  {'Duplicates Skipped':<22}: {m['duplicates_skipped']}")
        logger.info(f"  {'Conflicts Skipped':<22}: {m['conflicts_skipped']}")
        logger.info(f"  {'Delta Updates':<22}: {m['delta_updates']}")
        if m['records_exported']:
            logger.info("")
            logger.info("  Export Summary")
            logger.info("  " + "-" * (W - 2))
            for category, count in m['records_exported'].items():
                logger.info(f"  {category:<22}: {count}")
        logger.info("")
        logger.info(f"  {'GitHub API Calls':<22}: {m['github_api_calls']}")
        logger.info(f"  {'GitHub Cache Hits':<22}: {m['github_cache_hits']}")
        logger.info(f"  {'LLM Calls':<22}: {m['llm_calls']}")
        logger.info(f"  {'LLM Cache Hits':<22}: {m['llm_cache_hits']}")
        logger.info(f"  {'Processing Time':<22}: {m['processing_time']:.2f}s")
        logger.info("")
        logger.info(f"  {'Pipeline Status':<22}: SUCCESS")
        logger.info(sep)

    def reset(self) -> None:
        """Resets all metrics to zero."""
        self._init_metrics()

# Global metrics collector instance
metrics_collector = PipelineMetricsCollector()
