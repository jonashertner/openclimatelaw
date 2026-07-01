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
import secrets
import time
from pathlib import Path
from typing import Any

import structlog
from fastmcp.server.middleware import Middleware

log = structlog.get_logger("server.usage")

_SALT: str | None = None
_ARG_CAP = 4000  # truncate long string argument values
_PREVIEW_CAP = 1500  # truncate the response preview (full mode)
_INSERT = (
    "INSERT INTO usage_event (tool, ok, error_kind, duration_ms, client_name, "
    "client_version, session_id, ip_hash, user_agent, ip, arguments, result) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)"
)


def _log_full() -> bool:
    """Full logging (raw IP + arguments) is on by default for the testing phase."""
    return os.environ.get("USAGE_LOG_FULL", "1") != "0"


def _truncate_args(args: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (args or {}).items():
        out[k] = v[:_ARG_CAP] + "…(truncated)" if isinstance(v, str) and len(v) > _ARG_CAP else v
    return out


def _result_meta(result: Any, full: bool) -> str | None:
    """A compact response summary for quality control — count / total / no_match /
    top_confidence / returned_chars / violations, plus a truncated preview in full mode.
    This is public case/law text + result metadata, not user data."""
    try:
        sc = getattr(result, "structured_content", None)
        r = sc.get("result", sc) if isinstance(sc, dict) else sc
        meta: dict[str, Any] = {}
        if isinstance(r, dict):
            for k in ("count", "total", "no_match", "available", "passed", "returned_chars"):
                if r.get(k) is not None:
                    meta[k] = r[k]
            res = r.get("results")
            if isinstance(res, list):
                meta.setdefault("count", len(res))
            matches = r.get("matches")
            if isinstance(matches, list):
                meta["count"] = len(matches)
                if matches and isinstance(matches[0], dict):
                    meta["top_confidence"] = matches[0].get("confidence")
            viol = r.get("violations")
            if isinstance(viol, list):
                meta["violations"] = len(viol)
        elif isinstance(r, list):
            meta["count"] = len(r)
        if full and sc is not None:
            meta["preview"] = json.dumps(sc, default=str)[:_PREVIEW_CAP]
        return json.dumps(meta, default=str) if meta else None
    except Exception:
        return None


def _salt() -> str:
    """A secret salt for IP hashing. Prefer $USAGE_IP_SALT (set it in .env.production for a
    salt that's stable across deploys); else a persisted random salt; never a public default
    (a known salt makes the small IPv4 space trivially brute-forceable)."""
    global _SALT
    if _SALT is not None:
        return _SALT
    _SALT = os.environ.get("USAGE_IP_SALT") or ""
    if _SALT:
        return _SALT
    p = Path(os.path.expanduser("~/.usage_salt"))
    if p.exists():
        _SALT = p.read_text().strip()
    if not _SALT:
        _SALT = secrets.token_hex(16)
        try:
            p.write_text(_SALT)
            p.chmod(0o600)
        except Exception:
            pass  # ephemeral per-process salt is still unguessable
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
        # The edge proxy (Caddy) APPENDS the real peer to X-Forwarded-For, so the trusted
        # client IP is the LAST entry — the leftmost entries are client-supplied and spoofable.
        xff = req.headers.get("x-forwarded-for", "")
        ip = xff.split(",")[-1].strip() if xff else (req.client.host if req.client else None)
        return ip, req.headers.get("user-agent")
    except Exception:
        return None, None


class UsageMiddleware(Middleware):
    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        t0 = time.monotonic()
        ok, err, result = True, None, None
        try:
            result = await call_next(context)
            return result
        except Exception as e:
            ok, err = False, type(e).__name__
            raise
        finally:
            try:
                await self._record(context, ok, err, int((time.monotonic() - t0) * 1000), result)
            except Exception as e:  # never let tracking break a tool call
                log.debug("usage_record_failed", error=repr(e)[:120])

    async def _record(self, context: Any, ok: bool, err: str | None, dur: int, result: Any) -> None:
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
        result_json = _result_meta(result, full)
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
                    result_json,
                ),
            )
            await conn.commit()
