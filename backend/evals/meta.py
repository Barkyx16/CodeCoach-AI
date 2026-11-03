"""What an evaluation report records so it can be reproduced, and whether two reports compare.

A report names the commit it ran on (and whether the tree had uncommitted changes), every dataset
with its version and content hash, the rubric version, the coach prompt version and a fingerprint
of the prompts and request settings, the provider and model, the configuration, and when it ran.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import platform
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
MANIFEST = EVAL_DIR / "datasets.json"
PROMPT_REGISTRY = EVAL_DIR / "prompt_versions.json"
REPORT_SCHEMA = 2


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def datasets() -> list[dict]:
    """Every dataset in the manifest, with the hash of the file as it is now."""
    out = []
    for d in manifest()["datasets"]:
        actual = sha256_file(EVAL_DIR / d["file"])
        out.append({**d, "sha256_actual": actual, "matches_manifest": actual == d["sha256"]})
    return out


def manifest_problems() -> list[str]:
    """A dataset whose content changed without a new version and hash in the manifest is an error:
    results from the old and new content would otherwise be compared as if they were the same."""
    return [
        f"{d['file']} changed since version {d['version']} was recorded (hash {d['sha256_actual'][:12]}, "
        f"manifest says {d['sha256'][:12]}): give it a new version and hash in evals/datasets.json"
        for d in datasets()
        if not d["matches_manifest"]
    ]


def request_fingerprint() -> str:
    """Hash of everything that shapes a request to Claude: the system prompts, the prompt builders,
    the level guidance, the token limits and effort set in them, and the output schemas. Error
    handling is left out on purpose: it changes what happens to a reply, not what is asked."""
    from app.schemas.ai import CodeReview, FailureExplanation, HintContent
    from app.schemas.interview import InterviewerReply, InterviewEvaluation
    from app.services.ai import anthropic_provider as ap

    parts = [
        ap.SYSTEM_PROMPT,
        ap.INTERVIEWER_SYSTEM_PROMPT,
        ap.EVALUATOR_SYSTEM_PROMPT,
        json.dumps(ap._LEVEL_GUIDANCE, sort_keys=True),
        *(
            inspect.getsource(f)
            for f in (ap._transcript_block, ap._problem_block, ap._analysis_block, ap._numbered)
        ),
        *(
            inspect.getsource(getattr(ap.AnthropicCoach, m))
            for m in ("__init__", "hint", "review", "explain_failure", "interview_turn", "evaluate_interview")
        ),
        *(
            json.dumps(m.model_json_schema(), sort_keys=True)
            for m in (HintContent, CodeReview, FailureExplanation, InterviewerReply, InterviewEvaluation)
        ),
    ]
    return hashlib.sha256("\n\x1e".join(parts).encode()).hexdigest()


def prompt_version_problems() -> list[str]:
    from app.services.ai.anthropic_provider import PROMPT_VERSION

    registry = json.loads(PROMPT_REGISTRY.read_text(encoding="utf-8"))
    recorded = registry["versions"].get(PROMPT_VERSION)
    current = request_fingerprint()
    if recorded is None:
        return [f"PROMPT_VERSION {PROMPT_VERSION!r} is not in evals/prompt_versions.json"]
    if recorded["fingerprint"] != current:
        return [
            f"the coach prompts or request settings changed since {PROMPT_VERSION} was recorded "
            f"(fingerprint {current[:12]}, recorded {recorded['fingerprint'][:12]}): set a new PROMPT_VERSION "
            "in app/services/ai/anthropic_provider.py, add it with this fingerprint to "
            "evals/prompt_versions.json, and re-run the evaluation"
        ]
    return []


def git_state() -> dict:
    def git(*args: str) -> str | None:
        try:
            return subprocess.check_output(
                ["git", *args], cwd=EVAL_DIR, text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = git("status", "--porcelain", "--untracked-files=no")
    # Reports written by earlier runs are outputs, not code or data: they don't make a run dirty.
    changed = (
        None if status is None else [line for line in status.splitlines() if "evals/results/" not in line]
    )
    return {
        "commit": git("rev-parse", "HEAD"),
        "uncommitted_changes": bool(changed) if changed is not None else None,
    }


def run_metadata(*, provider: str, model: str, config: dict, sections: list[str], selection: dict) -> dict:
    from app.careers.grading import RUBRIC_VERSION
    from app.services.ai.anthropic_provider import PROMPT_VERSION

    return {
        "report_schema": REPORT_SCHEMA,
        "run_id": uuid.uuid4().hex,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **git_state(),
        "python": platform.python_version(),
        "provider": provider,
        "model": model,
        "config": config,
        "rubric_version": RUBRIC_VERSION,
        "prompt_version": PROMPT_VERSION,
        "prompt_fingerprint": request_fingerprint(),
        "datasets": [
            {
                k: d[k]
                for k in ("id", "file", "version", "split", "domain", "sha256_actual", "matches_manifest")
            }
            for d in datasets()
        ],
        "sections": sections,
        "selection": selection,
    }
