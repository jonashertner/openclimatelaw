-- Privacy-conscious usage tracking: one row per tool call. Records what (tool, ok,
-- duration) and who-coarsely (client name/version from the MCP handshake, a SALTED HASH
-- of the caller IP so distinct users are countable without storing PII, user-agent,
-- session id). No query text or arguments are stored — a legal-research query can reveal
-- litigation strategy.
CREATE TABLE usage_event (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts              timestamptz NOT NULL DEFAULT now(),
    tool            text NOT NULL,
    ok              boolean NOT NULL DEFAULT true,
    error_kind      text,
    duration_ms     integer,
    client_name     text,
    client_version  text,
    session_id      text,
    ip_hash         text,
    user_agent      text
);
CREATE INDEX usage_event_ts_idx ON usage_event (ts DESC);
CREATE INDEX usage_event_tool_idx ON usage_event (tool);
