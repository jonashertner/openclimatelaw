from importlib.metadata import version

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route


def build_mcp() -> FastMCP:
    mcp = FastMCP(name="openclimatelaw")

    from server.tools.statistics import GroupBy, Scope
    from server.tools.statistics import get_statistics as _get_statistics

    @mcp.tool(
        name="get_statistics",
        description=(
            "Return structured statistics over the climate-litigation corpus. "
            "scope: 'all' | 'sabin' | 'cclw'. "
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

    from server.tools.citations import find_cited_by as _find_cited_by
    from server.tools.citations import find_citations as _find_citations

    @mcp.tool(
        name="find_citations",
        description=(
            "Return cases that the given case cites (forward edges). The case "
            "is identified by canonical UUID or Sabin ID. Citation graph is "
            "extracted via NLP from case summaries and document text — "
            "source_of_edge='inferred_nlp'. limit max 200."
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

    from server.tools.search import search_cases as _search_cases

    @mcp.tool(
        name="search_cases",
        description=(
            "Free-text search over case titles and summaries with optional filters. "
            "Returns ranked matches with sabin_id, title, jurisdiction, status, "
            "summary excerpt, and a verbatim citation_string ready to use. "
            "Use this when you don't already have a case_id — for example to find "
            "'Urgenda Netherlands' or 'youth plaintiffs Montana' or 'fossil fuel "
            "subsidies Brazil'. Filters: jurisdiction (ISO alpha-2 like 'US' / 'NL' "
            "or special body code 'ICJ'/'ECTHR'), claim_type (e.g. 'human_rights'), "
            "status ('decided'/'pending'/etc.). limit max 50."
        ),
    )
    async def search_cases_tool(  # pyright: ignore[reportUnusedFunction]
        query: str,
        jurisdiction: str | None = None,
        claim_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        return await _search_cases(
            query=query,
            jurisdiction=jurisdiction,
            claim_type=claim_type,
            status=status,
            limit=limit,
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
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )
