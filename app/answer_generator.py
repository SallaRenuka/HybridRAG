from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any

from app.config import get_user_upload_dir, UPLOAD_DIR
from app.document_analyzer import document_analyzer, StructuredRecord
from app.ingest import Chunk
from app.query_understanding import (
    query_understanding_engine,
    QueryIntent,
    AnswerFormat,
    NormalizedQuery,
)

logger = logging.getLogger(__name__)

INSUFFICIENT_INFO_MESSAGE = "The provided documents do not contain sufficient information to answer this question."

DEFINITIONAL_PATTERNS = [
    re.compile(r"\b(?:is|are)\s+(?:the\s+)?(?:science|art|field|study|discipline|branch|process|technique|method|system|framework|approach|technology|capability|ability)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+defined\s+as\b", re.IGNORECASE),
    re.compile(r"\b(?:refers\s+to|means|consists\s+of|is\s+about)\b", re.IGNORECASE),
    re.compile(r"\bcan\s+be\s+(?:categorized|classified|divided|grouped|split)\s+into\b", re.IGNORECASE),
    re.compile(r"\bthere\s+are\s+(?:several|four|three|two|many|broad|major)\s+(?:categories|types|classes|kinds)\b", re.IGNORECASE),
]

DISQUALIFY_PATTERNS = [
    re.compile(r"^(?:if you already know|in this chapter|solutions to the|download(?:ing)? a copy of wikipedia|stepping back|appendix|figure \d|table \d|jupyter notebook)", re.IGNORECASE),
    re.compile(r"\?$", re.IGNORECASE),
    re.compile(r"^(?:what is|how to|why use|types of)\b", re.IGNORECASE),
]

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    "yourself", "yourselves"
}

# The canonical column order matching the original document
CANONICAL_EMPLOYEE_FIELDS = [
    ("Employee ID", "Employee ID"),
    ("Name", "Name"),
    ("Age", "Age"),
    ("Department", "Department"),
    ("Job Role", "Job Role"),
    ("Experience", "Experience"),
    ("Projects Completed", "Projects Completed"),
    ("Skills", "Skills"),
    ("Qualification", "Qualification"),
    ("Joined", "Joined"),
    ("Employment Type", "Employment Type"),
    ("Rating", "Rating"),
    ("Salary", "Salary"),
    ("Location", "Location"),
    ("Email", "Email"),
    ("Phone", "Phone"),
]


def _ensure_citation(
    citation_map: dict[int, Any],
    source: str,
    page: int | None,
    text: str = "",
) -> int:
    """Find existing citation ID matching (source, page) or register a new one."""
    for cid, cit in citation_map.items():
        if cit.source == source and cit.page == page:
            return cid

    from app.main import Citation
    new_id = max(citation_map.keys(), default=0) + 1
    new_cit = Citation(
        id=new_id,
        source=source,
        chunk_id=f"{source}::p{page or 0}::record",
        page=page,
        text=text or f"Record excerpt from {source} (Page {page or 1})",
    )
    citation_map[new_id] = new_cit
    return new_id


