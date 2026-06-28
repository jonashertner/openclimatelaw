from importlib.metadata import version

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

CONTRACT = """\
OpenClimateLaw — climate-litigation research with citation-safe grounding.

ANTI-HALLUCINATION CONTRACT — NON-NEGOTIABLE. Violating these degrades legal
writing that practitioners may rely on. Verifiability matters more than
veracity: an unverifiable answer cannot be checked; a verifiable one always can.

R1. NEVER construct a citation yourself. Every reference to a climate case MUST
    be a verbatim `citation_string` returned by a tool (search_cases, get_case,
    cite). If you cannot obtain a citation_string from a tool, do not cite —
    describe the authority in prose instead.
R2. NEVER write a direct quotation (text in quotation marks) unless it came
    verbatim from a retrieved source: a case `summary` (search_cases / get_case)
    or the decision text from get_document_text. Verify every quote with
    check_claim_support (source_kind 'case_summary' or 'document_text') before
    using it. If you cannot retrieve the exact words, paraphrase and cite the
    case as a whole.
R5. If a tool surfaces a pending or superseding proceeding, surface it to the user.
R10. CLAIM-LEVEL SOURCING. Every concrete factual assertion about a climate case
    — a holding, an outcome, a date, a party, a statistic — must point to its
    source. The right granularity is the claim, not the sentence. Never assert a
    fact about a case without a colocated, verifiable source; if you cannot
    ground it in a tool response, fetch it or qualify it as inference.

CITATION WORKFLOW (the only legitimate path): find cases with search_cases →
get_case for the record and its document list → get_document_text to read and
quote the decision → verify quotes with check_claim_support → before sending,
run attest_response(draft_text, retrieved_ids) and fix every flagged item until
it passes.
"""


