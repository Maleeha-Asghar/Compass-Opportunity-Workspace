from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from agents.deadline_extraction_agent import DeadlineExtractionAgent
from app.config import Settings, get_settings
from tools.extraction_llm import ExtractionLLM, coerce_extraction_llm
from tools.groq_tool import GroqClient
from tools.model_routing import ModelTask
from tools.prompt_budget import truncate_text
from tools.prompt_loader import render_prompt
from tools.scraper_tool import WebScraper
from tools.source_policy_gate import SourcePolicyGate
from tools.web_search_tool import SearchProvider


class DeadlineVerifierAgent:
    VAGUE_DEADLINE_TERMS = ("varies", "rolling", "see website", "not listed", "tba", "to be announced")
    DEADLINE_TERMS = ("deadline", "closing date", "applications close", "application dates", "admission dates")
    SUPPORTING_DEADLINE_DOMAINS = (
        "yocket.com",
        "scholarshiproar.com",
        "scholarshipsads.com",
        "wemakescholars.com",
        "scholarshipdb.net",
    )
    OFFICIAL_SOURCE_MIN_CONFIDENCE = 0.68
    THIRD_PARTY_MAX_CONFIDENCE = 0.54

    def __init__(
        self,
        *,
        search_provider: SearchProvider,
        scraper: WebScraper,
        settings: Settings | None = None,
        client: GroqClient | ExtractionLLM | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.search_provider = search_provider
        self.scraper = scraper
        self.llm = coerce_extraction_llm(client, self.settings)
        self.deadline_agent = DeadlineExtractionAgent(self.settings, llm=self.llm)

    def should_verify(self, opportunity: dict[str, Any]) -> bool:
        source_tier = str(opportunity.get("source_tier") or (opportunity.get("verification") or {}).get("source_tier") or "").upper()
        trust_level = str((opportunity.get("verification") or {}).get("trust_level") or "").lower()
        if source_tier in {"C", "D"} or trust_level in {"needs_review", "suspicious"}:
            return True
        deadline = opportunity.get("deadline")
        if not deadline:
            return True
        text = str(deadline).strip().lower()
        if any(term in text for term in self.VAGUE_DEADLINE_TERMS):
            return True
        try:
            return date.fromisoformat(str(deadline)) < date.today()
        except ValueError:
            return True

    def verify(self, opportunity: dict[str, Any], *, max_queries: int = 10, max_results_per_query: int = 4) -> dict[str, Any]:
        queries = self.build_queries(opportunity)[:max_queries]
        candidates = self._search_candidates(queries, max_results_per_query=max_results_per_query)
        best: dict[str, Any] | None = None
        for candidate in candidates:
            verification = self._verify_candidate(opportunity, candidate)
            if not best or float(verification.get("confidence") or 0) > float(best.get("confidence") or 0):
                best = verification
            if verification.get("status") == "verified" and float(verification.get("confidence") or 0) >= 0.82:
                break
        if not best or not best.get("deadline"):
            return self._not_found("Deadline was not found on official university pages or supporting articles. Please verify manually.")
        if float(best.get("confidence") or 0) < 0.35:
            return self._not_found("Deadline evidence was too weak to verify.")
        return best

    def build_queries(self, opportunity: dict[str, Any]) -> list[str]:
        title = self._quoted(opportunity.get("title"))
        provider = self._quoted(opportunity.get("provider"))
        program_alias = self._program_alias(str(opportunity.get("title") or ""))
        provider_plain = str(opportunity.get("provider") or "").strip()
        title_plain = str(opportunity.get("title") or "").strip()
        domain = urlparse(str(opportunity.get("application_url") or "")).netloc.lower()
        normalized_domain = domain.removeprefix("www.")
        queries = [
            f"{provider} {title} application deadline",
            f"{provider} {title} international deadline",
            f"site:yocket.com {provider} {title} deadline",
            f"{provider} {title} deadline article",
            f"{provider} {title} admissions deadline {date.today().year}",
        ]
        if provider_plain and program_alias and program_alias.lower() != title_plain.lower():
            queries.append(f"{self._quoted(provider_plain)} {self._quoted(program_alias)} international deadline")
        if normalized_domain:
            queries.extend(
                [
                    f"site:{normalized_domain} {title} deadline",
                    f"site:{normalized_domain} application dates postgraduate deadline",
                    f"site:{normalized_domain} international students deadline",
                ]
            )
        queries.extend(
            [
                f"{provider} {title} admissions deadlines",
                f"{provider} {title} scholarship deadline",
                f"{provider} {title} application deadline article {date.today().year}",
            ]
        )
        for supporting_domain in self.SUPPORTING_DEADLINE_DOMAINS:
            queries.append(f"site:{supporting_domain} {provider} {title} application deadline")
        deduped: list[str] = []
        for query in queries:
            query = " ".join(query.split()).strip()
            if query and query not in deduped:
                deduped.append(query)
        return deduped

    def _search_candidates(self, queries: list[str], *, max_results_per_query: int) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for query in queries:
            for result in self.search_provider.search(query, max_results=max_results_per_query):
                row = result.model_dump(mode="json")
                url = str(row.get("url") or "")
                if not url:
                    continue
                existing = by_url.get(url)
                row["query"] = query
                row["deadline_score"] = self._candidate_score(row)
                if not existing or row["deadline_score"] > existing.get("deadline_score", 0):
                    by_url[url] = row
        return sorted(by_url.values(), key=lambda item: item.get("deadline_score", 0), reverse=True)[:8]

    def _candidate_score(self, result: dict[str, Any]) -> int:
        url = str(result.get("url") or "")
        title = str(result.get("title") or "")
        snippet = str(result.get("snippet") or "")
        haystack = f"{url} {title} {snippet}".lower()
        domain = urlparse(url).netloc.lower()
        source_score = SourcePolicyGate.search_result_score(url) or 0
        deadline_score = 10 * sum(1 for term in self.DEADLINE_TERMS if term in haystack)
        pdf_score = 8 if urlparse(url).path.lower().endswith(".pdf") else 0
        official_boost = 18 if SourcePolicyGate.is_official_edu_domain(domain) else 0
        supporting_boost = 14 if self._is_supporting_deadline_domain(domain) else 0
        return source_score + deadline_score + pdf_score + official_boost + supporting_boost

    def _verify_candidate(self, opportunity: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        url = str(candidate.get("url") or "")
        page = self.scraper.scrape_page(
            url,
            search_query=str(candidate.get("query") or ""),
            title=str(candidate.get("title") or ""),
        )
        source_text = str(page.get("text") or candidate.get("snippet") or "")
        if not source_text.strip():
            return self._candidate_not_found(url, "No readable text found on candidate source.")
        payload = self._extract_with_llm(opportunity, candidate, source_text)
        payload = self._normalize_payload(payload, opportunity=opportunity, candidate=candidate, source_text=source_text)
        return payload

    def _extract_with_llm(self, opportunity: dict[str, Any], candidate: dict[str, Any], source_text: str) -> dict[str, Any]:
        user = render_prompt(
            "deadline_verifier_prompt.txt",
            opportunity=json.dumps(
                {
                    "title": opportunity.get("title"),
                    "provider": opportunity.get("provider"),
                    "country": opportunity.get("country"),
                    "opportunity_type": opportunity.get("opportunity_type"),
                    "application_url": opportunity.get("application_url"),
                },
                ensure_ascii=False,
            ),
            source_url=str(candidate.get("url") or ""),
            source_title=str(candidate.get("title") or ""),
            today=date.today().isoformat(),
            source_text=truncate_text(source_text, min(self.settings.extraction_max_source_chars, 2500)),
        )
        try:
            return self.llm.json_chat(
                task=ModelTask.DEADLINE,
                system="You verify admission and application deadlines. Return JSON only.",
                user=user,
                temperature=0.0,
            )
        except Exception:
            fallback = self.deadline_agent.extract(source_text)
            deadlines = fallback.get("deadlines") or []
            application_deadlines = [
                item for item in deadlines if str(item.get("type") or "").lower() == "application_deadline"
            ]
            item = application_deadlines[0] if application_deadlines else (deadlines[0] if deadlines else {})
            return {
                "deadline": item.get("date"),
                "deadline_type": item.get("type") or "unknown",
                "applies_to": item.get("description") or "",
                "source_text": item.get("description") or "",
                "confidence": self._coerce_confidence(item.get("confidence")),
                "status": "verified" if item.get("date") else "not_found",
                "note": "Fallback deadline extraction used.",
            }

    def _normalize_payload(
        self,
        payload: dict[str, Any],
        *,
        opportunity: dict[str, Any],
        candidate: dict[str, Any],
        source_text: str,
    ) -> dict[str, Any]:
        url = str(candidate.get("url") or "")
        domain = urlparse(url).netloc.lower()
        raw_deadline = payload.get("deadline")
        deadline = self._normalize_date(raw_deadline)
        source_type = self._source_type(url, opportunity, candidate)
        source_confidence = self._source_confidence(source_type)
        model_confidence = self._coerce_confidence(payload.get("confidence"))
        confidence = min(0.96, max(model_confidence, source_confidence if deadline else 0.0))
        if not SourcePolicyGate.is_official_edu_domain(domain):
            confidence = min(confidence, self.THIRD_PARTY_MAX_CONFIDENCE)
        status = str(payload.get("status") or ("verified" if deadline else "not_found"))
        if deadline and confidence < self.OFFICIAL_SOURCE_MIN_CONFIDENCE and SourcePolicyGate.is_official_edu_domain(domain):
            status = "needs_manual_review"
        if deadline and not SourcePolicyGate.is_official_edu_domain(domain):
            status = "needs_manual_review"
        if not deadline:
            status = "not_found"
        note = str(payload.get("note") or "")
        if raw_deadline and not deadline:
            note = "Past or invalid deadline ignored; only current and future deadlines are accepted."
        elif deadline and not SourcePolicyGate.is_official_edu_domain(domain):
            note = "Deadline found from a non-official article or third-party page. Please verify manually on the university or official admissions site before relying on it."
        return {
            "deadline": deadline,
            "deadline_type": str(payload.get("deadline_type") or "unknown"),
            "applies_to": str(payload.get("applies_to") or ""),
            "source_url": url if deadline else None,
            "source_text": truncate_text(str(payload.get("source_text") or self._deadline_sentence(source_text)), 320),
            "confidence": round(float(confidence), 2),
            "confidence_label": self._confidence_label(confidence, source_type),
            "source_type": source_type,
            "status": status,
            "note": note,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }

    def _source_type(self, url: str, opportunity: dict[str, Any], candidate: dict[str, Any]) -> str:
        domain = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        title = str(candidate.get("title") or "").lower()
        opportunity_title = str(opportunity.get("title") or "").lower()
        if not SourcePolicyGate.is_official_edu_domain(domain):
            return "third_party"
        if path.endswith(".pdf"):
            return "official_pdf_brochure"
        if self._has_title_terms(opportunity_title, f"{path} {title}"):
            return "official_university_program_page"
        if any(term in f"{path} {title}" for term in ("admission", "deadline", "dates", "calendar", "international")):
            return "official_admissions_page"
        if any(term in f"{path} {title}" for term in ("scholarship", "funding", "financial-aid")):
            return "official_scholarship_page"
        return "official_university_page"

    @classmethod
    def _is_supporting_deadline_domain(cls, domain: str) -> bool:
        normalized = SourcePolicyGate.normalize_domain(domain)
        return any(normalized == item or normalized.endswith(f".{item}") for item in cls.SUPPORTING_DEADLINE_DOMAINS)

    @staticmethod
    def _source_confidence(source_type: str) -> float:
        return {
            "official_university_program_page": 0.9,
            "official_university_page": 0.84,
            "official_admissions_page": 0.76,
            "official_scholarship_page": 0.72,
            "official_pdf_brochure": 0.7,
            "third_party": 0.42,
        }.get(source_type, 0.35)

    @staticmethod
    def _confidence_label(confidence: float, source_type: str) -> str:
        if source_type == "third_party":
            return "Low"
        if confidence >= 0.82:
            return "High"
        if confidence >= 0.62:
            return "Medium"
        if confidence > 0:
            return "Low"
        return "Not verified"

    @staticmethod
    def _normalize_date(value: object) -> str | None:
        if not value:
            return None
        text = str(value).strip()
        if text.lower() in {"null", "none", "unknown", "not_found"}:
            return None
        try:
            parsed = date.fromisoformat(text[:10])
        except ValueError:
            return None
        if parsed < date.today():
            return None
        return parsed.isoformat()

    @staticmethod
    def _coerce_confidence(value: object) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
        text = str(value).strip().lower()
        if text in {"high", "verified"}:
            return 0.84
        if text in {"medium", "moderate"}:
            return 0.64
        if text in {"low", "weak"}:
            return 0.36
        try:
            return max(0.0, min(1.0, float(text)))
        except ValueError:
            return 0.0

    @staticmethod
    def _deadline_sentence(text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
        for sentence in sentences:
            lowered = sentence.lower()
            if any(term in lowered for term in DeadlineVerifierAgent.DEADLINE_TERMS):
                return sentence
        return sentences[0] if sentences else ""

    @staticmethod
    def _has_title_terms(title: str, haystack: str) -> bool:
        terms = [term for term in re.split(r"[^a-z0-9]+", title) if len(term) >= 4]
        if not terms:
            return False
        matches = sum(1 for term in terms if term in haystack)
        return matches >= max(1, min(2, len(terms)))

    @staticmethod
    def _program_alias(title: str) -> str:
        return re.sub(r"\bmsc\b", "Master of", title, flags=re.IGNORECASE)

    @staticmethod
    def _quoted(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return f'"{text}"'

    def _candidate_not_found(self, url: str, note: str) -> dict[str, Any]:
        payload = self._not_found(note)
        payload["source_url"] = url or None
        return payload

    @staticmethod
    def _not_found(note: str) -> dict[str, Any]:
        return {
            "deadline": None,
            "deadline_type": "unknown",
            "applies_to": "",
            "source_url": None,
            "source_text": "",
            "confidence": 0.0,
            "confidence_label": "Not verified",
            "source_type": "unknown",
            "status": "not_found",
            "note": note,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }
