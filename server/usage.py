# pyright: basic
"""Usage tracking — one row per tool call.

Always records WHAT (tool, ok, duration) and WHO-coarsely (client name/version from the MCP
handshake, a SALTED HASH of the caller IP for distinct-user counting, the user-agent, the
session id). Best-effort: a logging failure never affects the tool call.

Two modes, switched by USAGE_LOG_FULL:
- FULL (default, current testing phase) — also stores the raw caller IP and the tool
  ARGUMENTS (including query text). Maximum visibility into who is using it and how.
- PRIVATE (USAGE_LOG_FULL=0) — keeps only the salted ip_hash; no raw IP, no arguments.
  A legal-research query can reveal a client's litigation strategy, so this is the intended
  posture once the preview phase ends.

Disable tracking entirely with USAGE_TRACKING=0. Set USAGE_IP_SALT to a secret for the hash.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import structlog
from fastmcp.server.middleware import Middleware

log = structlog.get_logger("server.usage")

_SALT: str | None = None
_ARG_CAP = 4000  # truncate long string argument values
_INSERT = (
    "INSERT INTO usage_event (tool, ok, error_kind, duration_ms, client_name, "
    "client_version, session_id, ip_hash, user_agent, ip, arguments) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)


def _log_full() -> bool:
    """Full logging (raw IP + arguments) is on by default for the testing phase."""
    return os.environ.get("USAGE_LOG_FULL", "1") != "0"


def _truncate_args(args: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (args or {}).items():
        out[k] = v[:_ARG_CAP] + "…(truncated)" if isinstance(v, str) and len(v) > _ARG_CAP else v
    return out


def _salt() -> str:
    global _SALT
    if _SALT is None:
        _SALT = os.environ.get("USAGE_IP_SALT") or ""
        if not _SALT:
            p = Path(os.path.expanduser("~/.usage_salt"))
            _SALT = p.read_text().strip() if p.exists() else "openclimatelaw-usage-v1"
    return _SALT


def hash_ip(ip: str | None) -> str | None:
    """Salted, truncated SHA-256 of an IP — distinct-user counting without storing the IP."""
    if not ip:
        return None
    return hashlib.sha256((_salt() + ip).encode()).hexdigest()[:16]


def _client_info(fc: Any) -> tuple[str | None, str | None]:
    try:
        ci = fc.request_context.session.client_params.clientInfo
        return ci.name, ci.version
    except Exception:
        return None, None


def _http_meta() -> tuple[str | None, str | None]:
    """(ip, user_agent) from the live HTTP request, or (None, None) off the HTTP transport."""
    try:
        from fastmcp.server.dependencies import get_http_request

        req = get_http_request()
        xff = req.headers.get("x-forwarded-for", "")
        ip = xff.split(",")[0].strip() if xff else (req.client.host if req.client else None)
        return ip, req.headers.get("user-agent")
    except Exception:
        return None, None


class UsageMiddleware(Middleware):
    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        t0 = time.monotonic()
        ok, err = True, None
        try:
            return await call_next(context)
        except Exception as e:
            ok, err = False, type(e).__name__
            raise
        finally:
            try:
                await self._record(context, ok, err, int((time.monotonic() - t0) * 1000))
            except Exception as e:  # never let tracking break a tool call
                log.debug("usage_record_failed", error=repr(e)[:120])

    async def _record(self, context: Any, ok: bool, err: str | None, dur: int) -> None:
        from server.db import get_pool

        msg = getattr(context, "message", None)
        tool = getattr(msg, "name", None) or "?"
        args = getattr(msg, "arguments", None)
        fc = context.fastmcp_context
        cname, cver = _client_info(fc)
        ip, ua = _http_meta()
        sid = getattr(fc, "session_id", None)
        full = _log_full()
        ip_val = ip if full else None
        args_json = json.dumps(_truncate_args(args)) if (full and isinstance(args, dict)) else None
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                _INSERT,
                (
                    tool,
                    ok,
                    err,
                    dur,
                    cname,
                    cver,
                    sid,
                    hash_ip(ip),
                    (ua[:500] if ua else None),
                    ip_val,
                    args_json,
                ),
            )
            await conn.commit()
