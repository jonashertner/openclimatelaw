from importlib.metadata import version

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route


def build_mcp() -> FastMCP:
    mcp = FastMCP(name="openclimatelaw")

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
        scope: str = "all",
        group_by: str | None = None,
    ) -> dict[str, object]:
        return await _get_statistics(scope=scope, group_by=group_by)

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

    mcp_app.add_route("/health", health)

    return Starlette(
        routes=[
            Mount("/", app=mcp_app),
            Route("/health", health),
        ],
        lifespan=mcp_app.lifespan,
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    from server.settings import get_settings

    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
    )
