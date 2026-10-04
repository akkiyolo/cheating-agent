"""Docker code sandbox.

Generated code is never executed on the host. Each run gets a fresh container with:
  * ``--network none``           no network
  * ``--cpus / --memory / --pids-limit``   resource limits
  * ``--read-only`` + tmpfs ``/tmp``       ephemeral writable scratch only
  * ``--cap-drop ALL``, ``no-new-privileges``, uid 65534   minimal privileges
  * per-test ``timeout`` inside, plus a host-side wall-clock kill, ``--rm`` cleanup

Limits come from frozen settings; the agent's tools expose no parameter that can change them.
"""

from __future__ import annotations

import asyncio
import base64
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.services.grading import outputs_match

LANGUAGES = {
    "python": {"file": "main.py"},
    "cpp": {"file": "main.cpp"},
    "java": {"file": "Main.java"},
}

RUN_SH = r"""#!/bin/sh
set -u
L="$1"; N="$2"; TL="$3"
cd /tmp
case "$L" in
  python) cp /work/main.py /tmp/main.py
          python3 -m py_compile /tmp/main.py 2>/tmp/ce.txt || { echo "__COMPILE_ERROR__"; base64 -w0 /tmp/ce.txt; echo; exit 3; }
          set -- python3 /tmp/main.py ;;
  cpp)    g++ -O2 -std=c++17 -o /tmp/main /work/main.cpp 2>/tmp/ce.txt || { echo "__COMPILE_ERROR__"; base64 -w0 /tmp/ce.txt; echo; exit 3; }
          set -- /tmp/main ;;
  java)   mkdir -p /tmp/j && cp /work/Main.java /tmp/j/Main.java
          javac -J-Xmx256m -d /tmp/j /tmp/j/Main.java 2>/tmp/ce.txt || { echo "__COMPILE_ERROR__"; base64 -w0 /tmp/ce.txt; echo; exit 3; }
          set -- java -Xss64m -Xmx256m -XX:+UseSerialGC -cp /tmp/j Main ;;
  *) echo "__BAD_LANGUAGE__"; exit 4 ;;
esac
echo "__COMPILED__"
i=0
while [ "$i" -lt "$N" ]; do
  s=$(date +%s%N)
  timeout "$TL" "$@" < "/work/in$i.txt" > "/tmp/out.txt" 2> "/tmp/err.txt"
  rc=$?
  e=$(date +%s%N)
  head -c 1048576 /tmp/out.txt > /tmp/out2.txt
  head -c 4000 /tmp/err.txt > /tmp/err2.txt
  echo "__CASE__ $i $rc $(( (e - s) / 1000000 )) $(base64 -w0 /tmp/out2.txt) $(base64 -w0 /tmp/err2.txt)"
  i=$((i + 1))
done
"""


class TestCase(BaseModel):
    __test__ = False  # not a pytest test class

    input: str = ""
    output: str | None = None  # expected; None = just capture output


class CaseResult(BaseModel):
    index: int
    passed: bool | None
    exit_code: int
    timed_out: bool
    time_ms: int
    stdout: str
    stderr: str
    expected: str | None = None
    input_preview: str = ""


class SandboxResult(BaseModel):
    language: str
    compiled: bool
    compile_error: str | None = None
    passed: bool
    tests_passed: int = 0
    tests_failed: int = 0
    execution_time_ms: int = 0
    cases: list[CaseResult] = Field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class SandboxLimits:
    cpus: float
    memory_mb: int
    pids: int
    per_test_timeout_s: float

    @classmethod
    def from_settings(cls, s: Settings, language: str) -> SandboxLimits:
        mem = max(s.sandbox_memory_mb, 640) if language == "java" else s.sandbox_memory_mb
        return cls(s.sandbox_cpus, mem, s.sandbox_pids, s.sandbox_timeout_s)


