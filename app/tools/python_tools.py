import ast
import os
import resource
import signal
import subprocess
import sys
import time

from langchain_core.tools import tool
from pydantic import BaseModel, Field


# Where the model's scripts land. Inside the app so you and the model share
# the same eye on side effects; delete the dir anytime.
WORKSPACE_ROOT = os.path.join(os.getcwd(), "python_workspace")

# Hard resource ceilings applied inside the child before exec. Tunes:
#   memory  2 GB   - big-but-finite lists are fine, 16 GB leaks are not
#   fsize   64 MB  - disk-filling write loops stop
#   nproc   512    - fork bombs stop (per-user in-container; 512 is plenty for
#                        normal scripts and still lets the harness breathe)
#   nofile  256    - fd-exhaustion loops stop
#   cpu     2 * timeout (set per-call)
_MEM_LIMIT = 2 * 1024 ** 3
_FSIZE_LIMIT = 64 * 1024 ** 2
_NPROC_LIMIT = 512
_NOFILE_LIMIT = 256
_OUTPUT_CAP = 64 * 1024  # bytes of stdout+stderr we will keep in the report


def _apply_limits(cpu_seconds: int):
    """Runs in the child after fork(), before exec() - kernel-enforced."""
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT, _MEM_LIMIT))
    resource.setrlimit(resource.RLIMIT_FSIZE, (_FSIZE_LIMIT, _FSIZE_LIMIT))
    resource.setrlimit(resource.RLIMIT_NPROC, (_NPROC_LIMIT, _NPROC_LIMIT))
    resource.setrlimit(resource.RLIMIT_NOFILE, (_NOFILE_LIMIT, _NOFILE_LIMIT))


def _truncate(data: bytes, cap: int = _OUTPUT_CAP) -> str:
    """Keep head + tail within a byte cap so a 2 GB log can't blow the context."""
    text = data.decode("utf-8", errors="replace")
    if len(text) <= cap:
        return text, False
    half = cap // 2
    head = text[:half]
    tail = text[-half:]
    omitted = len(text) - len(head) - len(tail)
    return head + f"\n... [{omitted} chars truncated ...]\n" + tail, True

class RunPythonInput(BaseModel):
    code: str = Field(description="The Python source code snippet to run.")
    args: list[str] = Field(default_factory=list, description="Optional list of CLI arguments.")
    stdin: str = Field(default="", description="Optional text to feed into standard input.")
    timeout: int = Field(default=10, description="Seconds before the process is killed.")


