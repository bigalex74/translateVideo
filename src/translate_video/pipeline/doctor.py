"""Project diagnostics and safe partial rerun helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from translate_video.core.schemas import ArtifactKind, JobStatus, Stage, VideoProject


DEFAULT_STAGE_ORDER = [
    Stage.EXTRACT_AUDIO.value,
    Stage.TRANSCRIBE.value,
    Stage.REGROUP.value,
    Stage.TRANSLATE.value,
    Stage.TIMING_FIT.value,
    Stage.TTS.value,
    Stage.RENDER.value,
    Stage.EXPORT.value,
    Stage.EMBED_SUBTITLES.value,
]

_REQUIRED_ARTIFACTS: dict[str, tuple[ArtifactKind, ...]] = {
    Stage.TRANSCRIBE.value: (ArtifactKind.SOURCE_AUDIO,),
    Stage.TRANSLATE.value: (ArtifactKind.SOURCE_TRANSCRIPT,),
    Stage.TIMING_FIT.value: (ArtifactKind.TRANSLATED_TRANSCRIPT,),
    Stage.TTS.value: (ArtifactKind.TRANSLATED_TRANSCRIPT,),
    Stage.RENDER.value: (ArtifactKind.TRANSLATED_TRANSCRIPT, ArtifactKind.TTS_AUDIO),
    Stage.EMBED_SUBTITLES.value: (ArtifactKind.OUTPUT_VIDEO, ArtifactKind.SUBTITLES),
}

_RECOVERY_STAGE_BY_ARTIFACT: dict[ArtifactKind, str] = {
    ArtifactKind.SOURCE_AUDIO: Stage.EXTRACT_AUDIO.value,
    ArtifactKind.SOURCE_TRANSCRIPT: Stage.TRANSCRIBE.value,
    ArtifactKind.TRANSLATED_TRANSCRIPT: Stage.TRANSLATE.value,
    ArtifactKind.TTS_AUDIO: Stage.TTS.value,
    ArtifactKind.OUTPUT_VIDEO: Stage.RENDER.value,
    ArtifactKind.SUBTITLES: Stage.EXPORT.value,
}


@dataclass(slots=True)
class SafeStagePlan:
    requested_from_stage: str | None
    safe_from_stage: str | None
    changed: bool
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _stage_order(stages: list[Any] | None = None) -> list[str]:
    if not stages:
        return list(DEFAULT_STAGE_ORDER)
    return [stage.stage.value for stage in stages if hasattr(stage, "stage")]


def _artifact_record(project: VideoProject, kind: ArtifactKind):
    for record in reversed(project.artifact_records):
        if record.kind == kind:
            return record
    return None


def _safe_project_path(project: VideoProject, rel_path: str) -> Path:
    candidate = (project.work_dir / rel_path).resolve()
    root = project.work_dir.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("artifact path escapes project directory")
    return candidate


def artifact_exists(project: VideoProject, kind: ArtifactKind) -> bool:
    record = _artifact_record(project, kind)
    if record is None:
        return False
    try:
        return _safe_project_path(project, record.path).exists()
    except ValueError:
        return False


def missing_required_artifacts(project: VideoProject, stage_value: str) -> list[ArtifactKind]:
    return [
        kind for kind in _REQUIRED_ARTIFACTS.get(stage_value, ())
        if not artifact_exists(project, kind)
    ]


def recommend_safe_from_stage(
    project: VideoProject,
    stages: list[Any] | None,
    requested_from_stage: str | None,
) -> SafeStagePlan:
    """Backtrack a requested partial rerun to the earliest missing dependency."""

    if not requested_from_stage:
        return SafeStagePlan(None, None, False, [])

    order = _stage_order(stages)
    if requested_from_stage not in order:
        return SafeStagePlan(
            requested_from_stage,
            requested_from_stage,
            False,
            [f"unknown or inactive stage: {requested_from_stage}"],
        )

    current = requested_from_stage
    warnings: list[str] = []
    visited: set[str] = set()
    while current not in visited:
        visited.add(current)
        missing = missing_required_artifacts(project, current)
        if not missing:
            break

        candidates = [
            _RECOVERY_STAGE_BY_ARTIFACT[kind]
            for kind in missing
            if _RECOVERY_STAGE_BY_ARTIFACT.get(kind) in order
        ]
        if not candidates:
            warnings.append(
                f"{current}: missing {', '.join(kind.value for kind in missing)}, no recovery stage in this pipeline"
            )
            break

        recovery = min(candidates, key=order.index)
        if order.index(recovery) >= order.index(current):
            warnings.append(
                f"{current}: missing {', '.join(kind.value for kind in missing)}"
            )
            break
        warnings.append(
            f"{current} requires missing {', '.join(kind.value for kind in missing)}; using {recovery}"
        )
        current = recovery

    return SafeStagePlan(
        requested_from_stage=requested_from_stage,
        safe_from_stage=current,
        changed=current != requested_from_stage,
        warnings=warnings,
    )


def diagnose_project(project: VideoProject, stages: list[Any] | None = None) -> dict[str, Any]:
    """Return a lightweight, actionable project integrity report."""

    order = _stage_order(stages)
    issues: list[dict[str, Any]] = []

    for record in project.artifact_records:
        try:
            path = _safe_project_path(project, record.path)
            exists = path.exists()
        except ValueError:
            path = project.work_dir / record.path
            exists = False
            issues.append({
                "severity": "error",
                "code": "artifact_path_escape",
                "kind": record.kind.value,
                "path": record.path,
                "message": "Artifact path leaves the project directory.",
            })
        if not exists:
            issues.append({
                "severity": "warning",
                "code": "missing_artifact_file",
                "kind": record.kind.value,
                "path": record.path,
                "message": "Artifact record exists, but the file is missing.",
            })

    latest_by_stage = {run.stage.value: run for run in project.stage_runs}
    for stage_value in order:
        run = latest_by_stage.get(stage_value)
        if run is None:
            continue
        if run.status == JobStatus.FAILED:
            issues.append({
                "severity": "error",
                "code": "stage_failed",
                "stage": stage_value,
                "message": run.error or "Stage failed.",
            })
        elif run.status == JobStatus.RUNNING:
            issues.append({
                "severity": "warning",
                "code": "stage_running",
                "stage": stage_value,
                "message": "Stage is marked running. If no job is active, resume from this stage.",
            })

    requested = _recommended_resume_stage(project, order)
    safe_plan = recommend_safe_from_stage(project, stages, requested)
    actions = _project_actions(project, stages)
    segment_summary = _segment_summary(project)
    return {
        "project_id": project.id,
        "status": project.status.value,
        "ok": not issues,
        "issues": issues,
        "recommended_from_stage": safe_plan.safe_from_stage,
        "requested_from_stage": requested,
        "safe_stage_plan": safe_plan.to_dict(),
        "actions": actions,
        "segment_summary": segment_summary,
        "segment_actions": _segment_actions(segment_summary),
    }


def _recommended_resume_stage(project: VideoProject, order: list[str]) -> str | None:
    latest_by_stage = {run.stage.value: run for run in project.stage_runs}
    for stage_value in order:
        run = latest_by_stage.get(stage_value)
        if run is None:
            return stage_value
        if run.status in {JobStatus.FAILED, JobStatus.RUNNING, JobStatus.PENDING}:
            return stage_value
    return None


def _project_actions(project: VideoProject, stages: list[Any] | None) -> list[dict[str, Any]]:
    has_translated_segments = any(bool((seg.translated_text or "").strip()) for seg in project.segments)
    candidates = [
        ("resume", _recommended_resume_stage(project, _stage_order(stages)), "Continue safely"),
        ("subtitles", Stage.EXPORT.value if has_translated_segments else None, "Rebuild subtitles"),
        ("tts", Stage.TTS.value if has_translated_segments else None, "Rebuild voice audio"),
        ("video", Stage.RENDER.value if has_translated_segments else None, "Rebuild final video"),
    ]
    actions: list[dict[str, Any]] = []
    for action_id, requested, label in candidates:
        plan = recommend_safe_from_stage(project, stages, requested)
        actions.append({
            "id": action_id,
            "label": label,
            "enabled": plan.safe_from_stage is not None,
            "requested_from_stage": requested,
            "from_stage": plan.safe_from_stage,
            "warnings": plan.warnings,
        })
    return actions


def _segment_summary(project: VideoProject) -> dict[str, int]:
    segments = list(project.segments or [])
    translated = [seg for seg in segments if (seg.translated_text or "").strip()]
    qa_flagged = [seg for seg in segments if seg.qa_flags]
    return {
        "segments_total": len(segments),
        "empty_translations": sum(1 for seg in segments if not (seg.translated_text or "").strip()),
        "missing_tts": sum(1 for seg in translated if not seg.tts_path),
        "timing_fit_failed": sum(1 for seg in segments if "timing_fit_failed" in seg.qa_flags),
        "qa_flagged": len(qa_flagged),
        "unreviewed_issues": sum(1 for seg in qa_flagged if not getattr(seg, "reviewed", False)),
    }


def _segment_actions(summary: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {
            "id": "select-empty",
            "label": "Select empty translations",
            "count": summary["empty_translations"],
            "action": "translate",
        },
        {
            "id": "select-missing-tts",
            "label": "Select segments without TTS",
            "count": summary["missing_tts"],
            "action": "tts",
        },
        {
            "id": "select-timing-failed",
            "label": "Select timing issues",
            "count": summary["timing_fit_failed"],
            "action": "mark-reviewed",
        },
        {
            "id": "select-unreviewed-qa",
            "label": "Select unreviewed QA issues",
            "count": summary["unreviewed_issues"],
            "action": "mark-reviewed",
        },
    ]
