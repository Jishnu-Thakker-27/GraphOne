"""
Export Layer.

Fetches data from MongoDB collections, flattens the nested structures,
and exports them to CSV, an Excel Workbook (separate sheets), and Google Sheets.
"""

import os
from typing import Any, Dict, List
import pandas as pd
from loguru import logger
import gspread
from google.oauth2.service_account import Credentials

from src.config.config import settings
from src.database.repositories import (
    StartupRepository,
    ProductRepository,
    ResearchPaperRepository,
    JobRepository,
    NewsRepository,
    EntityMappingRepository
)

class DataExporter:
    """Manages exporting pipeline records from MongoDB to CSV, Excel, and Google Sheets."""

    def __init__(self) -> None:
        self.startup_repo = StartupRepository()
        self.product_repo = ProductRepository()
        self.paper_repo = ResearchPaperRepository()
        self.job_repo = JobRepository()
        self.news_repo = NewsRepository()
        self.mapping_repo = EntityMappingRepository()

    def _fetch_flat_startups(self) -> List[Dict[str, Any]]:
        docs = self.startup_repo.find()
        flat = []
        for d in docs:
            content = d.get("content", {})
            data = content.get("data", {})
            source = d.get("source", {})
            flat.append({
                "Entity Name": content.get("entityName"),
                "Employee Count": data.get("employeeCount"),
                "Source Name": source.get("name"),
                "Source URL": source.get("url"),
                "Collected At": d.get("collectedAt"),
                "Observed At": d.get("observedAt"),
                "Updated At": d.get("updatedAt"),
            })
        return flat

    def _fetch_flat_products(self) -> List[Dict[str, Any]]:
        docs = self.product_repo.find()
        flat = []
        for d in docs:
            content = d.get("content", {})
            source = d.get("source", {})
            flat.append({
                "Startup Name": content.get("startupName"),
                "Pricing Model": content.get("pricingModel"),
                "Source Name": source.get("name"),
                "Source URL": source.get("url"),
                "Collected At": d.get("collectedAt"),
                "Observed At": d.get("observedAt"),
                "Updated At": d.get("updatedAt"),
            })
        return flat

    def _fetch_flat_papers(self) -> List[Dict[str, Any]]:
        docs = self.paper_repo.find()
        flat = []
        for d in docs:
            content = d.get("content", {})
            source = d.get("source", {})
            authors = content.get("authors", [])
            flat.append({
                "Title": content.get("title"),
                "Authors": ", ".join(authors) if isinstance(authors, list) else str(authors),
                "Paper URL": content.get("paper_url"),
                "GitHub URL": content.get("github_url"),
                "GitHub Stars": content.get("github_stars"),
                "GitHub Forks": content.get("github_forks"),
                "GitHub Language": content.get("github_language"),
                "GitHub Description": content.get("github_description"),
                "Published Date": content.get("published_date"),
                "Source Name": source.get("name"),
                "Source URL": source.get("url"),
                "Collected At": d.get("collectedAt"),
                "Observed At": d.get("observedAt"),
                "Updated At": d.get("updatedAt"),
            })
        return flat

    def _fetch_flat_jobs(self) -> List[Dict[str, Any]]:
        docs = self.job_repo.find()
        flat = []
        for d in docs:
            content = d.get("content", {})
            source = d.get("source", {})
            flat.append({
                "Company": content.get("company"),
                "Role Family": content.get("role_family"),
                "Is Remote": content.get("is_remote"),
                "Published Date": content.get("date"),
                "Source Name": source.get("name"),
                "Source URL": source.get("url"),
                "Collected At": d.get("collectedAt"),
                "Observed At": d.get("observedAt"),
                "Updated At": d.get("updatedAt"),
            })
        return flat

    def _fetch_flat_news(self) -> List[Dict[str, Any]]:
        docs = self.news_repo.find()
        flat = []
        for d in docs:
            content = d.get("content", {})
            source = d.get("source", {})
            flat.append({
                "Title": content.get("title"),
                "Summary": content.get("summary"),
                "URL": content.get("url"),
                "Published Date": content.get("published_date"),
                "Source Name": source.get("name"),
                "Source URL": source.get("url"),
                "Collected At": d.get("collectedAt"),
                "Observed At": d.get("observedAt"),
                "Updated At": d.get("updatedAt"),
            })
        return flat

    def _fetch_flat_mappings(self) -> List[Dict[str, Any]]:
        docs = self.mapping_repo.find()
        flat = []
        for d in docs:
            flat.append({
                "Raw Name": d.get("rawName"),
                "Canonical Name": d.get("canonicalName"),
                "Similarity Score": d.get("similarityScore", 100.0),
                "Resolution Method": d.get("resolutionMethod", "EXACT"),
                "Timestamp": d.get("timestamp"),
            })
        return flat

    def generate_dataframes(self) -> Dict[str, pd.DataFrame]:
        """Fetches all entity data and returns a dict of pandas DataFrames."""
        return {
            "Startups": pd.DataFrame(self._fetch_flat_startups()),
            "Products": pd.DataFrame(self._fetch_flat_products()),
            "Research Papers": pd.DataFrame(self._fetch_flat_papers()),
            "Jobs": pd.DataFrame(self._fetch_flat_jobs()),
            "News": pd.DataFrame(self._fetch_flat_news()),
            "Entity Mapping Log": pd.DataFrame(self._fetch_flat_mappings())
        }

    def export_to_local(self, output_dir: str = "outputs") -> None:
        """Exports all collections to local CSV files and a single Excel workbook."""
        os.makedirs(output_dir, exist_ok=True)
        dfs = self.generate_dataframes()

        # 1. Export CSVs
        for name, df in dfs.items():
            if df.empty:
                logger.warning(f"Dataframe '{name}' is empty. Skipping CSV write.")
                continue
            
            # Format filename (e.g. "Research Papers" -> "research_papers.csv")
            filename = name.lower().replace(" ", "_") + ".csv"
            filepath = os.path.join(output_dir, filename)
            
            # Format datetime columns to string for readable CSV output
            df_to_save = df.copy()
            for col in df_to_save.columns:
                if df_to_save[col].dtype == 'datetime64[ns]' or 'datetime' in str(df_to_save[col].dtype):
                    df_to_save[col] = df_to_save[col].dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            
            df_to_save.to_csv(filepath, index=False)
            logger.info(f"Exported CSV: {filepath}")

        # 2. Export Excel Workbook
        excel_path = os.path.join(output_dir, "extracted_data.xlsx")
        excel_preferred_dir = os.path.join(output_dir, "excel")
        excel_preferred_path = os.path.join(excel_preferred_dir, "AIIP_Output.xlsx")
        
        os.makedirs(excel_preferred_dir, exist_ok=True)
        
        try:
            # Write to legacy path (all sheets)
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                for name, df in dfs.items():
                    df_to_save = df.copy()
                    for col in df_to_save.columns:
                        if pd.api.types.is_datetime64_any_dtype(df_to_save[col]):
                            df_to_save[col] = df_to_save[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                    df_to_save.to_excel(writer, sheet_name=name, index=False)
            logger.info(f"Exported Excel Workbook: {excel_path}")
            
            # Write to assignment-preferred path (all 6 sheets)
            main_sheets = ["Startups", "Products", "Research Papers", "Jobs", "News", "Entity Mapping Log"]
            with pd.ExcelWriter(excel_preferred_path, engine="openpyxl") as writer:
                for name in main_sheets:
                    df = dfs.get(name, pd.DataFrame())
                    df_to_save = df.copy()
                    for col in df_to_save.columns:
                        if pd.api.types.is_datetime64_any_dtype(df_to_save[col]):
                            df_to_save[col] = df_to_save[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                    df_to_save.to_excel(writer, sheet_name=name, index=False)
            logger.info(f"Exported Preferred Excel Workbook: {excel_preferred_path}")
            
        except Exception as e:
            logger.error(f"Failed to write Excel workbook: {e}")

    def export_to_google_sheets(self) -> None:
        """Syncs MongoDB database content to the configured Google Sheet via gspread."""
        creds_path = settings.GOOGLE_SHEETS_CREDENTIALS_PATH
        sheet_id = settings.GOOGLE_SHEET_ID

        if not creds_path or not sheet_id:
            logger.warning("Google Sheets credentials path or Sheet ID not configured. Skipping Google Sheets sync.")
            return

        if not os.path.exists(creds_path):
            logger.warning(f"Google Sheets credentials file not found at path: {creds_path}. Skipping Google Sheets sync.")
            return

        logger.info(f"Syncing data to Google Sheet ID: {sheet_id}")
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(sheet_id)

            dfs = self.generate_dataframes()

            for tab_name, df in dfs.items():
                try:
                    # Clean and format DataFrame values
                    df_to_sync = df.copy()
                    
                    # Convert datetimes to strings for Google Sheets
                    for col in df_to_sync.columns:
                        if pd.api.types.is_datetime64_any_dtype(df_to_sync[col]):
                            df_to_sync[col] = df_to_sync[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    df_to_sync = df_to_sync.fillna("")
                    
                    # Get or create worksheet
                    try:
                        worksheet = spreadsheet.worksheet(tab_name)
                    except gspread.WorksheetNotFound:
                        worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="20")
                        logger.info(f"Created new worksheet: '{tab_name}'")

                    # Clear worksheet first
                    worksheet.clear()

                    # Write header and values
                    headers = df_to_sync.columns.tolist()
                    values = df_to_sync.values.tolist()
                    worksheet.update("A1", [headers] + values)
                    logger.info(f"Synchronized tab '{tab_name}' to Google Sheets. Rows: {len(values)}")
                except Exception as ex:
                    logger.error(f"Failed to synchronize tab '{tab_name}': {ex}")

            logger.info("Google Sheets synchronization completed successfully.")
        except Exception as e:
            logger.error(f"Failed to authorize or open Google Sheet: {e}")
