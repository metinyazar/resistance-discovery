import csv
import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET

import requests

from src.config import LITERATURE_SEED_PATH
from src.normalization import normalize_cancer_type, normalize_therapy
from src.skills.literature_cache import LiteratureCache
from src.types import BiomarkerQuery, LiteratureRecord

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

RESPONSE_TERMS = [
    "resistance",
    "resistant",
    "sensitivity",
    "sensitive",
    "response",
    "non-response",
    "progression",
]


class RateLimitedHTTP:
    def __init__(self, rate_limit_per_sec: float = 3.0, retries: int = 3, timeout: int = 30):
        self.min_interval = 1.0 / max(rate_limit_per_sec, 0.1)
        self.retries = retries
        self.timeout = timeout
        self.last_request = 0.0
        self.session = requests.Session()

    def get(self, url: str, params: dict):
        delay = 0.7
        for attempt in range(self.retries + 1):
            elapsed = time.time() - self.last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                self.last_request = time.time()
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                time.sleep(delay)
                delay *= 1.6
                continue

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt == self.retries:
                    response.raise_for_status()
                time.sleep(delay)
                delay *= 1.6
                continue

            response.raise_for_status()
            return response
        raise RuntimeError("Unexpected HTTP retry failure")


def search_literature(query: BiomarkerQuery, max_hits: int = 50, use_pubmed: bool | None = None) -> dict:
    cache = LiteratureCache()
    http = RateLimitedHTTP(rate_limit_per_sec=3.0)
    try:
        search_queries = build_literature_queries(query)
        diagnostics = {
            "europe_pmc_records": 0,
            "pubmed_enabled": False,
            "pubmed_records": 0,
            "max_hits": max_hits,
            "errors": [],
            "queries": search_queries,
        }

        records = []
        try:
            for search_query in search_queries:
                records = merge_records(records, search_europe_pmc(search_query, max_hits=max_hits, cache=cache, http=http))
            diagnostics["europe_pmc_records"] = len(records)
        except requests.RequestException as exc:
            diagnostics["errors"].append(f"Europe PMC request failed: {exc}")

        pubmed_enabled = bool(os.getenv("NCBI_EMAIL")) if use_pubmed is None else use_pubmed
        diagnostics["pubmed_enabled"] = pubmed_enabled
        pubmed_records = []
        if pubmed_enabled:
            try:
                for search_query in search_queries:
                    pubmed_records = merge_records(pubmed_records, search_pubmed(search_query, max_hits=max_hits, cache=cache, http=http))
                diagnostics["pubmed_records"] = len(pubmed_records)
                records = merge_records(records, pubmed_records)
            except requests.RequestException as exc:
                diagnostics["errors"].append(f"PubMed request failed: {exc}")

        seed_records = search_seed_literature(query)
        if seed_records and (not records or diagnostics["errors"]):
            records = merge_records(records, seed_records)
            diagnostics["seed_records"] = len(seed_records)
        else:
            diagnostics["seed_records"] = 0

        return {
            "query": search_queries[0],
            "records": records,
            "diagnostics": diagnostics,
        }
    finally:
        cache.close()


def build_literature_query(query: BiomarkerQuery) -> str:
    return build_literature_queries(query)[0]


def build_literature_queries(query: BiomarkerQuery) -> list[str]:
    therapy_info = normalize_therapy(query.therapy)
    cancer_info = normalize_cancer_type(query.cancer_type)
    therapy_terms = [query.therapy, therapy_info["canonical"], *therapy_info["aliases"]]
    cancer_terms = [query.cancer_type, cancer_info["canonical"], *cancer_info["aliases"]]

    gene_part = _or_terms([query.gene_symbol])
    alteration_part = _or_terms([query.alteration, f"{query.gene_symbol} {query.alteration}"])
    therapy_part = _or_terms(_dedupe(therapy_terms))
    cancer_part = _or_terms(_dedupe(cancer_terms))
    response_part = _or_terms(RESPONSE_TERMS)

    query_parts = [
        _or_terms([query.gene_symbol]),
        alteration_part,
        therapy_part,
        cancer_part,
        response_part,
    ]
    strict = " AND ".join(part for part in query_parts if part)

    relaxed_variants = [
        [gene_part, alteration_part, therapy_part, cancer_part],
        [gene_part, alteration_part, therapy_part, response_part],
        [gene_part, alteration_part, therapy_part],
        [gene_part, alteration_part, cancer_part],
    ]
    return _dedupe([strict, *[" AND ".join(part for part in parts if part) for parts in relaxed_variants]])


def search_europe_pmc(search_query: str, max_hits: int, cache: LiteratureCache, http: RateLimitedHTTP) -> list[LiteratureRecord]:
    params = {
        "query": search_query,
        "format": "json",
        "resultType": "core",
        "pageSize": max_hits,
        "sort": "RELEVANCE",
    }
    key = _cache_key(EUROPE_PMC_URL, params)
    cached = cache.get_json("europe_pmc_search", key)
    if cached is None:
        cached = http.get(EUROPE_PMC_URL, params=params).json()
        cache.set_json("europe_pmc_search", key, cached)

    results = cached.get("resultList", {}).get("result", [])
    return [_record_from_europe_pmc(item) for item in results]


