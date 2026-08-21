from pathlib import Path

from l9_constellation_topology.cli import run
from l9_constellation_topology.packets import load_topology_bundle

ROOT = Path(__file__).resolve().parents[1]
INPUT_A = ROOT / "tests/fixtures/repository_model_packets/l9-gate-sdk"
INPUT_B = ROOT / "tests/fixtures/repository_model_packets/l9-mcp-server"


def test_cli_compile_validate_and_render(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    reports = tmp_path / "reports"
    assert (
        run(
            [
                "compile-packet",
                "--repo-root",
                str(ROOT),
                "--input-bundle",
                str(INPUT_A),
                "--input-bundle",
                str(INPUT_B),
                "--out",
                str(bundle),
            ]
        )
        == 0
    )
    materialized, receipt = load_topology_bundle(bundle)
    assert receipt.status == "passed"
    assert len(materialized.state.repository_records) == 2
    assert run(["validate-packet", "--input-bundle", str(bundle)]) == 0
    # Revalidating against the input bundles resolves checked-in JSON Schemas from
    # the repository root. The option was missing from this parser, so the path
    # raised AttributeError before any validation ran.
    assert (
        run(
            [
                "validate-packet",
                "--repo-root",
                str(ROOT),
                "--input-bundle",
                str(bundle),
                "--repository-bundle",
                str(INPUT_A),
                "--repository-bundle",
                str(INPUT_B),
            ]
        )
        == 0
    )
    assert (
        run(
            [
                "render-report",
                "--repo-root",
                str(ROOT),
                "--input-bundle",
                str(bundle),
                "--out",
                str(reports),
                "--format",
                "markdown",
                "--format",
                "risk-markdown",
            ]
        )
        == 0
    )
    assert (reports / "topology-report.md").is_file()
    assert (reports / "risk-register.md").is_file()
    assert (reports / "report-manifest.json").is_file()


def test_cli_determinism_command() -> None:
    assert (
        run(
            [
                "verify-determinism",
                "--repo-root",
                str(ROOT),
                "--input-bundle",
                str(INPUT_A),
                "--input-bundle",
                str(INPUT_B),
            ]
        )
        == 0
    )