def build_mcp() -> FastMCP:
    mcp = FastMCP(name="openclimatelaw", instructions=CONTRACT)

    from server.tools.statistics import GroupBy, Scope
    from server.tools.statistics import get_statistics as _get_statistics

    @mcp.tool(
        name="get_statistics",
        description=(
            "Return structured statistics over the climate-litigation corpus. "
            "scope: 'all' | 'sabin'. "
            "group_by: 'jurisdiction' | 'claim_type' | 'year' | 'status' | 'outcome' | null. "
            "Returns case_count, document_count, statute_count, jurisdiction_count, "
            "and per-group counts when group_by is set."
        ),
    )
    async def get_statistics_tool(  # pyright: ignore[reportUnusedFunction]
        scope: Scope = "all",
        group_by: GroupBy | None = None,
    ) -> dict[str, object]:
        return await _get_statistics(scope=scope, group_by=group_by)

    from server.tools.cases import get_case as _get_case

    @mcp.tool(
        name="get_case",
        description=(
            "Return a full case record by canonical UUID or by Sabin ID. "
            "Includes parties, claim types, documents (with upstream URLs), "
            "citation strings, and field-level provenance. Returns null when no case matches."
        ),
    )
    async def get_case_tool(  # pyright: ignore[reportUnusedFunction]
        case_id_or_sabin_id: str,
    ) -> dict[str, object] | None:
        return await _get_case(case_id_or_sabin_id)

    from server.tools.documents import get_document_text as _get_document_text

    @mcp.tool(
        name="get_document_text",
        description=(
            "Return a window of a document's verbatim extracted text (a court "
            "opinion or filing — the full decision text), with its case "
            "citation_string. Use this to read and quote the actual decision: get a "
            "document UUID from get_case().documents[].id, retrieve the text here, "
            "then verify any quote with check_claim_support(source_kind='document_text'). "
            "Long decisions paginate via offset + max_chars (max 20000); follow "
            "has_more / next_offset."
        ),
    )
    async def get_document_text_tool(  # pyright: ignore[reportUnusedFunction]
        document_id: str, offset: int = 0, max_chars: int = 8000
    ) -> dict[str, object] | None:
        return await _get_document_text(document_id, offset=offset, max_chars=max_chars)

    from server.tools.passages import find_relevant_passage as _find_relevant_passage
    from server.tools.passages import get_passage as _get_passage

    @mcp.tool(
        name="find_relevant_passage",
        description=(
            "Pinpoint a claim to the exact passage(s) of a case's decision text. "
            "Returns ranked matches with verbatim text, char offsets, a highlighted "
            "snippet, a confidence score, and the case citation_string — or "
            "{no_match: true} when no passage clearly matches. If no_match, do NOT "
            "guess a pinpoint; say no passage clearly supports the claim. Use this to "
            "ground a specific statement in a precise, quotable passage."
        ),
    )
    async def find_relevant_passage_tool(  # pyright: ignore[reportUnusedFunction]
        case_id_or_sabin_id: str, claim: str, top_k: int = 5
    ) -> dict[str, object]:
        return await _find_relevant_passage(case_id_or_sabin_id, claim, top_k=top_k)

    @mcp.tool(
        name="get_passage",
        description=(
            "Return one decision passage verbatim by (document_id, para_index), with "
            "its neighbouring passage indices and the case citation_string. Pair with "
            "find_relevant_passage (which gives the indices) to read surrounding context."
        ),
    )
    async def get_passage_tool(  # pyright: ignore[reportUnusedFunction]
        document_id: str, para_index: int
    ) -> dict[str, object] | None:
        return await _get_passage(document_id, para_index)

    from server.tools.contracts.attest import attest_response as _attest_response
    from server.tools.contracts.check_support import check_claim_support as _check_claim_support
    from server.tools.contracts.cite import cite as _cite

    @mcp.tool(
        name="cite",
        description=(
            "Return the canonical citation_string for a case in the requested language "
            "and format. Requires a valid case_id (UUID or sabin_id). The R1 contract: "
            "never construct citations from training data; always call this tool to get a "
            "verbatim citation_string from a previously-retrieved case."
        ),
    )
    async def cite_tool(  # pyright: ignore[reportUnusedFunction]
        case_id: str, lang: str, format: str
    ) -> dict[str, object] | None:
        return await _cite(case_id=case_id, lang=lang, format=format)

    @mcp.tool(
        name="check_claim_support",
        description=(
            "Validate that a quoted string appears verbatim in the named source's text. "
            "source_kind: 'case_summary' | 'document_text' | 'citation_string'. "
            "The R2 contract: never quote what wasn't retrieved."
        ),
    )
    async def check_claim_support_tool(  # pyright: ignore[reportUnusedFunction]
        quote: str, source_id: str, source_kind: str
    ) -> dict[str, object]:
        return await _check_claim_support(quote=quote, source_id=source_id, source_kind=source_kind)

    @mcp.tool(
        name="attest_response",
        description=(
            "Scan a draft response for citation-shaped strings and flag any that don't "
            "appear in the citation_strings of retrieved cases. Returns "
            "{passed: bool, violations: [...]}. The R1 contract enforced after-the-fact."
        ),
    )
    async def attest_response_tool(  # pyright: ignore[reportUnusedFunction]
        draft_text: str, retrieved_ids: list[str]
    ) -> dict[str, object]:
        return await _attest_response(draft_text=draft_text, retrieved_ids=retrieved_ids)

    from server.tools.citations import find_citations as _find_citations
    from server.tools.citations import find_cited_by as _find_cited_by

    @mcp.tool(
        name="find_citations",
        description=(
            "Return cases that the given case cites (forward edges). The case "
            "is identified by canonical UUID or Sabin ID. Each result includes "
            "source_of_edge: 'title_match' (canonical_title found in summary or "
            "document text via Aho-Corasick), 'inferred_nlp' (formal cite — "
            "ECLI/BGE/US-reporter — extracted from text), or 'sabin_structured'. "
            "limit max 200."
        ),
    )
    async def find_citations_tool(  # pyright: ignore[reportUnusedFunction]
        case_id_or_sabin_id: str, limit: int = 50
    ) -> dict[str, object]:
        return await _find_citations(case_id_or_sabin_id=case_id_or_sabin_id, limit=limit)

    @mcp.tool(
        name="find_cited_by",
        description=(
            "Return cases that cite the given case (backward edges). The case "
            "is identified by canonical UUID or Sabin ID. Use this for influence "
            "analysis: 'how often is Urgenda cited by other climate cases?'. "
            "limit max 200."
        ),
    )
    async def find_cited_by_tool(  # pyright: ignore[reportUnusedFunction]
        case_id_or_sabin_id: str, limit: int = 50
    ) -> dict[str, object]:
        return await _find_cited_by(case_id_or_sabin_id=case_id_or_sabin_id, limit=limit)

    from server.tools.related import find_related_cases as _find_related_cases

    @mcp.tool(
        name="find_related_cases",
        description=(
            "Return cases semantically similar to the given case via "
            "sentence-transformer embedding cosine similarity. Useful for "
            "'other cases like this one' even when titles share no keywords. "
            "Filters: jurisdiction, claim_type, status. limit max 50."
        ),
    )
    async def find_related_cases_tool(  # pyright: ignore[reportUnusedFunction]
        case_id_or_sabin_id: str,
        jurisdiction: str | None = None,
        claim_type: str | None = None,
        status: str | None = None,
        limit: int = 10,
    ) -> dict[str, object]:
        return await _find_related_cases(
            case_id_or_sabin_id=case_id_or_sabin_id,
            jurisdiction=jurisdiction,
            claim_type=claim_type,
            status=status,
            limit=limit,
        )

    from server.tools.laws import find_cases_by_law as _find_cases_by_law

    @mcp.tool(
        name="find_cases_by_law",
        description=(
            "The legislation -> litigation reverse link: return climate cases that turn on "
            "a given law or instrument (case-insensitive substring over each case's principal "
            "laws). Examples: 'Public Trust Doctrine', 'Clean Air Act', 'European Convention "
            "on Human Rights', 'National Environmental Policy Act'. Each result includes "
            "sabin_id, title, jurisdiction, status, decision_date, and a verbatim "
            "citation_string; the response also returns the total match count. Pair with "
            "get_case (whose principal_laws field lists the laws for a single case)."
        ),
    )
    async def find_cases_by_law_tool(  # pyright: ignore[reportUnusedFunction]
        law: str, limit: int = 20
    ) -> dict[str, object]:
        return await _find_cases_by_law(law=law, limit=limit)

    from server.tools.statutes import get_statute as _get_statute
    from server.tools.statutes import search_statutes as _search_statutes

    @mcp.tool(
        name="search_statutes",
        description=(
            "Search the CCLW legislation layer — climate laws & policies (Climate Change "
            "Laws of the World, by the Sabin Center's partner Climate Policy Radar). "
            "Title-weighted full-text over each law's title + verbatim text. Returns "
            "cclw_id, short_title, jurisdiction, status, enacted_date, a highlighted "
            "match_snippet, and the total count. Filter by jurisdiction (ISO alpha-2). "
            "Pair with get_statute for the full law text, and find_cases_by_law to see "
            "the litigation that turns on a law."
        ),
    )
    async def search_statutes_tool(  # pyright: ignore[reportUnusedFunction]
        query: str, jurisdiction: str | None = None, limit: int = 20
    ) -> dict[str, object]:
        return await _search_statutes(query=query, jurisdiction=jurisdiction, limit=limit)

    @mcp.tool(
        name="get_statute",
        description=(
            "Return one CCLW law/policy by cclw_id (or UUID): jurisdiction, status, "
            "enacted_date, and a paginated window of its verbatim text (offset + "
            "max_chars, max 20000). Quote from this text and verify with "
            "check_claim_support(source_kind='document_text' is for cases; for statute "
            "text quote verbatim from the returned window)."
        ),
    )
    async def get_statute_tool(  # pyright: ignore[reportUnusedFunction]
        cclw_id_or_id: str, offset: int = 0, max_chars: int = 8000
    ) -> dict[str, object] | None:
        return await _get_statute(cclw_id_or_id, offset=offset, max_chars=max_chars)

    from server.tools.search import search_cases as _search_cases

    @mcp.tool(
        name="search_cases",
        description=(
            "The primary way to find a climate case when you don't have its id. "
            "Hybrid search over case titles and summaries: full-text + typo-tolerant "
            "fuzzy title matching + semantic (embedding) similarity. Find by "
            "topic, party, or keyword — e.g. 'Urgenda Netherlands', 'youth "
            "plaintiffs Montana', 'fossil fuel subsidies Brazil'. "
            "Each result includes sabin_id, title, jurisdiction, status, "
            "filing_date, decision_date, a highlighted match_snippet, a summary "
            "excerpt, relevance scores, and a verbatim citation_string ready to use; "
            "the response also returns the total match count. "
            "Recency: to get the newest or oldest decisions, set sort='newest' or "
            "'oldest' (default 'relevance'). Restrict by date with decided_after / "
            "decided_before / filed_after / filed_before (inclusive, ISO "
            "'YYYY-MM-DD'). Pass an EMPTY query to browse the corpus by date "
            "(newest-first) without a keyword. Paginate with limit (max 50) + offset. "
            "Filters: jurisdiction (ISO alpha-2 like 'US'/'NL', case-insensitive, or "
            "body code 'ICJ'/'ECTHR'), claim_type (e.g. 'human_rights'), status "
            "('decided'/'pending'/etc.)."
        ),
    )
    async def search_cases_tool(  # pyright: ignore[reportUnusedFunction]
        query: str,
        jurisdiction: str | None = None,
        claim_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        sort: str = "relevance",
        decided_after: str | None = None,
        decided_before: str | None = None,
        filed_after: str | None = None,
        filed_before: str | None = None,
    ) -> dict[str, object]:
        return await _search_cases(
            query=query,
            jurisdiction=jurisdiction,
            claim_type=claim_type,
            status=status,
            limit=limit,
            offset=offset,
            sort=sort,
            decided_after=decided_after,
            decided_before=decided_before,
            filed_after=filed_after,
            filed_before=filed_before,
        )

    return mcp


def build_app() -> Starlette:
    mcp = build_mcp()
    mcp_app = mcp.http_app()

    async def health(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": version("openclimatelaw"),
            }
        )

    return Starlette(
        routes=[
            Route("/health", health),
            Mount("/", app=mcp_app),
        ],
        lifespan=mcp_app.lifespan,
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    from server._logging import configure_logging
    from server.settings import get_settings

    settings = get_settings()
    configure_logging(level=settings.log_level, json=True)
    if settings.prewarm_embedder:
        import threading

        from server.tools.search import warm_embedder

        # Daemon thread: load the embedding model at startup so the first semantic
        # search after a (re)start doesn't pay the cold-load latency.
        threading.Thread(target=warm_embedder, daemon=True).start()
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )
