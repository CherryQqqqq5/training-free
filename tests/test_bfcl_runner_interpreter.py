import json
import subprocess
import sys
from pathlib import Path

from scripts.check_bfcl_runner_interpreter import check_script

CHECKER = Path("scripts/check_bfcl_runner_interpreter.py")
RUNNER = Path("scripts/run_bfcl_v4_baseline.sh")


def test_baseline_runner_uses_resolved_interpreter():
    result = subprocess.run([sys.executable, str(CHECKER), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["bfcl_runner_interpreter_passed"] is True
    text = RUNNER.read_text()
    assert 'GRC_PYTHON="${GRC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"' in text
    assert 'BFCL_CLI=("${GRC_PYTHON}" "${REPO_ROOT}/scripts/run_bfcl_cli.py")' in text
    assert 'GRC_CLI=("${GRC_PYTHON}" -m grc.cli)' in text
    assert 'python "${REPO_ROOT}/scripts/' not in text
    assert 'python - ' not in text


def test_checker_rejects_array_bare_python(tmp_path):
    script = tmp_path / "runner.sh"
    script.write_text('GRC_PYTHON="${GRC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"\nif [[ ! -x "${GRC_PYTHON}" ]]; then exit 2; fi\nBFCL_CLI=(python script.py)\n')
    summary = check_script(script)
    assert summary["bfcl_runner_interpreter_passed"] is False
    assert any(blocker.startswith("bare_python_invocation:") for blocker in summary["blockers"])


def test_checker_rejects_inline_bare_python(tmp_path):
    script = tmp_path / "runner.sh"
    script.write_text('GRC_PYTHON="${GRC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"\nif [[ ! -x "${GRC_PYTHON}" ]]; then exit 2; fi\npython - <<\'PY\'\nprint("x")\nPY\n')
    summary = check_script(script)
    assert summary["bfcl_runner_interpreter_passed"] is False
    assert any(blocker.startswith("bare_python_invocation:") for blocker in summary["blockers"])


def test_checker_accepts_grc_python(tmp_path):
    script = tmp_path / "runner.sh"
    script.write_text('GRC_PYTHON="${GRC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"\nif [[ ! -x "${GRC_PYTHON}" ]]; then exit 2; fi\n"${GRC_PYTHON}" script.py\n"${GRC_PYTHON}" - <<\'PY\'\nprint("x")\nPY\n')
    summary = check_script(script)
    assert summary["bfcl_runner_interpreter_passed"] is True


def test_checker_rejects_missing_executable_guard(tmp_path):
    script = tmp_path / "runner.sh"
    script.write_text('GRC_PYTHON="${GRC_PYTHON:-${REPO_ROOT}/.venv/bin/python}"\n"${GRC_PYTHON}" script.py\n')
    summary = check_script(script)
    assert summary["bfcl_runner_interpreter_passed"] is False
    assert "runner_interpreter_executable_guard_missing" in summary["blockers"]
