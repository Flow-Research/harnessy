from __future__ import annotations

import json
import os
import subprocess
import tarfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS_DEPLOY = REPO_ROOT / "tools" / "flow-install" / "skills" / "service-deploy" / "scripts" / "harness-deploy"


def write_profiles(root: Path, *, adapter: str = "mock", app: dict | None = None) -> None:
    profiles = root / ".jarvis" / "context" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "qa.json").write_text(
        json.dumps(
            {
                "version": 1,
                "specs": [{"path": "qa/browser/scripts/web.md", "app": "web", "layer": "browser"}],
                "apps": [{"id": "web", "tests": {"browser": ["tests/browser"]}}],
                "output": {"coverage": "qa/coverage.md"},
            }
        )
    )
    (profiles / "ci.json").write_text(
        json.dumps(
            {
                "version": 1,
                "project": {"name": "fixture", "integrationBranch": "main"},
                "release": {
                    "versionFile": "VERSION",
                    "changelogFile": "CHANGELOG.md",
                    "productionTrigger": "semver-tag",
                    "tagPattern": "v*.*.*",
                },
                "qa": {"profile": ".jarvis/context/profiles/qa.json", "requiredGates": []},
                "gates": [{"name": "passing gate", "command": "python3 -c 'print(1)'", "required": True}],
                "policy": {"allowLocalOverride": True, "requireSameGatesForLocalOverride": True},
            }
        )
    )
    (profiles / "deploy.json").write_text(
        json.dumps(
            {
                "version": 1,
                "defaultEnvironment": "canary",
                "apps": [app or {"id": "web", "type": "static", "root": ".", "outputDir": "dist", "package": "auto"}],
                "environments": {
                    "canary": {
                        "provider": "hostinger",
                        "adapter": adapter,
                        "strategy": "canary",
                        "url": "https://fixture.example",
                    }
                },
                "providerPolicy": {
                    "forbidBillingActions": True,
                    "forbidDestructiveActions": True,
                    "forbidDnsMutation": True,
                },
                "evidence": {"persist": True, "root": ".jarvis/context/deployments"},
            }
        )
    )


