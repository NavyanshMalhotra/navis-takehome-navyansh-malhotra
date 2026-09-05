"""
Source Data Ingestion Module.
Provides robust readers for Notion CSVs + Page Markdown files, Custodian XLSX,
Advisor Roster, and Slack exports.
Works with zero external dependencies (pure standard library).
"""

import csv
import glob
import os
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

def read_advisor_roster(roster_path: Path) -> List[Dict[str, str]]:
    """Reads advisor_roster.csv into list of advisor records."""
    if not roster_path.exists():
        raise FileNotFoundError(f"Advisor roster not found at: {roster_path}")
    with open(roster_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]

def read_custodian_positions(xlsx_path: Path) -> List[Dict[str, Any]]:
    """
    Reads custodian_positions.xlsx using standard library zipfile and XML parser.
    Ensures complete independence from heavy third-party excel libraries.
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Custodian positions file not found at: {xlsx_path}")
    
    with zipfile.ZipFile(xlsx_path) as z:
        # 1. Parse shared strings if present
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in tree.findall("m:si", ns):
                texts = [t.text for t in si.findall(".//m:t", ns) if t.text]
                shared_strings.append("".join(texts))
        
        # 2. Parse primary worksheet
        sheet_xml = z.read("xl/worksheets/sheet1.xml")
        tree = ET.fromstring(sheet_xml)
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        
        raw_rows = []
        for r in tree.findall(".//m:row", ns):
            row_idx = int(r.attrib.get("r", "0"))
            cells = []
            for c in r.findall("m:c", ns):
                t = c.attrib.get("t")
                v = c.find("m:v", ns)
                is_t = c.find("m:is/m:t", ns)
                
                if is_t is not None and is_t.text is not None:
                    val = is_t.text
                elif v is not None and v.text is not None:
                    if t == "s" and shared_strings:
                        val = shared_strings[int(v.text)]
                    else:
                        val = v.text
                else:
                    val = ""
                cells.append(val)
            raw_rows.append((row_idx, cells))
            
        if not raw_rows:
            return []
        
        headers = raw_rows[0][1]
        data_rows = []
        for row_idx, cells in raw_rows[1:]:
            # Map headers to values
            row_dict = dict(zip(headers, cells))
            row_dict["_source_file"] = str(xlsx_path)
            row_dict["_source_row"] = row_idx
            data_rows.append(row_dict)
            
        return data_rows

def read_notion_clients(notion_dir: Path) -> List[Dict[str, Any]]:
    """
    Finds and parses Clients*.csv and binds each record to its associated
    page Markdown file located in the adjacent Notion folder.
    """
    csv_candidates = list(notion_dir.glob("Clients*.csv"))
    if not csv_candidates:
        raise FileNotFoundError(f"No Clients*.csv found under {notion_dir}")
    clients_csv = csv_candidates[0]
    
    # Locate page bodies folder
    folder_candidates = [d for d in notion_dir.glob("Clients*") if d.is_dir()]
    page_folder = folder_candidates[0] if folder_candidates else None
    
    client_records = []
    with open(clients_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            record = dict(row)
            record["_source_file"] = str(clients_csv)
            record["_source_row"] = row_idx
            record["_page_body"] = ""
            record["_page_file"] = ""
            
            # Find corresponding Markdown page body
            client_name = record.get("Name", "").strip()
            if page_folder and client_name:
                # Notion export files are typically named: "<Name> <hash>.md"
                # Search for files starting with client_name or sanitized name
                matched_pages = list(page_folder.glob(f"{glob.escape(client_name)}*.md"))
                if not matched_pages:
                    # Try partial match (e.g. commas or special chars)
                    first_part = client_name.split(",")[0].strip()
                    matched_pages = list(page_folder.glob(f"*{glob.escape(first_part)}*.md"))
                
                if matched_pages:
                    page_path = matched_pages[0]
                    try:
                        with open(page_path, "r", encoding="utf-8") as pf:
                            record["_page_body"] = pf.read().strip()
                            record["_page_file"] = str(page_path)
                    except Exception:
                        pass
            
            client_records.append(record)
            
    return client_records

def read_notion_meetings(notion_dir: Path) -> List[Dict[str, Any]]:
    """
    Finds and parses Meetings*.csv and binds each record to its associated
    page Markdown notes.
    """
    csv_candidates = list(notion_dir.glob("Meetings*.csv"))
    if not csv_candidates:
        raise FileNotFoundError(f"No Meetings*.csv found under {notion_dir}")
    meetings_csv = csv_candidates[0]
    
    folder_candidates = [d for d in notion_dir.glob("Meetings*") if d.is_dir()]
    page_folder = folder_candidates[0] if folder_candidates else None
    
    meeting_records = []
    with open(meetings_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            record = dict(row)
            record["_source_file"] = str(meetings_csv)
            record["_source_row"] = row_idx
            record["_page_body"] = ""
            record["_page_file"] = ""
            
            meeting_name = record.get("Name", "").strip()
            if page_folder and meeting_name:
                # Match by full meeting name first (e.g. "Intro Call — Fairbanks *.md")
                matched = list(page_folder.glob(f"{glob.escape(meeting_name)}*.md"))
                if not matched:
                    # Fallback to client name match
                    client_name = record.get("Client", "").strip()
                    if client_name:
                        matched = list(page_folder.glob(f"*{glob.escape(client_name)}*.md"))
                if matched:
                    page_path = matched[0]
                    try:
                        with open(page_path, "r", encoding="utf-8") as pf:
                            record["_page_body"] = pf.read().strip()
                            record["_page_file"] = str(page_path)
                    except Exception:
                        pass
            
            meeting_records.append(record)
            
    return meeting_records

def read_slack_thread(slack_path: Path) -> str:
    """Reads ops_slack_thread.md content."""
    if not slack_path.exists():
        raise FileNotFoundError(f"Slack thread not found at: {slack_path}")
    with open(slack_path, mode="r", encoding="utf-8") as f:
        return f.read().strip()
