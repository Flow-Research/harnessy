import json
import shlex
import subprocess
import sys
from pathlib import Path


FLOW_INSTALL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = FLOW_INSTALL_ROOT / "skills" / "code-review" / "scripts"


def run_script(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_ROOT / script), *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Harnessy Test")
    (repo / "README.md").write_text("# Demo\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    return repo


def test_discover_diff_emits_inventory_and_risk_surfaces(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "checkout", "-b", "feature/code-review")

    skill_file = repo / "tools" / "flow-install" / "skills" / "example" / "SKILL.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("---\nname: example\ndescription: Example skill.\n---\n")
    git(repo, "add", str(skill_file))
    git(repo, "commit", "-m", "add example skill")

    result = run_script("discover-diff.py", "--base", "main", "--head", "HEAD", cwd=repo)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert payload["base_ref"] == "main"
    assert payload["head_ref"] == "HEAD"
    assert payload["summary"]["files_changed"] == 1
    assert payload["files"][0]["path"] == "tools/flow-install/skills/example/SKILL.md"
    assert payload["files"][0]["cluster"] == "skills"
    assert "skill-packaging" in payload["risk_surfaces"]
    assert "git diff --name-status -M main...HEAD" in payload["commands"]


def test_validate_output_accepts_valid_request_changes(tmp_path: Path) -> None:
    review = tmp_path / "feedback.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "ai_review",
                "review_status": "completed",
                "verdict": "request_changes",
                "summary": "One blocking issue.",
                "findings": [
                    {
                        "id": "CR-001",
                        "severity": "major",
                        "category": "test_gap",
                        "file": "src/app.py",
                        "line": 12,
                        "title": "Missing integration coverage",
                        "evidence": "The behavior changed without a corresponding test.",
                        "risk": "Regression would pass current tests.",
                        "recommended_fix": "Add an integration test for the changed behavior.",
                    }
                ],
                "tests_reviewed": ["tests/test_app.py"],
                "missing_tests": ["integration test for changed behavior"],
                "verification": {
                    "schema_valid": True,
                    "citations_valid": True,
                    "blocking_findings_verified": True,
                    "verifier_notes": "Finding is supported.",
                },
            }
        )
    )

    result = run_script("validate-output.py", str(review), "--json")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "errors": []}


def test_validate_output_accepts_skipped_ci_review(tmp_path: Path) -> None:
    review = tmp_path / "feedback.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "deterministic_only",
                "review_status": "skipped",
                "skipped_reason": "No provider command configured.",
                "verdict": "approve",
                "summary": "AI review skipped.",
                "findings": [],
                "tests_reviewed": [],
                "missing_tests": [],
                "verification": {
                    "schema_valid": True,
                    "citations_valid": True,
                    "blocking_findings_verified": True,
                },
            }
        )
    )

    result = run_script("validate-output.py", str(review), "--json")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "errors": []}


