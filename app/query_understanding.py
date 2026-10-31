from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any


class QueryIntent(str, Enum):
    ENTITY_PROFILE = "ENTITY_PROFILE"
    ENTITY_FIELD = "ENTITY_FIELD"
    COMPARISON = "COMPARISON"
    RANKING = "RANKING"
    STATISTICS = "STATISTICS"
    SUMMARY = "SUMMARY"
    LIST = "LIST"
    EXPLANATION = "EXPLANATION"
    GENERAL_QA = "GENERAL_QA"


class AnswerFormat(str, Enum):
    TABLE = "TABLE"
    COMPARISON_TABLE = "COMPARISON_TABLE"
    RANKED_TABLE = "RANKED_TABLE"
    PARAGRAPH = "PARAGRAPH"
    LIST = "LIST"
    SUMMARY = "SUMMARY"
    STATISTICS = "STATISTICS"


@dataclass
class NormalizedQuery:
    original_query: str
    cleaned_query: str
    intent: QueryIntent
    target_format: AnswerFormat
    entity_ids: list[str] = field(default_factory=list)
    target_field: str | None = None
    ranking_metric: str | None = None
    ranking_direction: str = "desc"  # "desc" or "asc"
    ranking_limit: int = 10
    stat_metric: str | None = None
    stat_func: str | None = None  # "avg", "sum", "count", "min", "max"
    filter_field: str | None = None
    filter_value: str | None = None


# Known attributes/fields in employee and structured records
FIELD_SYNONYMS: dict[str, list[str]] = {
    "Experience": ["experience", "exp", "years of experience", "work experience", "tenure"],
    "Projects Completed": ["projects completed", "projects", "proj", "project count", "completed projects", "number of projects"],
    "Salary": ["salary", "compensation", "pay", "ctc", "earnings", "income"],
    "Rating": ["rating", "score", "performance rating", "review rating"],
    "Department": ["department", "dept", "division", "team", "unit"],
    "Job Role": ["job role", "role", "designation", "position", "title", "job title"],
    "Skills": ["skills", "skillset", "technologies", "tech stack", "tools"],
    "Qualification": ["qualification", "degree", "education", "qual"],
    "Joined": ["joined", "join year", "joining year", "year joined", "start year"],
    "Type": ["type", "employment type", "contract type", "job type"],
    "Location": ["location", "city", "place", "work location", "office"],
    "Email": ["email", "email address", "mail"],
    "Phone": ["phone", "phone number", "contact", "mobile", "contact number"],
    "Age": ["age", "how old"],
    "Name": ["name", "full name", "employee name"],
}


