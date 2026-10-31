from __future__ import annotations

import csv
from dataclasses import dataclass, field
import io
import logging
from pathlib import Path
import re
from typing import Any

from pypdf import PdfReader

from app.config import UPLOAD_DIR

logger = logging.getLogger(__name__)

KNOWN_DEPTS = [
    "Software Development",
    "Data Science",
    "Cloud Computing",
    "Cybersecurity",
    "Finance",
    "HR",
    "AI/ML",
    "Marketing",
    "Sales",
    "Operations",
    "DevOps",
]

DEGREE_KEYWORDS = [
    "B.Sc",
    "M.Sc",
    "B.Tech",
    "M.Tech",
    "B.Com",
    "M.Com",
    "MBA",
    "MCA",
    "BBA",
    "BCA",
    "Ph.D",
]


@dataclass
class DocumentSection:
    heading: str
    level: int
    text: str
    page: int | None = None
    subsections: list[DocumentSection] = field(default_factory=list)


@dataclass
class StructuredRecord:
    data: dict[str, Any]
    source: str
    page: int | None
    record_id: str | None = None


@dataclass
class StructuredTable:
    title: str
    headers: list[str]
    records: list[StructuredRecord] = field(default_factory=list)
    source: str = ""
    page: int | None = None


@dataclass
class DocumentAnalysis:
    filename: str
    has_tables: bool = False
    has_paragraphs: bool = True
    has_headings: bool = False
    has_lists: bool = False
    tables: list[StructuredTable] = field(default_factory=list)
    sections: list[DocumentSection] = field(default_factory=list)
    entities: dict[str, StructuredRecord] = field(default_factory=dict)