class SandboxUnavailable(RuntimeError):
    pass


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, timeout=15)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class DockerSandbox:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def image_for(self, language: str) -> str:
        return {
            "python": self.settings.sandbox_python_image,
            "cpp": self.settings.sandbox_cpp_image,
            "java": self.settings.sandbox_java_image,
        }[language]

    async def run(self, language: str, code: str, tests: list[TestCase]) -> SandboxResult:
        return await asyncio.to_thread(self.run_sync, language, code, tests)

    def run_sync(self, language: str, code: str, tests: list[TestCase]) -> SandboxResult:
        if language not in LANGUAGES:
            return SandboxResult(language=language, compiled=False, passed=False,
                                 error=f"unsupported language {language}")
        if not tests:
            tests = [TestCase(input="")]
        limits = SandboxLimits.from_settings(self.settings, language)
        work = Path(tempfile.mkdtemp(prefix="sbx-", dir=self.settings.sandbox_workdir))
        work.chmod(0o755)  # mkdtemp is 0700; the sandbox user (65534) must be able to read it
        name = f"cheating-agent-sbx-{uuid.uuid4().hex[:12]}"
        try:
            (work / LANGUAGES[language]["file"]).write_text(code, encoding="utf-8", newline="\n")
            (work / "run.sh").write_text(RUN_SH, encoding="utf-8", newline="\n")
            for i, t in enumerate(tests):
                (work / f"in{i}.txt").write_text(t.input, encoding="utf-8", newline="\n")
            cmd = [
                "docker", "run", "--rm", "--name", name,
                "--network", "none",
                f"--cpus={limits.cpus}",
                f"--memory={limits.memory_mb}m", f"--memory-swap={limits.memory_mb}m",
                f"--pids-limit={limits.pids}",
                "--read-only", "--tmpfs", "/tmp:rw,exec,nosuid,size=128m",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", "65534:65534", "-e", "HOME=/tmp",
                "-v", f"{work}:/work:ro",
                self.image_for(language),
                "sh", "/work/run.sh", language, str(len(tests)), f"{limits.per_test_timeout_s:g}",
            ]
            wall = 60 + limits.per_test_timeout_s * len(tests)
            t0 = time.perf_counter()
            try:
                proc = subprocess.run(cmd, capture_output=True, timeout=wall)
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "kill", name], capture_output=True)
                return SandboxResult(language=language, compiled=False, passed=False,
                                     error="sandbox wall-clock timeout")
            except OSError as e:
                raise SandboxUnavailable(str(e)) from e
            elapsed = int((time.perf_counter() - t0) * 1000)
            out = proc.stdout.decode("utf-8", "replace")
            if proc.returncode == 125 or ("docker" in proc.stderr.decode(errors="replace").lower()
                                          and "__COMPILED__" not in out and "__COMPILE_ERROR__" not in out):
                raise SandboxUnavailable(proc.stderr.decode("utf-8", "replace")[:2000])
            return self._parse(language, out, tests, elapsed)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    @staticmethod
    def _parse(language: str, out: str, tests: list[TestCase], elapsed: int) -> SandboxResult:
        lines = out.splitlines()
        if lines and lines[0] == "__COMPILE_ERROR__":
            err = base64.b64decode(lines[1]).decode("utf-8", "replace") if len(lines) > 1 else ""
            return SandboxResult(language=language, compiled=False, compile_error=err[:4000], passed=False,
                                 tests_failed=len(tests), execution_time_ms=elapsed)
        cases: list[CaseResult] = []
        for ln in lines:
            if not ln.startswith("__CASE__"):
                continue
            parts = ln.split(" ")
            idx, rc, ms = int(parts[1]), int(parts[2]), int(parts[3])
            stdout = base64.b64decode(parts[4]).decode("utf-8", "replace") if len(parts) > 4 and parts[4] else ""
            stderr = base64.b64decode(parts[5]).decode("utf-8", "replace") if len(parts) > 5 and parts[5] else ""
            t = tests[idx]
            timed_out = rc == 124
            passed = None if t.output is None else (rc == 0 and outputs_match(t.output, stdout))
            cases.append(CaseResult(index=idx, passed=passed, exit_code=rc, timed_out=timed_out, time_ms=ms,
                                    stdout=stdout[:20000], stderr=stderr, expected=t.output,
                                    input_preview=t.input[:300]))
        n_pass = sum(1 for c in cases if c.passed)
        graded = [c for c in cases if c.passed is not None]
        n_fail = len(tests) - n_pass if graded else 0
        all_ran = len(cases) == len(tests)
        passed = all_ran and all(c.passed is not False for c in cases) and all(c.exit_code == 0 for c in cases)
        return SandboxResult(language=language, compiled=True, passed=passed, tests_passed=n_pass,
                             tests_failed=n_fail, execution_time_ms=sum(c.time_ms for c in cases), cases=cases,
                             error=None if all_ran else "sandbox terminated before all tests ran")
