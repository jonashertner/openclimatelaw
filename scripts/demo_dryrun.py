# pyright: basic
"""Dry-run every demo beat against the live MCP and print PASS/FAIL.

The morning-of check for docs/demo/runbook.md. Run:
    uv run python scripts/demo_dryrun.py

Exits non-zero if any beat fails, so it doubles as a pre-demo smoke gate. IDs are the
pinned flagships from the runbook; if one fails, re-resolve it (duplicate family records
mean the #1-by-name can drift).
"""

import asyncio
import sys

from fastmcp import Client

URL = "https://mcp.openclimatelaw.org/mcp"


def _uw(r):
    sc = r.structured_content
    return sc.get("result", sc) if isinstance(sc, dict) else sc


async def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            failures.append(name)

    async with Client(URL) as c:

        async def call(tool, args):
            return _uw(await c.call_tool(tool, args))

        print("B0 — apex cases rank #1 by name")
        for q in ["Urgenda", "Held v. State", "Massachusetts v. EPA", "KlimaSeniorinnen"]:
            s = await call("search_cases", {"query": q, "limit": 1})
            top = (s.get("results") or [{}])[0]
            check(
                f"search '{q}'",
                bool(s.get("results")),
                f"#1 {top.get('canonical_title', '?')[:40]}",
            )

        print("B1 — fabrication catch (global citation formats)")
        a = await call(
            "attest_response",
            {
                "draft_text": "As held in Smith v. Exxon, 999 U.S. 1 (2030) and Plan B v PM "
                "[2099] EWHC 9999 (Admin), emitters owe a duty.",
                "retrieved_ids": ["Sabin.family.2823.0"],
            },
        )
        check(
            "attest flags US+UK fakes",
            not a.get("passed") and len(a.get("violations", [])) >= 2,
            f"passed={a.get('passed')} violations={len(a.get('violations', []))}",
        )

        print("B2 — grounded verbatim research (US pinpoint)")
        fp = await call(
            "find_relevant_passage",
            {
                "case_id_or_sabin_id": "Sabin.family.151.0",
                "claim": "EPA has authority to regulate greenhouse gases as air pollutants",
            },
        )
        ok = not fp.get("no_match") and bool(fp.get("matches"))
        check("find_relevant_passage(EPA)", ok, f"count={fp.get('count')}")
        if ok:
            m = fp["matches"][0]
            ck = await call(
                "check_claim_support",
                {
                    "quote": (m.get("text") or "")[:90],
                    "source_id": m.get("document_id"),
                    "source_kind": "document_text",
                },
            )
            check(
                "check_claim_support", bool(ck.get("supported")), f"supported={ck.get('supported')}"
            )

        print("B3 — litigation <-> legislation bridge")
        ss = await call("search_statutes", {"query": "renewable energy targets", "limit": 1})
        check("search_statutes", (ss.get("total") or 0) > 0, f"total={ss.get('total')}")
        g = await call(
            "get_case", {"case_id_or_sabin_id": "Sabin.family.7481.0", "include_documents": False}
        )
        ls = g.get("linked_statutes") or []
        check(
            "linked_statutes(Friends of the Earth)",
            bool(ls),
            f"-> {[x['short_title'][:24] for x in ls]}",
        )
        fl = await call(
            "find_cases_by_law", {"law": "European Convention on Human Rights", "limit": 1}
        )
        check("find_cases_by_law(ECHR)", (fl.get("total") or 0) > 0, f"total={fl.get('total')}")

        print("B4 — cross-jurisdiction discovery")
        fr = await call(
            "find_related_cases", {"case_id_or_sabin_id": "Sabin.family.2823.0", "limit": 4}
        )
        check(
            "find_related_cases(Urgenda)",
            bool(fr.get("results")),
            f"{[x['canonical_title'][:20] for x in (fr.get('results') or [])]}",
        )

        print("B5 — outcomes + parties")
        sh = await call(
            "get_case", {"case_id_or_sabin_id": "Sabin.family.8918.0", "include_documents": False}
        )
        check(
            "Shell outcome=mixed",
            sh.get("outcome_code") == "mixed",
            f"outcome={sh.get('outcome_code')}",
        )
        check(
            "Shell parties",
            len(sh.get("parties") or []) >= 2,
            f"{len(sh.get('parties') or [])} parties",
        )
        st = await call("get_statistics", {"scope": "all"})
        check(
            "get_statistics",
            (st.get("totals", {}).get("case_count") or 0) > 0,
            str(st.get("totals")),
        )

        print("\nB1b — grounding judge (optional; needs ANTHROPIC_API_KEY in prod)")
        vg = await call(
            "verify_grounding",
            {
                "draft_text": "In Urgenda the court ordered each citizen to receive 5 billion euros.",
                "retrieved_ids": ["Sabin.family.2823.0"],
            },
        )
        if vg.get("available"):
            check(
                "verify_grounding flags fabricated holding",
                vg.get("supported") is False,
                f"unsupported_claims={len(vg.get('unsupported_claims', []))}",
            )
        else:
            print("  [INFO] verify_grounding dormant (no prod key) — Beat 1b unavailable")

    print(f"\n{'ALL BEATS PASS' if not failures else 'FAILURES: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