class DocumentAnalyzer:
    """Deep Document Analysis Engine.

    Inspects uploaded documents to identify:
    - Tables and structured records (employees, transactions, specs)
    - Headings, subheadings, and section hierarchy
    - Paragraphs and explanatory text
    - Bulleted and numbered lists
    - Numerical data, entities (IDs, emails, phones), and statistics
    """

    def __init__(self):
        self._cached_analyses: dict[str, DocumentAnalysis] = {}

    def analyze_file(self, file_path: Path) -> DocumentAnalysis:
        cache_key = f"{file_path}_{file_path.stat().st_mtime if file_path.exists() else 0}"
        if cache_key in self._cached_analyses:
            return self._cached_analyses[cache_key]

        analysis = DocumentAnalysis(filename=file_path.name)
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".pdf":
                self._analyze_pdf(file_path, analysis)
            elif suffix in {".csv", ".tsv"}:
                self._analyze_delimited(file_path, analysis)
            elif suffix in {".txt", ".md"}:
                self._analyze_text(file_path, analysis)
        except Exception as exc:
            logger.warning(f"Error during deep document analysis of {file_path.name}: {exc}")

        self._cached_analyses[cache_key] = analysis
        return analysis

    def analyze_directory(self, directory: Path) -> list[DocumentAnalysis]:
        if not directory.exists():
            return []
        analyses = []
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".pdf", ".csv", ".tsv", ".txt", ".md"}:
                analyses.append(self.analyze_file(path))
        return analyses

    def find_entity(
        self, entity_id: str, upload_dir: Path | None = None
    ) -> tuple[StructuredRecord | None, list[str]]:
        """Exact entity lookup across uploaded documents.

        Detects duplicate IDs and returns (record, conflict_sources).
        """
        target_id = entity_id.strip().upper()
        target_dir = upload_dir if upload_dir is not None else UPLOAD_DIR
        analyses = self.analyze_directory(target_dir)

        matching_records: list[StructuredRecord] = []
        for da in analyses:
            if target_id in da.entities:
                matching_records.append(da.entities[target_id])

        if not matching_records:
            return None, []

        if len(matching_records) == 1:
            return matching_records[0], []

        # Multiple records found: check for conflicts
        first_rec = matching_records[0]
        sources = [r.source for r in matching_records]
        conflicts = []
        for other in matching_records[1:]:
            # If names or critical fields differ across sources, record conflict
            if (
                other.data.get("Name") != first_rec.data.get("Name")
                or other.data.get("Department") != first_rec.data.get("Department")
            ):
                conflicts = sources
                break

        return first_rec, conflicts

    def get_all_records(self, upload_dir: Path | None = None) -> list[StructuredRecord]:
        """Retrieve all structured records across uploaded documents, deduplicating by ID."""
        target_dir = upload_dir if upload_dir is not None else UPLOAD_DIR
        analyses = self.analyze_directory(target_dir)
        records_by_id: dict[str, StructuredRecord] = {}

        for da in analyses:
            for tbl in da.tables:
                for rec in tbl.records:
                    if rec.record_id:
                        rid = rec.record_id.upper()
                        if rid not in records_by_id:
                            records_by_id[rid] = rec

        return list(records_by_id.values())

    def _analyze_pdf(self, path: Path, analysis: DocumentAnalysis) -> None:
        reader = PdfReader(str(path))
        num_pages = len(reader.pages)
        full_text_pages: list[tuple[int, list[str]]] = []

        is_employee_db = False
        all_emp_indices_count = 0

        for pno, page in enumerate(reader.pages, start=1):
            txt = page.extract_text() or ""
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            full_text_pages.append((pno, lines))
            emp_ids = [l for l in lines if re.match(r"^EMP\d{3}$", l)]
            all_emp_indices_count += len(emp_ids)

        if all_emp_indices_count >= 5:
            is_employee_db = True

        if is_employee_db:
            table = self._parse_employee_pdf_table(path.name, full_text_pages)
            if table and table.records:
                analysis.has_tables = True
                analysis.tables.append(table)
                for rec in table.records:
                    if rec.record_id:
                        analysis.entities[rec.record_id.upper()] = rec

        # Also extract sections, headings, and lists for prose/mixed documents
        for pno, lines in full_text_pages:
            for line in lines:
                if re.match(r"^(?:#{1,4}\s+|Chapter\s+\d+|[A-Z0-9\.\s]{4,35}:?$)", line) and len(line) < 60:
                    analysis.has_headings = True
                if re.match(r"^[•\-\*]\s+|\b\d+\.\s+", line):
                    analysis.has_lists = True

    def _parse_employee_pdf_table(
        self, filename: str, pages_data: list[tuple[int, list[str]]]
    ) -> StructuredTable:
        headers = [
            "Employee ID",
            "Name",
            "Age",
            "Department",
            "Job Role",
            "Experience",
            "Projects Completed",
            "Skills",
            "Qualification",
            "Joined",
            "Employment Type",
            "Rating",
            "Salary",
            "Location",
            "Email",
            "Phone",
        ]
        table = StructuredTable(title="Employee Database", headers=headers, source=filename)

        for pno, lines in pages_data:
            emp_indices = [i for i, l in enumerate(lines) if re.match(r"^EMP\d{3}$", l)]
            for k, s_idx in enumerate(emp_indices):
                e_idx = emp_indices[k + 1] if k + 1 < len(emp_indices) else len(lines)
                rec_lines = lines[s_idx:e_idx]
                if not rec_lines:
                    continue

                emp_id = rec_lines[0]

                # Age is the first integer between 18 and 75
                age_idx = None
                for i in range(1, len(rec_lines)):
                    if rec_lines[i].isdigit() and 18 <= int(rec_lines[i]) <= 75:
                        age_idx = i
                        break
                if age_idx is None:
                    continue

                name = " ".join(rec_lines[1:age_idx])
                age = int(rec_lines[age_idx])
                phone = rec_lines[-1]

                # Salary line (contains currency symbol or number formatted with commas)
                salary_idx = None
                for idx_l, l in enumerate(rec_lines):
                    if re.search(r"[■₹$€£]?\s*[\d,]{6,}", l):
                        salary_idx = idx_l
                        break

                if salary_idx is not None and salary_idx >= 4:
                    salary = rec_lines[salary_idx].replace("■", "₹")
                    try:
                        rating = float(rec_lines[salary_idx - 1])
                    except ValueError:
                        rating = 0.0
                    rec_type = rec_lines[salary_idx - 2]
                    try:
                        joined = int(rec_lines[salary_idx - 3])
                    except ValueError:
                        joined = 0

                    loc_email_lines = rec_lines[salary_idx + 1 : -1]
                    location = loc_email_lines[0] if loc_email_lines else ""
                    email = "".join(loc_email_lines[1:]) if len(loc_email_lines) > 1 else ""

                    # Between age and joined:
                    mid = rec_lines[age_idx + 1 : salary_idx - 3]
                    int_indices = [i for i, v in enumerate(mid) if v.isdigit()]
                    if len(int_indices) >= 2:
                        exp_i, proj_i = int_indices[0], int_indices[1]
                        exp = int(mid[exp_i])
                        proj = int(mid[proj_i])
                        dept_role_lines = mid[:exp_i]
                        skills_qual_lines = mid[proj_i + 1 :]
                    else:
                        exp = 0
                        proj = 0
                        dept_role_lines = []
                        skills_qual_lines = mid

                    dept = ""
                    dept_str = " ".join(dept_role_lines)
                    for d in sorted(KNOWN_DEPTS, key=len, reverse=True):
                        if dept_str.startswith(d):
                            dept = d
                            role = dept_str[len(d) :].strip()
                            break
                    if not dept:
                        dept = dept_role_lines[0] if dept_role_lines else ""
                        role = " ".join(dept_role_lines[1:]) if len(dept_role_lines) > 1 else ""

                    qual_idx = None
                    for q_i, q_val in enumerate(skills_qual_lines):
                        if any(dk in q_val for dk in DEGREE_KEYWORDS):
                            qual_idx = q_i
                            break
                    if qual_idx is not None:
                        skills = " ".join(skills_qual_lines[:qual_idx])
                        qual = " ".join(skills_qual_lines[qual_idx:])
                    else:
                        skills = " ".join(skills_qual_lines[:-1]) if skills_qual_lines else ""
                        qual = skills_qual_lines[-1] if skills_qual_lines else ""

                    record_data = {
                        "Employee ID": emp_id,
                        "Name": name,
                        "Age": age,
                        "Department": dept,
                        "Job Role": role,
                        "Experience": exp,
                        "Projects Completed": proj,
                        "Skills": skills,
                        "Qualification": qual,
                        "Joined": joined,
                        "Employment Type": rec_type,
                        "Type": rec_type,
                        "Rating": rating,
                        "Salary": salary,
                        "Location": location,
                        "Email": email,
                        "Phone": phone,
                    }

                    s_rec = StructuredRecord(
                        data=record_data,
                        source=filename,
                        page=pno,
                        record_id=emp_id,
                    )
                    table.records.append(s_rec)

        return table

    def _analyze_delimited(self, path: Path, analysis: DocumentAnalysis) -> None:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        content = path.read_text(encoding="utf-8", errors="replace")
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            return

        headers = [h.strip() for h in rows[0] if h.strip()]
        if not headers:
            return

        table = StructuredTable(title=path.stem, headers=headers, source=path.name, page=1)
        analysis.has_tables = True

        for r_idx, row in enumerate(rows[1:], start=2):
            if not any(row):
                continue
            row_dict = {}
            rec_id = None
            for col_i, col_name in enumerate(headers):
                val = row[col_i].strip() if col_i < len(row) else ""
                row_dict[col_name] = val
                if not rec_id and re.match(r"^[A-Za-z0-9_-]{2,15}$", val):
                    rec_id = val

            rec = StructuredRecord(data=row_dict, source=path.name, page=1, record_id=rec_id)
            table.records.append(rec)
            if rec_id:
                analysis.entities[rec_id.upper()] = rec

        analysis.tables.append(table)

    def _analyze_text(self, path: Path, analysis: DocumentAnalysis) -> None:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            if re.match(r"^#{1,4}\s+", line):
                analysis.has_headings = True
            if re.match(r"^[•\-\*]\s+|\b\d+\.\s+", line):
                analysis.has_lists = True
            if line.strip().startswith("|") and line.strip().endswith("|"):
                analysis.has_tables = True


document_analyzer = DocumentAnalyzer()
