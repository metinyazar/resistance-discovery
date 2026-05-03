from src.harmonizer import harmonize_evidence
from src.normalization import normalize_query
from src.skills.claim_extractor import extract_claims
from src.skills.database_support import fetch_database_support
from src.skills.evidence_interpreter import interpret_evidence
from src.skills.evidence_synthesizer import synthesize_literature_first
from src.skills.literature_context import get_literature_context
from src.skills.literature_search import search_literature
from src.skills.paper_ranker import rank_papers
from src.skills.report_writer import generate_narrative
from src.skills.source_planner import plan_sources
from src.types import LiteratureFirstConclusion, VerdictSummary


def analyze_variant_response(gene_symbol, biomarker_type, alteration, therapy, cancer_type):
    query, profile, context = normalize_query(
        gene_symbol=gene_symbol,
        biomarker_type=biomarker_type,
        alteration=alteration,
        therapy=therapy,
        cancer_type=cancer_type,
    )

    literature_search = search_literature(query)
    ranked_papers = rank_papers(query, literature_search["records"])
    literature_claims = extract_claims(query, ranked_papers)

    database_support = fetch_database_support(query, profile, context)
    direct_curated = database_support["direct_curated"]
    related_curated = database_support["related_curated"]
    supporting = database_support["supporting_experimental"]

    database_summary = synthesize_verdict(direct_curated, related_curated, supporting)
    literature_conclusion = synthesize_literature_first(
        literature_claims,
        direct_curated,
        related_curated,
        supporting,
    )
    summary = _conclusion_to_summary(literature_conclusion)

    return {
        "query": query,
        "profile": profile,
        "normalization": context,
        "summary": summary,
        "database_summary": database_summary,
        "database_support": database_support,
        "literature_search": literature_search,
        "ranked_papers": ranked_papers,
        "literature_claims": literature_claims,
        "literature_conclusion": literature_conclusion,
        "direct_curated": direct_curated,
        "related_curated": related_curated,
        "supporting_experimental": supporting,
    }


def run_variant_analysis(description: str, confirmed_query) -> dict:
    source_plan = plan_sources(description, confirmed_query)
    result = analyze_variant_response(
        gene_symbol=confirmed_query["gene_symbol"],
        biomarker_type=confirmed_query["biomarker_type"],
        alteration=confirmed_query["alteration"],
        therapy=confirmed_query["therapy"],
        cancer_type=confirmed_query["cancer_type"],
    )

    result["source_plan"] = source_plan
    result["agent_steps"] = [
        {"skill": "query_parser", "status": "done", "summary": "Parsed and confirmed the biomarker-response query."},
        {"skill": "source_planner", "status": "done", "summary": f"Selected {len(source_plan.get('sources', []))} evidence sources."},
        {"skill": "literature_search", "status": "done", "summary": f"Retrieved {len(result['literature_search']['records'])} literature records."},
        {"skill": "paper_ranker", "status": "done", "summary": f"Ranked {len(result['ranked_papers'])} papers by transparent match flags."},
        {"skill": "claim_extractor", "status": "done", "summary": f"Extracted {len(result['literature_claims'])} candidate claim sentences."},
        {"skill": "database_support", "status": "done", "summary": f"Attached {len(result['direct_curated']) + len(result['related_curated'])} curated and {len(result['supporting_experimental'])} experimental support records."},
        {"skill": "evidence_synthesizer", "status": "done", "summary": f"Called {result['summary'].verdict} with {result['summary'].confidence_band} literature-first confidence."},
    ]

    evidence_digest = harmonize_evidence(result)
    result["evidence_digest"] = evidence_digest
    interpretation = interpret_evidence(
        result["query"],
        result["direct_curated"],
        result["related_curated"],
        result["supporting_experimental"],
        result["summary"],
        result["literature_claims"],
        result["ranked_papers"],
    )
    result["interpretation"] = interpretation
    result["agent_steps"].append(
        {
            "skill": "evidence_interpreter",
            "status": "done",
            "summary": f"Called {interpretation['verdict']} with {interpretation['confidence_band']} confidence.",
        }
    )

    result["literature_context"] = get_literature_context(result["query"], result)
    result["agent_steps"].append(
        {
            "skill": "literature_context",
            "status": "done" if result["literature_context"] else "skipped",
            "summary": "Generated biological context." if result["literature_context"] else "LLM context skipped because no API key is configured.",
        }
    )
    result["report_text"] = generate_narrative(description, result)
    result["agent_steps"].append(
        {
            "skill": "report_writer",
            "status": "done" if result["report_text"] else "skipped",
            "summary": "Generated narrative report." if result["report_text"] else "LLM report skipped because no API key is configured.",
        }
    )
    return result


