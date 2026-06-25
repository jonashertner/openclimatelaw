from server.main import build_mcp


def test_instructions_carry_the_contract() -> None:
    instr = build_mcp().instructions or ""
    for marker in ("R1", "R10", "verbatim", "attest_response", "citation"):
        assert marker in instr, f"missing contract marker: {marker}"