def search_pubmed(search_query: str, max_hits: int, cache: LiteratureCache, http: RateLimitedHTTP) -> list[LiteratureRecord]:
    email = os.getenv("NCBI_EMAIL")
    api_key = os.getenv("NCBI_API_KEY", "")
    if not email:
        return []

    common = {"tool": "resistance_discovery", "email": email}
    if api_key:
        common["api_key"] = api_key

    esearch_params = {
        **common,
        "db": "pubmed",
        "term": search_query,
        "retmode": "json",
        "retmax": max_hits,
        "sort": "relevance",
    }
    esearch_key = _cache_key(f"{NCBI_BASE}/esearch.fcgi", esearch_params)
    cached = cache.get_json("pubmed_esearch", esearch_key)
    if cached is None:
        cached = http.get(f"{NCBI_BASE}/esearch.fcgi", params=esearch_params).json()
        cache.set_json("pubmed_esearch", esearch_key, cached)

    pmids = cached.get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return []

    efetch_params = {
        **common,
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    efetch_key = _cache_key(f"{NCBI_BASE}/efetch.fcgi", efetch_params)
    xml_text = cache.get("pubmed_efetch", efetch_key)
    if xml_text is None:
        xml_text = http.get(f"{NCBI_BASE}/efetch.fcgi", params=efetch_params).text
        cache.set("pubmed_efetch", efetch_key, xml_text)

    return parse_pubmed_xml(xml_text)


def search_seed_literature(query: BiomarkerQuery) -> list[LiteratureRecord]:
    if not LITERATURE_SEED_PATH.exists():
        return []

    therapy_info = normalize_therapy(query.therapy)
    cancer_info = normalize_cancer_type(query.cancer_type)
    therapy_terms = [query.therapy, therapy_info["canonical"], *therapy_info["aliases"]]
    cancer_terms = [query.cancer_type, cancer_info["canonical"], *cancer_info["aliases"]]

    records = []
    with LITERATURE_SEED_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            record = LiteratureRecord(
                source=row["source"],
                pmid=row["pmid"],
                doi=row["doi"],
                title=row["title"],
                journal=row["journal"],
                year=row["year"],
                authors=row["authors"],
                abstract=row["abstract"],
                url=row["url"],
            )
            text = f"{record.title} {record.abstract}".lower()
            if (
                query.gene_symbol.lower() in text
                and query.alteration.lower() in text
                and (_contains_any(text, therapy_terms) or _contains_any(text, cancer_terms))
            ):
                records.append(record)
    return records


def merge_records(primary: list[LiteratureRecord], secondary: list[LiteratureRecord]) -> list[LiteratureRecord]:
    merged = []
    seen = set()
    for record in primary + secondary:
        key = record.pmid or record.doi or record.title.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(record)
    return merged


def _contains_any(lowered_text: str, terms: list[str]) -> bool:
    return any(term and term.lower() in lowered_text for term in terms)


def parse_pubmed_xml(xml_text: str) -> list[LiteratureRecord]:
    root = ET.fromstring(xml_text)
    records = []
    for article in root.findall(".//PubmedArticle"):
        pmid = (article.findtext(".//MedlineCitation/PMID") or "").strip()
        title = " ".join((article.findtext(".//ArticleTitle") or "").split())
        journal = article.findtext(".//Journal/Title") or ""
        year = article.findtext(".//PubDate/Year") or ""
        abstract_parts = [node.text or "" for node in article.findall(".//Abstract/AbstractText")]
        abstract = " ".join(" ".join(part.split()) for part in abstract_parts if part)
        doi = ""
        for node in article.findall(".//ArticleId"):
            if node.attrib.get("IdType") == "doi":
                doi = node.text or ""
        first_author = _first_author(article)
        records.append(
            LiteratureRecord(
                source="pubmed",
                pmid=pmid,
                doi=doi,
                title=title,
                journal=journal,
                year=year,
                authors=first_author,
                abstract=abstract,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            )
        )
    return records


def _record_from_europe_pmc(item: dict) -> LiteratureRecord:
    pmid = item.get("pmid") or item.get("id") or ""
    doi = item.get("doi") or ""
    return LiteratureRecord(
        source="europe_pmc",
        pmid=pmid,
        doi=doi,
        title=item.get("title") or "",
        journal=item.get("journalTitle") or "",
        year=item.get("pubYear") or "",
        authors=item.get("authorString") or "",
        abstract=item.get("abstractText") or "",
        url=f"https://europepmc.org/article/MED/{pmid}" if pmid else item.get("fullTextUrlList", {}).get("fullTextUrl", [{}])[0].get("url", ""),
    )


def _first_author(article) -> str:
    author = article.find(".//AuthorList/Author")
    if author is None:
        return ""
    last = author.findtext("LastName") or ""
    initials = author.findtext("Initials") or ""
    return " ".join(part for part in [last, initials] if part)


def _or_terms(terms: list[str]) -> str:
    clean_terms = [term for term in _dedupe(terms) if term]
    if not clean_terms:
        return ""
    return "(" + " OR ".join(f'"{term}"' for term in clean_terms) + ")"


def _dedupe(items) -> list[str]:
    out = []
    seen = set()
    for item in items:
        text = " ".join(str(item).split())
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _cache_key(url: str, params: dict) -> str:
    packed = json.dumps({"url": url, "params": params}, sort_keys=True)
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()