def test_validate_output_rejects_bad_verdict_policy_and_missing_evidence(tmp_path: Path) -> None:
    review = tmp_path / "feedback.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "verdict": "approve",
                "summary": "Bad approval.",
                "findings": [
                    {
                        "id": "CR-001",
                        "severity": "major",
                        "category": "correctness",
                        "file": "",
                        "line": "",
                        "title": "Unsupported blocker",
                        "evidence": "A claim without citation.",
                        "risk": "Unknown.",
                        "recommended_fix": "Add evidence.",
                    }
                ],
                "tests_reviewed": [],
                "missing_tests": [],
                "verification": {
                    "schema_valid": True,
                    "citations_valid": False,
                    "blocking_findings_verified": False,
                },
            }
        )
    )

    result = run_script("validate-output.py", str(review), "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "findings[0].file is required for blocking findings" in payload["errors"]
    assert "findings[0].line is required for blocking findings" in payload["errors"]
    assert "verdict must be request_changes when critical or major findings exist" in payload["errors"]


def test_build_evidence_writes_bundle(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    review = tmp_path / "feedback.json"
    output_root = tmp_path / "evidence"
    discovery.write_text(
        json.dumps(
            {
                "base_ref": "main",
                "head_ref": "HEAD",
                "files": [{"path": "README.md"}],
                "risk_surfaces": ["docs"],
                "commands": ["git diff --name-status -M main...HEAD"],
            }
        )
    )
    review.write_text(
        json.dumps(
            {
                "verdict": "approve",
                "verification": {
                    "citations_valid": True,
                    "blocking_findings_verified": True,
                },
            }
        )
    )

    result = run_script(
        "build-evidence.py",
        "--discovery",
        str(discovery),
        "--review",
        str(review),
        "--run-id",
        "cr_test",
        "--output-root",
        str(output_root),
        "--print-path",
    )

    assert result.returncode == 0, result.stderr
    evidence_path = Path(result.stdout.strip())
    evidence = json.loads(evidence_path.read_text())
    assert evidence["run_id"] == "cr_test"
    assert evidence["capability_id"] == "harnessy.code_review"
    assert evidence["changed_file_count"] == 1
    assert evidence["output_schema_result"] == "pass"
    assert evidence["verifier_result"] == "pass"
    assert evidence["mode"] == "ai_review"
    assert evidence["review_status"] == "completed"
    assert evidence["ci_provider"] == "local"
    assert evidence["gate_result"] == "pass"
    assert evidence["verdict"] == "approve"


def test_harness_code_review_ci_skips_ai_and_writes_artifacts(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "checkout", "-b", "feature/ci-skip")
    (repo / "src.py").write_text("print('hello')\n")
    git(repo, "add", "src.py")
    git(repo, "commit", "-m", "add source")
    output_root = tmp_path / "evidence"

    result = run_script(
        "harness-code-review",
        "ci",
        "--base",
        "main",
        "--head",
        "HEAD",
        "--run-id",
        "cr_ci_skip",
        "--output-root",
        str(output_root),
        "--json",
        cwd=repo,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["gate_result"] == "pass"
    assert payload["mode"] == "deterministic_only"
    assert payload["review_status"] == "skipped"
    run_dir = output_root / "cr_ci_skip"
    assert (run_dir / "discovery.json").exists()
    assert (run_dir / "feedback.json").exists()
    assert (run_dir / "REVIEW_REPORT.md").exists()
    assert (run_dir / "review.sarif").exists()
    assert (run_dir / "evidence.json").exists()
    feedback = json.loads((run_dir / "feedback.json").read_text())
    assert feedback["review_status"] == "skipped"
    sarif = json.loads((run_dir / "review.sarif").read_text())
    assert sarif["runs"][0]["results"] == []
    evidence = json.loads((run_dir / "evidence.json").read_text())
    assert evidence["gate_result"] == "pass"
    assert evidence["review_status"] == "skipped"
    assert payload["evidence_validation"] == {"ok": True, "errors": []}


def test_validate_evidence_accepts_ci_bundle(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "checkout", "-b", "feature/evidence-valid")
    (repo / "src.py").write_text("print('hello')\n")
    git(repo, "add", "src.py")
    git(repo, "commit", "-m", "add source")
    output_root = tmp_path / "evidence"

    gate = run_script(
        "harness-code-review",
        "ci",
        "--base",
        "main",
        "--head",
        "HEAD",
        "--run-id",
        "cr_evidence_valid",
        "--output-root",
        str(output_root),
        "--json",
        cwd=repo,
    )
    assert gate.returncode == 0, gate.stderr

    result = run_script("validate-evidence.py", str(output_root / "cr_evidence_valid" / "evidence.json"), "--json", cwd=repo)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "errors": []}


def test_validate_evidence_rejects_tampered_bundle(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "checkout", "-b", "feature/evidence-tamper")
    (repo / "src.py").write_text("print('hello')\n")
    git(repo, "add", "src.py")
    git(repo, "commit", "-m", "add source")
    output_root = tmp_path / "evidence"

    gate = run_script(
        "harness-code-review",
        "ci",
        "--base",
        "main",
        "--head",
        "HEAD",
        "--run-id",
        "cr_evidence_tamper",
        "--output-root",
        str(output_root),
        "--json",
        cwd=repo,
    )
    assert gate.returncode == 0, gate.stderr

    evidence_path = output_root / "cr_evidence_tamper" / "evidence.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["changed_file_count"] = 99
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")

    result = run_script("validate-evidence.py", str(evidence_path), "--json", cwd=repo)

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "changed_file_count does not match discovery.files length" in payload["errors"]


def test_harness_code_review_symlink_resolves_helper_scripts(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    output_root = tmp_path / "evidence"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    command = bin_dir / "harness-code-review"
    command.symlink_to(SCRIPT_ROOT / "harness-code-review")

    result = subprocess.run(
        [
            sys.executable,
            str(command),
            "ci",
            "--base",
            "HEAD",
            "--head",
            "HEAD",
            "--run-id",
            "cr_symlink",
            "--output-root",
            str(output_root),
            "--json",
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["gate_result"] == "pass"
    assert (output_root / "cr_symlink" / "evidence.json").exists()


def test_harness_code_review_ci_blocks_on_major_review_command_finding(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "checkout", "-b", "feature/blocking")
    (repo / "app.py").write_text("print('changed')\n")
    git(repo, "add", "app.py")
    git(repo, "commit", "-m", "change app")
    writer = tmp_path / "write_review.py"
    writer.write_text(
        """
import json
import os
from pathlib import Path

Path(os.environ["HARNESSY_CODE_REVIEW_FEEDBACK_JSON"]).write_text(json.dumps({
    "schema_version": 1,
    "verdict": "request_changes",
    "summary": "One blocking issue.",
    "findings": [{
        "id": "CR-001",
        "severity": "major",
        "category": "test_gap",
        "file": "app.py",
        "line": 1,
        "title": "Missing regression coverage",
        "evidence": "app.py changed without an accompanying test.",
        "risk": "The behavior can regress without CI catching it.",
        "recommended_fix": "Add an integration test for the changed behavior."
    }],
    "tests_reviewed": [],
    "missing_tests": ["integration test for app.py behavior"],
    "verification": {
        "schema_valid": True,
        "citations_valid": True,
        "blocking_findings_verified": True
    }
}) + "\\n")
""".lstrip()
    )
    output_root = tmp_path / "evidence"
    review_command = f"{shlex.quote(sys.executable)} {shlex.quote(str(writer))}"

    result = run_script(
        "harness-code-review",
        "ci",
        "--base",
        "main",
        "--head",
        "HEAD",
        "--run-id",
        "cr_ci_block",
        "--output-root",
        str(output_root),
        "--review-command",
        review_command,
        "--json",
        cwd=repo,
    )

    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["gate_result"] == "fail"
    assert payload["mode"] == "ai_review"
    assert payload["review_status"] == "completed"
    assert payload["finding_counts"]["major"] == 1
    run_dir = output_root / "cr_ci_block"
    feedback = json.loads((run_dir / "feedback.json").read_text())
    assert feedback["mode"] == "ai_review"
    assert feedback["review_status"] == "completed"
    sarif = json.loads((run_dir / "review.sarif").read_text())
    assert sarif["runs"][0]["results"][0]["level"] == "error"
    evidence = json.loads((run_dir / "evidence.json").read_text())
    assert evidence["gate_result"] == "fail"


def test_harness_code_review_ci_fails_when_ai_required_without_command(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "checkout", "-b", "feature/required-ai")
    (repo / "README.md").write_text("# Demo\n\nChanged.\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "change readme")
    output_root = tmp_path / "evidence"

    result = run_script(
        "harness-code-review",
        "ci",
        "--base",
        "main",
        "--head",
        "HEAD",
        "--run-id",
        "cr_ci_required_ai",
        "--output-root",
        str(output_root),
        "--require-ai",
        "--json",
        cwd=repo,
    )

    assert result.returncode == 3, result.stderr
    payload = json.loads(result.stdout)
    assert payload["gate_result"] == "fail"
    assert payload["review_status"] == "skipped"
    run_dir = output_root / "cr_ci_required_ai"
    assert (run_dir / "evidence.json").exists()
    evidence = json.loads((run_dir / "evidence.json").read_text())
    assert evidence["gate_result"] == "fail"
    assert evidence["skipped_reason"] == "AI review is required but no review command was configured."