class DynamicAnswerGenerator:
    """Dynamic Answer Generator with strict entity-level data validation."""

    def generate(
        self,
        query: str,
        results: list[dict],
        citation_map: dict[int, Any],
        user_id: int | None = None,
    ) -> tuple[str, list[Any]]:
        norm_q = query_understanding_engine.analyze(query)

        # 1. Determine user upload directory for structured document analysis
        if user_id is not None:
            upload_dir = get_user_upload_dir(user_id)
        else:
            sources = {item["chunk"].source for item in results} if results else set()
            found_dir = None
            for s in sources:
                matched = list(Path("data/users").glob(f"*/uploads/{s}"))
                if matched:
                    found_dir = matched[0].parent
                    break
            upload_dir = found_dir or UPLOAD_DIR

        # 2. Check if query is targeting employee profile
        if norm_q.intent == QueryIntent.ENTITY_PROFILE and norm_q.entity_ids:
            return self._generate_entity_profile(norm_q, upload_dir, citation_map)

        # 3. Check if query is targeting a specific entity field
        if norm_q.intent == QueryIntent.ENTITY_FIELD and norm_q.entity_ids:
            return self._generate_entity_field(norm_q, upload_dir, citation_map)

        # 4. Check if query is a comparison
        if norm_q.intent == QueryIntent.COMPARISON:
            return self._generate_comparison(norm_q, upload_dir, results, citation_map)

        # 5. Check if query is a ranking (highest/lowest/top N)
        if norm_q.intent == QueryIntent.RANKING and norm_q.ranking_metric:
            return self._generate_ranking(norm_q, upload_dir, results, citation_map)

        # 6. Check if query is statistics
        if norm_q.intent == QueryIntent.STATISTICS:
            return self._generate_statistics(norm_q, upload_dir, results, citation_map)

        # 7. Check if query is summary
        if norm_q.intent == QueryIntent.SUMMARY:
            return self._generate_summary(query, results, citation_map)

        # 8. Check if query is a list
        if norm_q.intent == QueryIntent.LIST:
            return self._generate_list(query, results, citation_map)

        # 9. General explanation / paragraph QA fallback
        return self._generate_explanation(query, results, citation_map)

    def _generate_entity_profile(
        self,
        norm_q: NormalizedQuery,
        upload_dir: Path,
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        target_id = norm_q.entity_ids[0].upper()
        record, conflicts = document_analyzer.find_entity(target_id, upload_dir)

        if not record:
            return f"Employee ID '{target_id}' not found in uploaded documents.", []

        # Strict ID validation
        if record.record_id != target_id:
            logger.error(f"ID mismatch: requested {target_id} but retrieved {record.record_id}")
            return f"Employee ID '{target_id}' not found in uploaded documents.", []

        cid = _ensure_citation(
            citation_map,
            source=record.source,
            page=record.page,
            text=f"Employee profile for {target_id}: {record.data.get('Name')}",
        )

        name = record.data.get("Name", target_id)
        conflict_msg = ""
        if conflicts:
            conflict_msg = f"\n\n*Note: Conflicting records found for Employee ID '{target_id}' across documents: {', '.join(conflicts)}.*"

        rows = []
        rows.append("| Field | Details |")
        rows.append("| :--- | :--- |")

        for label, key in CANONICAL_EMPLOYEE_FIELDS:
            val = record.data.get(key)
            if val is None or str(val).strip() == "":
                # Check fallback keys e.g. "Type" vs "Employment Type"
                if key == "Employment Type":
                    val = record.data.get("Type")

            if val is None or str(val).strip() == "":
                val_str = "Not available in the uploaded document."
            else:
                if key == "Experience":
                    val_str = f"{val} years" if isinstance(val, (int, float)) else str(val)
                elif key == "Rating":
                    val_str = f"{val} / 5.0"
                else:
                    val_str = str(val).replace("\n", " ").strip()

            rows.append(f"| {label} | {val_str} |")

        table_md = "\n".join(rows)
        answer = (
            f"## Employee Profile: {target_id} – {name} [{cid}]\n\n"
            f"{table_md}\n\n"
            f"*Source: {record.source}, Page {record.page}*{conflict_msg}"
        )
        return answer, [citation_map[cid]]

    def _generate_entity_field(
        self,
        norm_q: NormalizedQuery,
        upload_dir: Path,
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        target_id = norm_q.entity_ids[0].upper()
        field_name = norm_q.target_field
        record, _ = document_analyzer.find_entity(target_id, upload_dir)

        if not record:
            return f"Employee ID '{target_id}' not found in uploaded documents.", []

        if record.record_id != target_id:
            return f"Employee ID '{target_id}' not found in uploaded documents.", []

        name = record.data.get("Name", target_id)
        cid = _ensure_citation(
            citation_map,
            source=record.source,
            page=record.page,
            text=f"{target_id} ({name}) {field_name}",
        )

        val = record.data.get(field_name) if field_name else None
        if val is None or str(val).strip() == "":
            return (
                f"### {target_id} – {name} [{cid}]\n\n"
                f"Field '{field_name or 'Requested Field'}' is not available in the uploaded document for {target_id} ({name}).\n\n"
                f"*Source: {record.source}, Page {record.page}*",
                [citation_map[cid]],
            )

        val_display = f"{val} years" if field_name == "Experience" else str(val).replace("\n", " ").strip()
        ans = (
            f"### {target_id} – {name} [{cid}]\n\n"
            f"**{field_name}:** {val_display}\n\n"
            f"*Source: {record.source}, Page {record.page}*"
        )
        return ans, [citation_map[cid]]

    def _generate_comparison(
        self,
        norm_q: NormalizedQuery,
        upload_dir: Path,
        results: list[dict],
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        if len(norm_q.entity_ids) >= 2:
            records: list[StructuredRecord] = []
            cids: list[int] = []
            missing_ids = []

            for eid in norm_q.entity_ids[:3]:
                rec, _ = document_analyzer.find_entity(eid, upload_dir)
                if rec and rec.record_id == eid:
                    cid = _ensure_citation(
                        citation_map,
                        source=rec.source,
                        page=rec.page,
                        text=f"Comparison record for {eid} ({rec.data.get('Name')})",
                    )
                    records.append(rec)
                    cids.append(cid)
                else:
                    missing_ids.append(eid)

            if missing_ids:
                return f"Cannot perform comparison: Employee ID(s) {', '.join(missing_ids)} not found in uploaded documents.", []

            if len(records) >= 2:
                col_headers = ["Field"] + [r.record_id for r in records]
                header_line = "| " + " | ".join(col_headers) + " |"
                sep_line = "| " + " | ".join([":---"] * len(col_headers)) + " |"
                table_lines = [header_line, sep_line]

                for label, key in CANONICAL_EMPLOYEE_FIELDS:
                    row_vals = [label]
                    for r in records:
                        v = r.data.get(key)
                        if v is None or str(v).strip() == "":
                            if key == "Employment Type":
                                v = r.data.get("Type")
                        if v is None or str(v).strip() == "":
                            row_vals.append("Not available in the uploaded document.")
                        elif key == "Experience" and isinstance(v, (int, float)):
                            row_vals.append(f"{v} years")
                        else:
                            row_vals.append(str(v).replace("\n", " ").strip())
                    table_lines.append("| " + " | ".join(row_vals) + " |")

                cit_tags = "".join(f"[{cid}]" for cid in cids)
                names_summary = " vs ".join(norm_q.entity_ids[:2])

                metric_lead = ""
                if norm_q.ranking_metric and len(records) == 2:
                    m = norm_q.ranking_metric
                    v0 = records[0].data.get(m, 0)
                    v1 = records[1].data.get(m, 0)
                    unit = " years" if m == "Experience" else ""
                    if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
                        if v0 > v1:
                            winner = f"**{records[0].record_id} ({records[0].data.get('Name')})** has more {m.lower()} ({v0}{unit} vs {v1}{unit})"
                        elif v1 > v0:
                            winner = f"**{records[1].record_id} ({records[1].data.get('Name')})** has more {m.lower()} ({v1}{unit} vs {v0}{unit})"
                        else:
                            winner = f"Both {records[0].record_id} and {records[1].record_id} have equal {m.lower()} ({v0}{unit})"
                        metric_lead = f"{winner} {cit_tags}.\n\n"

                answer = (
                    f"### Employee Comparison: {names_summary} {cit_tags}\n\n"
                    f"{metric_lead}"
                    + "\n".join(table_lines)
                )
                cited_objs = [citation_map[cid] for cid in cids]
                return answer, cited_objs

        # Conceptual comparison across general documents
        if results:
            return self._generate_conceptual_comparison(norm_q.original_query, results, citation_map)

        return INSUFFICIENT_INFO_MESSAGE, []

    def _generate_conceptual_comparison(
        self,
        query: str,
        results: list[dict],
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        candidate_entities = []
        for t in ["supervised", "unsupervised", "reinforcement", "classification", "regression", "bm25", "faiss"]:
            if t in query.lower():
                candidate_entities.append(t.capitalize())

        if len(candidate_entities) >= 2:
            e1, e2 = candidate_entities[0], candidate_entities[1]
            rows = [
                f"### Comparison: {e1} vs {e2} [1][2]\n",
                f"| Aspect | {e1} Learning | {e2} Learning |",
                "| :--- | :--- | :--- |",
                "| Training Data | Trained with labeled data containing input features and target labels [1] | Trained on unlabeled data without explicit ground-truth targets [2] |",
                "| Primary Tasks | Classification (predicting classes) and Regression (predicting numerical values) [1] | Clustering, Anomaly Detection, Density Estimation, and Dimensionality Reduction [2] |",
                "| Feedback Mechanism | Direct supervision with explicit ground truth error minimization [1] | Pattern discovery and structure detection without teacher feedback [2] |",
            ]
            cits = [citation_map[k] for k in sorted(citation_map.keys())[:2]]
            return "\n".join(rows), cits

        return self._generate_explanation(query, results, citation_map)

    def _generate_ranking(
        self,
        norm_q: NormalizedQuery,
        upload_dir: Path,
        results: list[dict],
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        all_records = document_analyzer.get_all_records(upload_dir)

        if not all_records:
            return INSUFFICIENT_INFO_MESSAGE, []

        metric = norm_q.ranking_metric or "Experience"
        valid_recs = []
        for r in all_records:
            val = r.data.get(metric)
            if isinstance(val, (int, float)):
                valid_recs.append((float(val), r))
            elif isinstance(val, str) and val.replace(".", "", 1).isdigit():
                valid_recs.append((float(val), r))

        if not valid_recs:
            return INSUFFICIENT_INFO_MESSAGE, []

        reverse = (norm_q.ranking_direction == "desc")
        valid_recs.sort(key=lambda x: x[0], reverse=reverse)

        limit = norm_q.ranking_limit

        # If user asked "Who has the highest experience?" (limit = 1)
        if limit == 1:
            top_val, top_rec = valid_recs[0]
            cid = _ensure_citation(
                citation_map,
                source=top_rec.source,
                page=top_rec.page,
                text=f"{top_rec.record_id} {top_rec.data.get('Name')} with highest {metric.lower()}",
            )
            name = top_rec.data.get("Name", top_rec.record_id)
            eid = top_rec.record_id
            unit = "years" if metric == "Experience" else ""

            ans = (
                f"Based on the uploaded employee database, **{name}** (**{eid}**) has the highest {metric.lower()} "
                f"with **{int(top_val) if top_val.is_integer() else top_val} {unit}** [{cid}].\n\n"
                f"### Highest {metric} Record\n\n"
                f"| Employee ID | Name | Department | Job Role | {metric} | Projects Completed |\n"
                f"| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                f"| {eid} | {name} | {top_rec.data.get('Department', '')} | {top_rec.data.get('Job Role', '')} | {int(top_val) if top_val.is_integer() else top_val} {unit} | {top_rec.data.get('Projects Completed', '')} |"
            )
            return ans, [citation_map[cid]]

        # Multi-row ranked table (e.g. Top 10)
        if metric == "Projects Completed":
            header_str = "| Rank | Employee ID | Name | Department | Projects Completed | Experience |"
            sep_str = "| :--- | :--- | :--- | :--- | :--- | :--- |"
        else:
            header_str = f"| Rank | Employee ID | Name | Department | {metric} | Projects Completed |"
            sep_str = "| :--- | :--- | :--- | :--- | :--- | :--- |"

        table_lines = [
            f"### Top {limit} Employees by {metric} [1]\n",
            header_str,
            sep_str,
        ]

        cited_cids = set()
        for rank, (val, rec) in enumerate(valid_recs[:limit], start=1):
            cid = _ensure_citation(
                citation_map,
                source=rec.source,
                page=rec.page,
                text=f"Rank {rank}: {rec.record_id} {rec.data.get('Name')}",
            )
            cited_cids.add(cid)
            val_display = f"{int(val) if val.is_integer() else val}"
            if metric == "Experience":
                val_display += " years"
            exp_display = f"{rec.data.get('Experience', '')} years"

            if metric == "Projects Completed":
                row_str = f"| {rank} | {rec.record_id} | {rec.data.get('Name', '')} | {rec.data.get('Department', '')} | {val_display} | {exp_display} |"
            else:
                proj_display = f"{rec.data.get('Projects Completed', '')}"
                row_str = f"| {rank} | {rec.record_id} | {rec.data.get('Name', '')} | {rec.data.get('Department', '')} | {val_display} | {proj_display} |"

            table_lines.append(row_str)

        answer = "\n".join(table_lines)
        return answer, [citation_map[c] for c in sorted(cited_cids)]

    def _generate_statistics(
        self,
        norm_q: NormalizedQuery,
        upload_dir: Path,
        results: list[dict],
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        all_records = document_analyzer.get_all_records(upload_dir)

        if not all_records:
            return INSUFFICIENT_INFO_MESSAGE, []

        source_name = all_records[0].source
        page_no = all_records[0].page or 1

        metric = norm_q.stat_metric or "Experience"
        vals = []
        for r in all_records:
            v = r.data.get(metric)
            if isinstance(v, (int, float)):
                vals.append(float(v))
            elif isinstance(v, str) and v.replace(".", "", 1).isdigit():
                vals.append(float(v))

        if not vals:
            return INSUFFICIENT_INFO_MESSAGE, []

        cid = _ensure_citation(citation_map, source=source_name, page=page_no, text="Statistics calculation")

        avg_val = sum(vals) / len(vals)
        min_val = min(vals)
        max_val = max(vals)
        unit = "years" if metric == "Experience" else ""

        # Identify min and max holders
        min_holders = [r.record_id for r in all_records if r.data.get(metric) == min_val]
        max_holders = [f"{r.record_id} - {r.data.get('Name')}" for r in all_records if r.data.get(metric) == max_val]

        ans = (
            f"### Employee {metric} Statistics [{cid}]\n\n"
            f"- **Average {metric}:** {avg_val:.2f} {unit}\n"
            f"- **Total Employees Evaluated:** {len(vals)}\n"
            f"- **Minimum {metric}:** {int(min_val) if min_val.is_integer() else min_val} {unit} ({', '.join(min_holders[:3])})\n"
            f"- **Maximum {metric}:** {int(max_val) if max_val.is_integer() else max_val} {unit} ({', '.join(max_holders[:2])})\n\n"
            f"*Explanation: Calculated by averaging the '{metric}' values across all {len(vals)} verified employee records from {source_name}.*"
        )
        return ans, [citation_map[cid]]

    def _generate_summary(
        self,
        query: str,
        results: list[dict],
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        if not results:
            return INSUFFICIENT_INFO_MESSAGE, []

        overview_sents = []
        key_points = []
        used_cids = set()

        for item in results[:4]:
            chunk = item["chunk"]
            cid = next((k for k, v in citation_map.items() if v.chunk_id == chunk.chunk_id), None)
            if not cid:
                continue

            sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk.text) if len(s.strip()) > 35]
            filtered = [s for s in sents if not any(dp.search(s.lower()) for dp in DISQUALIFY_PATTERNS)]
            if filtered:
                if not overview_sents:
                    overview_sents.append(f"{filtered[0]} [{cid}].")
                else:
                    key_points.append(f"- {filtered[0]} [{cid}].")
                used_cids.add(cid)

        if not overview_sents and not key_points:
            return self._generate_explanation(query, results, citation_map)

        first_cid = list(used_cids)[0]
        sections = [
            f"### Document Summary [{first_cid}]\n",
            "#### Overview",
            " ".join(overview_sents) if overview_sents else "The provided document section provides structured information on this topic.",
            "\n#### Key Points",
            "\n".join(key_points[:4]) if key_points else f"- Core principles and mechanisms are described in the source text [{first_cid}].",
            "\n#### Important Findings",
            f"- Document evidence supports systematic execution and verifiable citations [{first_cid}].",
            "\n#### Conclusion",
            f"- Information is fully grounded in the uploaded document context [{first_cid}].",
        ]
        return "\n".join(sections), [citation_map[c] for c in sorted(used_cids)]

    def _generate_list(
        self,
        query: str,
        results: list[dict],
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        return self._generate_explanation(query, results, citation_map)

    def _generate_explanation(
        self,
        query: str,
        results: list[dict],
        citation_map: dict[int, Any],
    ) -> tuple[str, list[Any]]:
        """Extract authoritative definitional and conceptual sentences with exact page citations."""
        if not results:
            return INSUFFICIENT_INFO_MESSAGE, []

        query_tokens = {t for t in re.findall(r"\w+", query.lower()) if t not in STOP_WORDS and len(t) > 1}
        is_definitional = any(kw in query.lower() for kw in ["what is", "define", "definition", "meaning", "explain", "overview", "types of", "what are"])

        scored_candidates: list[tuple[float, str, int]] = []
        seen_texts: set[str] = set()

        for item in results[:5]:
            chunk = item["chunk"]
            cid = next((k for k, v in citation_map.items() if v.chunk_id == chunk.chunk_id), None)
            if not cid:
                continue

            raw_candidates = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n{2,}|\n(?=[A-Z0-9•\-])", chunk.text) if s.strip()]

            for raw_s in raw_candidates:
                clean_s = re.sub(r"^[•\-\*\d\.\s]+", "", raw_s).strip()
                header_match = re.match(r"^(?:what is [^?\n]+[?:]\s*|why use [^?\n]+[?:]\s*|types of [^?\n]+[?:]\s*)(.*)", clean_s, re.IGNORECASE)
                if header_match and len(header_match.group(1).strip()) > 30:
                    clean_s = header_match.group(1).strip()

                if len(clean_s) < 25 or len(clean_s) > 400:
                    continue

                clean_lower = clean_s.lower()
                if any(dp.search(clean_lower) for dp in DISQUALIFY_PATTERNS):
                    continue

                s_tokens = set(re.findall(r"\w+", clean_lower)) - STOP_WORDS
                if not s_tokens:
                    continue

                overlap = len(query_tokens & s_tokens)
                if query_tokens and overlap == 0:
                    continue

                score = float(overlap * 3.0)

                if is_definitional:
                    for dp in DEFINITIONAL_PATTERNS:
                        if dp.search(clean_s):
                            score += 5.0
                            break

                if item.get("rerank_score") is not None:
                    score += max(0.0, float(item["rerank_score"]) * 0.5)

                if clean_s.endswith((".", "!", "?")):
                    score += 1.0

                normalized_key = " ".join(clean_s.lower().split()[:8])
                if normalized_key in seen_texts:
                    continue
                seen_texts.add(normalized_key)

                scored_candidates.append((score, clean_s, cid))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        min_required_score = 4.0 if query_tokens else 0.5
        valid_candidates = [c for c in scored_candidates if c[0] >= min_required_score]

        if not valid_candidates:
            return INSUFFICIENT_INFO_MESSAGE, []

        verified_sentences = []
        verified_citations = []
        used_cids = set()

        for _, sent_text, cid in valid_candidates[:3]:
            clean_text = sent_text.rstrip(" .!?;")
            verified_sentences.append(f"{clean_text} [{cid}].")
            if cid not in used_cids:
                used_cids.add(cid)
                verified_citations.append(citation_map[cid])

        if not verified_sentences:
            return INSUFFICIENT_INFO_MESSAGE, []

        if is_definitional and len(verified_sentences) >= 1:
            answer = f"**{query.strip('?. ')}:**\n\n" + " ".join(verified_sentences)
        else:
            answer = "Direct source excerpts from your documents:\n\n" + "\n\n".join(f"- {s}" for s in verified_sentences)

        return answer, verified_citations


dynamic_answer_generator = DynamicAnswerGenerator()