class QueryUnderstandingEngine:
    """Intelligent Query Understanding and Intent Detection Engine."""

    def __init__(self):
        # Regular expressions for entity identifiers such as EMP001, EMP025, ID123, etc.
        self._entity_id_regex = re.compile(r"\b([A-Za-z]{2,5}\d{2,6})\b", re.IGNORECASE)

    def analyze(self, query: str) -> NormalizedQuery:
        clean_q = query.strip()

        # 1. Extract entity identifiers (case-insensitive, normalized to UPPERCASE)
        raw_ids = self._entity_id_regex.findall(clean_q)
        # Preserve order while deduplicating
        seen_ids = set()
        entity_ids = []
        for rid in raw_ids:
            uid = rid.upper()
            if uid not in seen_ids:
                seen_ids.add(uid)
                entity_ids.append(uid)

        q_lower = clean_q.lower()

        # 2. Comparison detection
        is_comparison = bool(
            re.search(r"\b(?:compare|comparison|versus|vs\.?|difference\s+between|differences|relative\s+to|who\s+has\s+more|which\s+one\s+has\s+more)\b", q_lower)
            or (len(entity_ids) >= 2 and ("and" in q_lower or "or" in q_lower or "vs" in q_lower or "between" in q_lower))
        )
        if is_comparison:
            comp_metric = self._detect_metric(q_lower)
            return NormalizedQuery(
                original_query=clean_q,
                cleaned_query=self._clean_conversational_prefixes(clean_q),
                intent=QueryIntent.COMPARISON,
                target_format=AnswerFormat.COMPARISON_TABLE,
                entity_ids=entity_ids,
                ranking_metric=comp_metric,
            )

        # 3. Ranking / Extremum detection (Highest, Lowest, Top N, Bottom N, Most, Least)
        rank_match = re.search(
            r"\b(?:who\s+has\s+the\s+|which\s+employee\s+has\s+the\s+|show\s+(?:the\s+)?top\s+(\d+)?|top\s+(\d+)|bottom\s+(\d+)|highest|lowest|maximum|max|minimum|min|most|least|best|worst|ranked?)\b",
            q_lower,
        )
        if rank_match:
            direction = "desc"
            if re.search(r"\b(?:lowest|minimum|min|least|worst|bottom)\b", q_lower):
                direction = "asc"

            # Determine limit (e.g. top 10 -> limit 10; "who has highest" -> limit 1)
            limit = 10
            for g in rank_match.groups():
                if g and g.isdigit():
                    limit = int(g)
                    break
            if re.search(r"\b(?:who\s+has\s+the|which\s+(?:one|employee|person)\s+has)\b", q_lower):
                limit = 1

            # Determine ranking metric
            metric = self._detect_metric(q_lower)
            if metric:
                return NormalizedQuery(
                    original_query=clean_q,
                    cleaned_query=self._clean_conversational_prefixes(clean_q),
                    intent=QueryIntent.RANKING,
                    target_format=AnswerFormat.RANKED_TABLE,
                    ranking_metric=metric,
                    ranking_direction=direction,
                    ranking_limit=limit,
                )

        # 4. Statistics / Aggregation detection (Average, mean, sum, total, count)
        stat_match = re.search(
            r"\b(?:average|avg|mean|total|sum\s+of|count\s+of|how\s+many\s+employees|number\s+of\s+employees)\b",
            q_lower,
        )
        if stat_match:
            func = "avg"
            if re.search(r"\b(?:total|sum)\b", q_lower):
                func = "sum"
            elif re.search(r"\b(?:how\s+many|count|number\s+of)\b", q_lower):
                func = "count"

            metric = self._detect_metric(q_lower) or "Employee ID"
            return NormalizedQuery(
                original_query=clean_q,
                cleaned_query=self._clean_conversational_prefixes(clean_q),
                intent=QueryIntent.STATISTICS,
                target_format=AnswerFormat.STATISTICS,
                stat_metric=metric,
                stat_func=func,
            )

        # 5. Entity Specific Queries
        if entity_ids:
            # Check if asking for a specific field/attribute:
            # e.g., "What is the experience of EMP001?", "EMP001 salary"
            target_field = self._detect_target_field(q_lower)

            # If user asks for general profile/history/details/overview:
            # "Show me the history of EMP001", "Tell me about EMP001", "EMP001 profile", "EMP001", etc.
            is_general_profile = bool(
                re.search(
                    r"\b(?:history|profile|details|about|information|info|record|overview|complete|all)\b",
                    q_lower,
                )
                or not target_field
            )

            if is_general_profile or target_field == "Profile":
                return NormalizedQuery(
                    original_query=clean_q,
                    cleaned_query=f"{entity_ids[0]} complete profile history",
                    intent=QueryIntent.ENTITY_PROFILE,
                    target_format=AnswerFormat.TABLE,
                    entity_ids=entity_ids,
                )
            else:
                return NormalizedQuery(
                    original_query=clean_q,
                    cleaned_query=self._clean_conversational_prefixes(clean_q),
                    intent=QueryIntent.ENTITY_FIELD,
                    target_format=AnswerFormat.PARAGRAPH,
                    entity_ids=entity_ids,
                    target_field=target_field,
                )

        # 6. Summary detection
        if re.search(r"\b(?:summarize|summary\s+of|give\s+a\s+summary|brief\s+overview|executive\s+summary)\b", q_lower):
            return NormalizedQuery(
                original_query=clean_q,
                cleaned_query=self._clean_conversational_prefixes(clean_q),
                intent=QueryIntent.SUMMARY,
                target_format=AnswerFormat.SUMMARY,
            )

        # 7. List detection
        if re.search(r"\b(?:list\s+the|give\s+me\s+a\s+list|enumerate|what\s+are\s+the\s+types|types\s+of|categories\s+of)\b", q_lower):
            return NormalizedQuery(
                original_query=clean_q,
                cleaned_query=self._clean_conversational_prefixes(clean_q),
                intent=QueryIntent.LIST,
                target_format=AnswerFormat.LIST,
            )

        # 8. General explanation / definition
        if re.search(r"\b(?:what\s+is|what\s+are|define|definition|explain|how\s+does|why\s+do|overview)\b", q_lower):
            return NormalizedQuery(
                original_query=clean_q,
                cleaned_query=self._clean_conversational_prefixes(clean_q),
                intent=QueryIntent.EXPLANATION,
                target_format=AnswerFormat.PARAGRAPH,
            )

        # Default fallback
        return NormalizedQuery(
            original_query=clean_q,
            cleaned_query=clean_q,
            intent=QueryIntent.GENERAL_QA,
            target_format=AnswerFormat.PARAGRAPH,
        )

    def _clean_conversational_prefixes(self, text: str) -> str:
        pattern = r"^(?:can\s+you\s+(?:please\s+)?(?:tell\s+me|show\s+me|give\s+me|explain)|please\s+show\s+me|please\s+tell\s+me|show\s+me(?:\s+the)?|tell\s+me\s+about|give\s+me(?:\s+the)?|what\s+information\s+is\s+available\s+about|i\s+want\s+to\s+know(?:\s+about)?)\s+"
        cleaned = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE)
        return cleaned.strip("?. ")

    def _detect_metric(self, query: str) -> str | None:
        for field_name, synonyms in FIELD_SYNONYMS.items():
            if field_name in ["Experience", "Projects Completed", "Salary", "Rating", "Age"]:
                for syn in synonyms:
                    if re.search(r"\b" + re.escape(syn) + r"\b", query):
                        return field_name
        return None

    def _detect_target_field(self, query: str) -> str | None:
        # 1. Check against known specific attribute synonyms
        for field_name, synonyms in FIELD_SYNONYMS.items():
            for syn in synonyms:
                if re.search(r"\b" + re.escape(syn) + r"\b", query):
                    return field_name

        # 2. Extract arbitrary field requested (including missing fields like "passport number" or "manager")
        match = re.search(
            r"\b(?:what\s+is\s+(?:the\s+)?|who\s+is\s+(?:the\s+)?|show\s+(?:the\s+)?)([a-z\s]{3,35}?)\s+(?:of|for)\s+",
            query.lower(),
        )
        if match:
            candidate = match.group(1).strip()
            if candidate not in {"history", "profile", "details", "information", "info", "record", "overview", "all"}:
                return candidate.title()

        return None


query_understanding_engine = QueryUnderstandingEngine()
