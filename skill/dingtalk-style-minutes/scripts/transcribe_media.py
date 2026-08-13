#!/usr/bin/env python3
"""ASR-only entrypoint shared with clean-talking-video."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def resolve_clean_talking_skill(explicit: Path | None) -> Path:
    """Resolve the required sibling skill without assuming a user's home path."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(explicit.expanduser())
    if os.environ.get("CLEAN_TALKING_VIDEO_SKILL"):
        candidates.append(Path(os.environ["CLEAN_TALKING_VIDEO_SKILL"]).expanduser())
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    agents_home = Path(os.environ.get("AGENTS_HOME", Path.home() / ".agents"))
    candidates.extend([
        codex_home / "skills/clean-talking-video",
        agents_home / "skills/clean-talking-video/clean-talking-video",
        agents_home / "skills/clean-talking-video",
    ])
    for candidate in candidates:
        if (candidate / "scripts/transcribe.py").is_file():
            return candidate
    checked = "\n  - ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "clean-talking-video skill not found. Install it, set "
        "CLEAN_TALKING_VIDEO_SKILL, or pass --clean-talking-skill. Checked:\n  - " + checked
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--speaker-count", type=int)
    parser.add_argument("--no-diarization", action="store_true")
    parser.add_argument("--clean-talking-skill", type=Path)
    args = parser.parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    key = os.environ.get("DASHSCOPE_ASR_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not key:
        raise RuntimeError("DASHSCOPE_API_KEY is required; load workspace .ENV before ASR")
    skill = resolve_clean_talking_skill(args.clean_talking_skill)
    transcriber = skill / "scripts/transcribe.py"
    if not transcriber.is_file():
        raise FileNotFoundError(transcriber)
    cmd = [sys.executable, str(transcriber), "--input", str(args.input), "--output-dir", str(args.output_dir), "--language", args.language]
    if not args.no_diarization:
        cmd += ["--diarization"]
    if args.speaker_count is not None:
        cmd += ["--speaker-count", str(args.speaker_count)]
    if args.prompt:
        cmd += ["--prompt", args.prompt]
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