def _conclusion_to_summary(conclusion: LiteratureFirstConclusion) -> VerdictSummary:
    return VerdictSummary(
        verdict=conclusion.verdict,
        confidence_band=conclusion.confidence_band,
        top_rationale=conclusion.rationale,
        direct_evidence_count=conclusion.primary_literature_count,
        conflicting_evidence_count=conclusion.conflicting_count,
        supporting_experimental_count=conclusion.supporting_database_count,
    )


def synthesize_verdict(direct_curated, related_curated, supporting) -> VerdictSummary:
    curated = direct_curated + related_curated
    supporting_count = len(supporting)

    if not curated:
        rationale = "No accepted predictive CIViC evidence matched the biomarker, therapy, and cancer context."
        if supporting:
            rationale += " Experimental cell-line support exists, but curated evidence is still insufficient."
        return VerdictSummary(
            verdict="INSUFFICIENT",
            confidence_band="low",
            top_rationale=rationale,
            direct_evidence_count=0,
            conflicting_evidence_count=0,
            supporting_experimental_count=supporting_count,
        )

    verdict_counts = {
        "SENSITIVE": 0,
        "RESISTANT": 0,
        "ADVERSE": 0,
    }
    for record in curated:
        if record.response_class in verdict_counts:
            verdict_counts[record.response_class] += 1

    nonzero = [key for key, value in verdict_counts.items() if value > 0]
    conflicting = len(nonzero) > 1
    if conflicting:
        verdict = "CONFLICTING"
    else:
        verdict = nonzero[0] if nonzero else "INSUFFICIENT"

    confidence = "high" if len(direct_curated) >= 2 else "moderate" if direct_curated else "low"
    rationale = _build_rationale(verdict, direct_curated, related_curated, supporting)

    return VerdictSummary(
        verdict=verdict,
        confidence_band=confidence,
        top_rationale=rationale,
        direct_evidence_count=len(direct_curated),
        conflicting_evidence_count=sum(verdict_counts.values()) if conflicting else 0,
        supporting_experimental_count=supporting_count,
    )


def _build_rationale(verdict, direct_curated, related_curated, supporting):
    curated_total = len(direct_curated) + len(related_curated)
    if verdict == "SENSITIVE":
        return f"Accepted curated evidence is predominantly sensitivity-oriented ({curated_total} matched CIViC records, {len(direct_curated)} direct)."
    if verdict == "RESISTANT":
        return f"Accepted curated evidence is predominantly resistance-oriented ({curated_total} matched CIViC records, {len(direct_curated)} direct)."
    if verdict == "ADVERSE":
        return f"Accepted curated evidence highlights adverse-response risk ({curated_total} matched CIViC records)."
    if verdict == "CONFLICTING":
        return (
            f"Curated evidence contains competing response classes across {curated_total} matched CIViC records. "
            f"{len(supporting)} supporting experimental records were kept separate from the main verdict."
        )
    if supporting:
        return "Only supporting experimental evidence matched; curated predictive evidence was insufficient."
    return "Matched evidence did not support a confident predictive response call."
