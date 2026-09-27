"""Deterministic no-provider checks for R/P prototype isolation."""

from build_requests import assert_invariants


def main() -> None:
    report = assert_invariants()
    assert set(report) == {"M1_vs_R", "M1_vs_P"}
    assert report["M1_vs_R"]["system_suffix_only"]
    assert report["M1_vs_P"]["system_suffix_only"]
    print("offline_checks: PASS (provider_calls=0, production_changes=0)")


if __name__ == "__main__":
    main()