@tool(args_schema=RunPythonInput)
def run_python(
    code: str,
    args: list[str] = [],
    stdin: str = "",
    timeout: int = 10,
) -> str:
    """
    Actually EXECUTE a Python snippet in an isolated child process and report
    the real result (stdout, stderr, exit code, timing). Use validate_python
    first for a free static check; use this when you need the code to run.

    Isolation (the boundary, honestly scoped):
      - separate process, no shared state with the harness
      - kernel rlimits: 2 GB memory, 64 MB max file size, 512 processes,
        256 open files, CPU bounded by timeout
      - wall-clock timeout (default 10 s); the whole process group is killed
        on exceed, including any child processes this script spawned
    It stops RUNAWAY behavior (infinite loops, memory/disk/fd blowups). It is
    not a security sandbox against adversarial code (that needs a container).

    Args:
      code:     the Python source to run. Its top level IS the entry point.
      args:     optional list of CLI args, available as sys.argv[1:] in the code.
      stdin:    optional text to feed the script's standard input.
      timeout:  wall-clock seconds before the whole process group is killed.

    Returns a === RUN RESULT === block with status OK / FAIL, duration_ms,
    the workspace dir (inspect it with read_file), stdout, and stderr.
    """
    code = (code or "").strip()
    if not code:
        return (
            "=== RUN RESULT ===\n"
            "status: FAIL\n"
            "reason: no code provided (empty)\n"
        )

    # 1) fresh workspace dir per run, write the script, run with cwd there
    os.makedirs(WORKSPACE_ROOT, exist_ok=True)
    run_dir = os.path.join(WORKSPACE_ROOT, time.strftime("%Y%m%d-%H%M%S-") + str(int(time.time() * 1e6) % 1_000_000))
    os.makedirs(run_dir, exist_ok=True)
    main_path = os.path.join(run_dir, "main.py")
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(code)

    timeout = max(1, int(timeout))
    cmd = [sys.executable, "-I", main_path, *list(args or [])]

    proc = None
    timed_out = False
    stdout_b = b""
    stderr_b = b""
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=run_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # own process group -> killpg reaches children
            preexec_fn=lambda: _apply_limits(cpu_seconds=2 * timeout),
        )
        try:
            stdout_b, stderr_b = proc.communicate(
                input=(stdin or "").encode("utf-8"), timeout=timeout
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            # kill the whole group (script + anything it spawned)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
            try:
                stdout_b, stderr_b = proc.communicate(timeout=5)
            except Exception:
                stdouts = stdout_b, stderr_b = b"", b""
            proc.wait(timeout=5)
    except Exception as e:
        return (
            "=== RUN RESULT ===\n"
            "status: FAIL\n"
            f"reason: failed to launch subprocess: {e}\n"
        )
    duration_ms = int((time.monotonic() - start) * 1000)
    exit_code = proc.returncode if proc is not None else -1

    stdout_s, out_trunc = _truncate(stdout_b or b"")
    stderr_s, err_trunc = _truncate(stderr_b or b"")
    truncated = out_trunc or err_trunc

    status = "OK" if (exit_code == 0 and not timed_out) else "FAIL"
    if timed_out:
        status_detail = f"FAIL (timeout after {timeout}s; process group killed)"
    else:
        status_detail = f"{'OK' if exit_code == 0 else 'FAIL'} (exit {exit_code})"

    lines = [
        "=== RUN RESULT ===",
        f"status: {status_detail}",
        f"duration_ms: {duration_ms}",
        f"workspace: {run_dir}",
        "stdout:",
        stdout_s.strip(),
        "stderr:",
        stderr_s.strip(),
        f"truncated: {'yes' if truncated else 'no'}",
    ]
    return "\n".join(lines)
# Modules that are network / process / exec-related. Flagged (not blocked) so
# the model is aware; the run tool is where you'd hard-enforce if you want.
DANGEROUS_IMPORTS = {
    "socket", "subprocess", "http", "urllib", "requests",
    "importlib", "ctypes", "asyncio", "multiprocessing", "threading", "ssl",
}



@tool
def validate_python(code: str, filename: str = "snippet.py") -> str:
    """
    Statically validate a Python snippet WITHOUT executing it - safe to call on
    every draft, no side effects.

    Checks:
      - syntax / byte-compile (compile() stops before running)
      - imports present
      - risky imports and dynamic calls (eval/exec/importlib) as warnings

    Returns a readable report with `status: OK` or `status: FAIL`.
    Warnings are heads-ups, not failures. To actually execute, use run_python.
    """
    code = (code or "").strip()
    if not code:
        return (
            "=== VALIDATION ===\n"
            "status: FAIL\n"
            "reason: no code provided (empty)\n"
        )

    imports: list[str] = []
    warnings: list[str] = []
    lines = ["=== VALIDATION ===", f"filename: {filename}"]

    # 1) syntax / byte-compile — NEVER runs the code.
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError as e:
        return "\n".join([
            *lines,
            "status: FAIL",
            "syntax: ERROR",
            f"  line {e.lineno}: {e.msg or 'invalid syntax'}",
            "hint: fix the syntax error, then re-validate.",
        ]) + "\n"

    lines.append("syntax: OK")

    # 2) walk the AST for imports + dynamic calls.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                if alias.name.split(".")[0] in DANGEROUS_IMPORTS:
                    warnings.append(f"line {node.lineno}: imports sensitive module '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if node.module:
                imports.append(node.module)
                if top in DANGEROUS_IMPORTS:
                    warnings.append(f"line {node.lineno}: imports sensitive module '{node.module}'")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in ("eval", "exec"):
                warnings.append(f"line {node.lineno}: uses {f.id}() - dynamic, can't be fully validated")

    # 3) assemble report. Warnings never fail the run.
    lines.append("status: OK")
    lines.append("imports: " + (", ".join(sorted(set(imports))) if imports else "(none)"))
    if warnings:
        lines.append("warnings:")
        lines.extend("  " + w for w in warnings)
    else:
        lines.append("warnings: (none)")
    lines.append("note: static checks only - nothing was executed. Use run_python to actually run it.")
    return "\n".join(lines) + "\n"