def run_deploy(root: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(HARNESS_DEPLOY), *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_plan_and_check_read_profiles(tmp_path: Path) -> None:
    write_profiles(tmp_path)
    result = run_deploy(tmp_path, "plan", "--json")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["provider"] == "hostinger"
    assert plan["adapter"] == "mock"
    assert plan["runtimeModes"] == ["static"]

    result = run_deploy(tmp_path, "check", "--json")
    assert result.returncode == 0, result.stderr
    check = json.loads(result.stdout)
    assert check["ok"] is True
    assert check["gates"][0]["ok"] is True


def test_configure_writes_gitignored_hostinger_env(tmp_path: Path) -> None:
    write_profiles(tmp_path)
    env = {
        **dict(os.environ),
        "HOSTINGER_API_TOKEN": "secret-test-token",
    }

    result = run_deploy(tmp_path, "configure", "--no-prompt", "--json", env=env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    env_path = tmp_path / payload["envFile"]["path"]
    assert env_path.exists()
    assert payload["envFile"]["hasHostingerToken"] is True
    assert "secret-test-token" not in result.stdout
    assert env_path.stat().st_mode & 0o777 == 0o600
    content = env_path.read_text()
    assert "HOSTINGER_API_TOKEN=secret-test-token" in content
    assert "HAPI_API_TOKEN=secret-test-token" in content


def test_targets_uses_local_env_file_without_printing_token(tmp_path: Path) -> None:
    write_profiles(tmp_path)
    env_file = tmp_path / ".jarvis" / "context" / "profiles" / "local" / "hostinger.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("HOSTINGER_API_TOKEN=secret-test-token\nHAPI_API_TOKEN=secret-test-token\n")
    env_file.chmod(0o600)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    hapi = bin_dir / "hapi"
    hapi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "assert os.environ.get('HAPI_API_TOKEN') == 'secret-test-token'\n"
        "print(json.dumps([{'id': 123, 'hostname': 'srv123.hstgr.cloud', 'state': 'running', 'ipv4': '192.0.2.10'}]))\n"
    )
    hapi.chmod(0o755)
    env = {**dict(os.environ), "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}

    result = run_deploy(tmp_path, "targets", "--write-selection", "--json", env=env)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["targets"][0]["id"] == 123
    assert payload["targets"][0]["hostname"] == "srv123.hstgr.cloud"
    assert payload["selectedTargetId"] == "123"
    assert "HOSTINGER_VPS_ID=123" in env_file.read_text()
    assert "secret-test-token" not in result.stdout


def test_package_excludes_secret_and_node_modules(tmp_path: Path) -> None:
    write_profiles(tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<h1>ok</h1>")
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / ".jarvis" / "context" / "profiles" / "local").mkdir(parents=True)
    (tmp_path / ".jarvis" / "context" / "profiles" / "local" / "hostinger.env").write_text("HOSTINGER_API_TOKEN=secret")
    (tmp_path / ".streamlit").mkdir()
    (tmp_path / ".streamlit" / "secrets.toml").write_text("password='secret'")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("module.exports = 1")

    result = run_deploy(tmp_path, "package", "--run-id", "run-test", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    package_path = tmp_path / payload["package"]
    assert package_path.exists()

    with tarfile.open(package_path, "r:gz") as archive:
        names = archive.getnames()
    assert "dist/index.html" in names
    assert ".env" not in names
    assert ".jarvis/context/profiles/local/hostinger.env" not in names
    assert ".streamlit/secrets.toml" not in names
    assert "node_modules/pkg/index.js" not in names


def test_deploy_local_override_records_mock_evidence(tmp_path: Path) -> None:
    write_profiles(tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<h1>ok</h1>")

    result = run_deploy(tmp_path, "deploy", "--local-override", "--run-id", "run-deploy", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    evidence_dir = tmp_path / payload["evidenceDir"]
    assert payload["provider"]["status"] == "succeeded"
    assert (evidence_dir / "manifest.json").exists()
    assert (evidence_dir / "provider-response.json").exists()
    assert (evidence_dir / "smoke.json").exists()
    assert (evidence_dir / "trace.json").exists()


def test_live_hostinger_without_dry_run_is_blocked(tmp_path: Path) -> None:
    write_profiles(tmp_path, adapter="mcp")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<h1>ok</h1>")

    result = run_deploy(tmp_path, "deploy", "--local-override", "--run-id", "run-live", "--json")
    assert result.returncode != 0
    assert "Live Hostinger execution is not enabled in v1" in result.stderr


def test_systemd_runtime_is_supported_when_profile_is_complete(tmp_path: Path) -> None:
    write_profiles(
        tmp_path,
        app={
            "id": "econ-sim",
            "type": "python",
            "root": ".",
            "package": "auto",
            "runtime": {
                "mode": "systemd",
                "serviceName": "econ-sim",
                "startCommand": "uv run streamlit run src/econ_sim/app.py --server.port 8501",
                "workingDirectory": "/opt/econ-sim/current",
                "port": 8501,
                "healthcheckPath": "/_stcore/health",
            },
        },
    )

    result = run_deploy(tmp_path, "plan", "--json")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["runtimeModes"] == ["systemd"]
    assert plan["deploymentUnits"][0]["serviceName"] == "econ-sim"
    assert plan["deploymentUnits"][0]["healthcheckPath"] == "/_stcore/health"

    result = run_deploy(tmp_path, "check", "--json")
    assert result.returncode == 0, result.stderr
    check = json.loads(result.stdout)
    assert check["ok"] is True


def test_systemd_runtime_requires_service_name_and_start_command(tmp_path: Path) -> None:
    write_profiles(
        tmp_path,
        app={
            "id": "broken",
            "type": "python",
            "root": ".",
            "runtime": {"mode": "systemd"},
        },
    )

    result = run_deploy(tmp_path, "check", "--json")
    assert result.returncode != 0
    check = json.loads(result.stdout)
    rules = {issue["rule"] for issue in check["issues"]}
    assert "systemd-service-name" in rules
    assert "systemd-start-command" in rules


def test_docker_compose_runtime_is_configurable(tmp_path: Path) -> None:
    write_profiles(
        tmp_path,
        app={
            "id": "econ-sim",
            "type": "python",
            "root": ".",
            "package": "auto",
            "runtime": {
                "mode": "docker-compose",
                "composeFile": "docker-compose.yml",
                "serviceName": "econ-sim",
                "healthcheckPath": "/_stcore/health",
            },
        },
    )

    result = run_deploy(tmp_path, "plan", "--json")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["runtimeModes"] == ["docker-compose"]
    assert plan["deploymentUnits"][0]["composeFile"] == "docker-compose.yml"

    result = run_deploy(tmp_path, "check", "--json")
    assert result.returncode == 0, result.stderr


def test_internal_subprocess_helper_propagates_env(tmp_path: Path) -> None:
    script = (
        "import importlib.machinery, pathlib, sys\n"
        f"path = pathlib.Path({str(HARNESS_DEPLOY)!r})\n"
        "module = importlib.machinery.SourceFileLoader('harness_deploy_script', str(path)).load_module()\n"
        "result = module.run_subprocess(\n"
        "    [sys.executable, '-c', 'import os; print(os.environ.get(\"HARNESS_TEST_ENV\"))'],\n"
        "    env={'HARNESS_TEST_ENV': 'present'},\n"
        ")\n"
        "assert result.returncode == 0\n"
        "assert result.stdout.strip() == 'present'\n"
    )
    result = subprocess.run(["python3", "-c", script], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_internal_remote_bash_command_is_single_line(tmp_path: Path) -> None:
    script = (
        "import importlib.machinery, pathlib\n"
        f"path = pathlib.Path({str(HARNESS_DEPLOY)!r})\n"
        "module = importlib.machinery.SourceFileLoader('harness_deploy_script', str(path)).load_module()\n"
        "command = module.encoded_remote_bash_command('echo one\\necho two\\n')\n"
        "assert '\\n' not in command\n"
        "assert 'base64 -d | bash' in command\n"
    )
    result = subprocess.run(["python3", "-c", script], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_internal_ssh_options_use_configured_identity(tmp_path: Path) -> None:
    key_path = tmp_path / "deploy_key"
    key_path.write_text("placeholder")
    script = (
        "import importlib.machinery, pathlib\n"
        f"path = pathlib.Path({str(HARNESS_DEPLOY)!r})\n"
        "module = importlib.machinery.SourceFileLoader('harness_deploy_script', str(path)).load_module()\n"
        f"options = module.ssh_client_options(None, {{'HOSTINGER_SSH_KEY': {str(key_path)!r}}})\n"
        f"assert {str(key_path)!r} in options\n"
        "assert 'IdentitiesOnly=yes' in options\n"
    )
    result = subprocess.run(["python3", "-c", script], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_internal_public_url_uses_configured_public_port(tmp_path: Path) -> None:
    script = (
        "import importlib.machinery, pathlib\n"
        f"path = pathlib.Path({str(HARNESS_DEPLOY)!r})\n"
        "module = importlib.machinery.SourceFileLoader('harness_deploy_script', str(path)).load_module()\n"
        "url = module.public_url_for_env({}, {}, {'hostname': 'srv.example'}, {'publicPort': 8081})\n"
        "assert url == 'http://srv.example:8081'\n"
    )
    result = subprocess.run(["python3", "-c", script], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_internal_websocket_url_preserves_host_port(tmp_path: Path) -> None:
    script = (
        "import importlib.machinery, pathlib\n"
        f"path = pathlib.Path({str(HARNESS_DEPLOY)!r})\n"
        "module = importlib.machinery.SourceFileLoader('harness_deploy_script', str(path)).load_module()\n"
        "url = module.websocket_url_for_http_url('http://srv.example:8081', '/_stcore/stream')\n"
        "assert url == 'ws://srv.example:8081/_stcore/stream'\n"
    )
    result = subprocess.run(["python3", "-c", script], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
