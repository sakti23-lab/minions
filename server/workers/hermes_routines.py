"""Routine operations and run-output projection for the Hermes worker.

Wraps Hermes's `cron.jobs` / `cron.scheduler` modules with input validation,
shape normalization, and a background ticker thread.
"""

from __future__ import annotations

import stat
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from hermes_worker_utils import (
    WorkerError,
    json_safe,
    string_or_none,
    truncate_with_ellipsis,
)


_ROUTINES_TICKER_STARTED = False
_ROUTINES_TICKER_LOCK = threading.Lock()


def _ensure_imports() -> None:
    # Lazy import so this module does not need a top-level dep on hermes_worker.
    # `hermes_worker._ensure_imports()` adds the Hermes agent dir to sys.path,
    # making `cron.jobs` / `cron.scheduler` importable below.
    import hermes_worker

    hermes_worker._ensure_imports()


def _normalize_routine(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(job, dict):
        return None

    job_id = string_or_none(job.get("id")) or ""
    raw_schedule = job.get("schedule")
    raw_origin = job.get("origin")
    raw_skills = job.get("skills")
    if raw_skills is None and job.get("skill"):
        raw_skills = [job.get("skill")]
    raw_context_from = job.get("context_from")
    if isinstance(raw_context_from, str):
        context_from = [raw_context_from]
    elif isinstance(raw_context_from, list):
        context_from = [str(item) for item in raw_context_from if str(item).strip()]
    else:
        context_from = []
    raw_repeat = job.get("repeat")

    return {
        "id": job_id,
        "name": string_or_none(job.get("name")) or job_id,
        "prompt": string_or_none(job.get("prompt")),
        "schedule": json_safe(raw_schedule) if isinstance(raw_schedule, dict) else None,
        "scheduleDisplay": string_or_none(job.get("schedule_display")),
        "enabled": bool(job.get("enabled", True)),
        "state": string_or_none(job.get("state")),
        "nextRunAt": string_or_none(job.get("next_run_at")),
        "lastRunAt": string_or_none(job.get("last_run_at")),
        "lastStatus": string_or_none(job.get("last_status")),
        "lastError": string_or_none(job.get("last_error")),
        "lastDeliveryError": string_or_none(job.get("last_delivery_error")),
        "model": string_or_none(job.get("model")),
        "provider": string_or_none(job.get("provider")),
        "baseUrl": string_or_none(job.get("base_url")),
        "deliver": string_or_none(job.get("deliver")),
        "origin": json_safe(raw_origin) if isinstance(raw_origin, dict) else None,
        "repeat": json_safe(raw_repeat) if isinstance(raw_repeat, dict) else None,
        "contextFrom": context_from,
        "skills": [str(item) for item in raw_skills] if isinstance(raw_skills, list) else [],
        "workdir": string_or_none(job.get("workdir")),
        "createdAt": string_or_none(job.get("created_at")),
    }


def _validate_path_segment(value: Any, label: str) -> str:
    raw = string_or_none(value)
    if not raw:
        raise WorkerError(f"{label} is required.", code="bad_request")
    if "/" in raw or "\\" in raw or ".." in raw:
        raise WorkerError(f"Invalid {label}.", code="bad_request")
    return raw


def _require_string(value: Any, label: str) -> str:
    raw = string_or_none(value)
    if not raw:
        raise WorkerError(f"{label} is required.", code="bad_request")
    return raw


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise WorkerError("repeat must be a number.", code="bad_request") from exc
    return parsed if parsed > 0 else None


def _list_of_strings(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise WorkerError("skills must be a list of strings.", code="bad_request")
    return [str(item).strip() for item in value if str(item).strip()]


def _repeat_update(value: Any) -> dict[str, Any]:
    return {"times": _int_or_none(value), "completed": 0}


def _build_update_dict(request: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}

    string_fields = ("name", "prompt", "schedule", "deliver", "skills", "model", "provider", "workdir")
    for field in string_fields:
        if field not in request:
            continue
        if field == "skills":
            skills = _list_of_strings(request.get(field))
            updates["skills"] = skills
            updates["skill"] = skills[0] if skills else None
        else:
            updates[field] = string_or_none(request.get(field))

    if "baseUrl" in request:
        updates["base_url"] = string_or_none(request.get("baseUrl"))
    if "repeat" in request:
        updates["repeat"] = _repeat_update(request.get("repeat"))
    if "contextFrom" in request:
        updates["context_from"] = request.get("contextFrom") or None

    if not updates:
        raise WorkerError("No routine updates were provided.", code="bad_request")
    return updates


def list_routines(include_disabled: bool = False) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import list_jobs

    jobs = [_normalize_routine(job) for job in list_jobs(include_disabled=include_disabled)]
    return {"jobs": [job for job in jobs if job is not None]}


def get_routine(job_id: Any) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import get_job

    job = _normalize_routine(get_job(_validate_path_segment(job_id, "Routine ID")))
    return {"job": job}


def create_routine(request: dict[str, Any]) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import create_job

    try:
        job = create_job(
            prompt=_require_string(request.get("prompt"), "prompt"),
            schedule=_require_string(request.get("schedule"), "schedule"),
            name=string_or_none(request.get("name")),
            deliver=string_or_none(request.get("deliver")),
            skills=_list_of_strings(request.get("skills")),
            model=string_or_none(request.get("model")),
            provider=string_or_none(request.get("provider")),
            base_url=string_or_none(request.get("baseUrl")),
            workdir=string_or_none(request.get("workdir")),
            repeat=_int_or_none(request.get("repeat")),
            context_from=request.get("contextFrom") or None,
        )
    except ValueError as exc:
        raise WorkerError(str(exc), code="bad_request") from exc
    return {"job": _normalize_routine(job)}


def update_routine(request: dict[str, Any]) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import update_job

    job_id = _validate_path_segment(request.get("jobId"), "Routine ID")
    try:
        job = _normalize_routine(update_job(job_id, _build_update_dict(request)))
    except ValueError as exc:
        raise WorkerError(str(exc), code="bad_request") from exc
    return {"job": job}


def pause_routine(job_id: Any, reason: Any = None) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import pause_job

    routine_id = _validate_path_segment(job_id, "Routine ID")
    return {"job": _normalize_routine(pause_job(routine_id, reason=string_or_none(reason)))}


def resume_routine(job_id: Any) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import resume_job

    return {"job": _normalize_routine(resume_job(_validate_path_segment(job_id, "Routine ID")))}


def trigger_routine(job_id: Any) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import trigger_job

    routine_id = _validate_path_segment(job_id, "Routine ID")
    job = _normalize_routine(trigger_job(routine_id))
    if job is not None:
        _kick_immediate_tick()
    return {"job": job}


def _kick_immediate_tick() -> None:
    """Fire a scheduler tick in the background so a just-triggered job runs
    now instead of waiting up to one full periodic-ticker interval (~60s).

    Hermes's `tick()` uses a non-blocking file lock so this is safe to run
    alongside the periodic ticker — only one will execute and the other
    returns 0.
    """
    def _run() -> None:
        try:
            tick_routines()
        except Exception as exc:  # noqa: BLE001 — log and swallow, this is best-effort
            print(f"[hermes-worker] immediate routine tick failed: {exc}", file=sys.stderr, flush=True)

    threading.Thread(target=_run, name="hermes-routines-trigger", daemon=True).start()


def remove_routine(job_id: Any) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import remove_job

    return {"ok": bool(remove_job(_validate_path_segment(job_id, "Routine ID")))}


def _extract_run_body(content: str) -> str | None:
    """Return the body of the `## Response` or `## Error` section, if present.

    Hermes writes every run as a markdown file whose first ~1KB is metadata
    (job id, run time, schedule, the full prompt including its [IMPORTANT: …]
    preamble). None of that is useful in the UI, so we strip down to the body
    of the response/error section before returning run previews or content.
    """
    lines = content.split("\n")
    for marker in ("## Response", "## Error"):
        for index, line in enumerate(lines):
            if line.strip() == marker:
                return "\n".join(lines[index + 1:]).strip()
    return None


def _run_body(content: str) -> str:
    return (_extract_run_body(content) or content).strip()


def _run_preview(content: str, max_chars: int = 240) -> str:
    body = _run_body(content)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return truncate_with_ellipsis("\n".join(lines[:4]), max_chars)


def _run_timestamp_from_stem(stem: str) -> str | None:
    try:
        return datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S").isoformat()
    except ValueError:
        return None


def _routine_run_status(content: str) -> str:
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    if first_line.startswith("# Cron Job:") and "(FAILED)" in first_line:
        return "error"
    if first_line.startswith("# Cron Job:"):
        return "ok"
    return "unknown"


def _read_run_head(path: Path, max_bytes: int = 8192) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)
    except OSError:
        return ""


def list_routine_runs(job_id: Any, limit: Any = 20) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import OUTPUT_DIR

    routine_id = _validate_path_segment(job_id, "Routine ID")
    try:
        parsed_limit = int(limit)
    except (TypeError, ValueError):
        parsed_limit = 20
    parsed_limit = max(1, min(parsed_limit, 100))

    output_dir = Path(OUTPUT_DIR) / routine_id
    entries: list[tuple[float, Path]] = []
    for path in output_dir.glob("*.md"):
        try:
            st = path.stat()
        except OSError:
            continue
        if not stat.S_ISREG(st.st_mode):
            continue
        entries.append((st.st_mtime, path))
    entries.sort(key=lambda entry: (entry[0], entry[1].name), reverse=True)

    runs: list[dict[str, Any]] = []
    for _, path in entries[:parsed_limit]:
        head = _read_run_head(path)
        runs.append({
            "id": path.stem,
            "jobId": routine_id,
            "ranAt": _run_timestamp_from_stem(path.stem),
            "path": str(path),
            "status": _routine_run_status(head),
            "preview": _run_preview(head),
        })

    return {"runs": runs}


def get_routine_run_content(job_id: Any, run_id: Any) -> dict[str, Any]:
    _ensure_imports()
    from cron.jobs import OUTPUT_DIR

    routine_id = _validate_path_segment(job_id, "Routine ID")
    raw_run_id = _validate_path_segment(run_id, "Run ID")

    path = Path(OUTPUT_DIR) / routine_id / f"{raw_run_id}.md"
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise WorkerError("Routine run output not found.", code="not_found") from exc
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")

    return {
        "body": _run_body(content),
        "status": _routine_run_status(content),
    }


def tick_routines() -> int:
    _ensure_imports()
    from cron.scheduler import tick

    return int(tick(verbose=False) or 0)


def _routines_ticker_loop() -> None:
    while True:
        try:
            executed = tick_routines()
            if executed:
                print(f"[hermes-worker] routine tick executed {executed} job(s)", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"[hermes-worker] routine tick failed: {exc}", file=sys.stderr, flush=True)
        time.sleep(60)


def start_routine_ticker() -> None:
    global _ROUTINES_TICKER_STARTED
    with _ROUTINES_TICKER_LOCK:
        if _ROUTINES_TICKER_STARTED:
            return
        thread = threading.Thread(target=_routines_ticker_loop, name="hermes-routines-ticker", daemon=True)
        thread.start()
        _ROUTINES_TICKER_STARTED = True
