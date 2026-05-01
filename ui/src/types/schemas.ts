export type SegmentStatus = "draft" | "transcribed" | "translated" | "tts_ready" | "failed";
export type ProjectStatus = "created" | "running" | "completed" | "failed";
export type JobStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type Stage = "init" | "probe" | "extract_audio" | "transcribe" | "speaker_analysis" | "translate" | "voice_cast" | "tts" | "timing_fit" | "mix" | "render" | "qa" | "export";

export interface PipelineConfig {
    source_language: string;
    target_language: string;
    translation_mode: string;
    translation_style: string;
    adaptation_level: string;
    voice_strategy: string;
    quality_gate: string;
    terminology_domain: string;
    target_audience: string;
    glossary_path?: string;
    do_not_translate: string[];
}

export type PipelineConfigDraft = Partial<PipelineConfig>;

export interface Segment {
    id: string;
    start: number;
    end: number;
    source_text: string;
    translated_text: string;
    speaker_id?: string;
    voice?: string;
    confidence?: number;
    status: SegmentStatus;
    tts_path?: string;
}

export interface StageRun {
    id: string;
    stage: Stage;
    status: JobStatus;
    started_at?: string;
    finished_at?: string;
    inputs: string[];
    outputs: string[];
    error?: string;
    attempt: number;
}

export interface ArtifactRecord {
    kind: string;
    path: string;
    stage: Stage;
    content_type: string;
    created_at: string;
    metadata: Record<string, unknown>;
    checksum?: string;
}

export interface VideoProject {
    project_id: string;
    status: ProjectStatus;
    input_video: string;
    work_dir: string;
    segments: number | Segment[];
    artifacts: Record<string, string>;
    artifact_records?: ArtifactRecord[];
    stage_runs?: StageRun[];
    config?: PipelineConfig;
}
