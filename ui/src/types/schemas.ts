export type SegmentStatus = "draft" | "transcribed" | "translated" | "tts_ready" | "failed";
export type ProjectStatus = "created" | "running" | "completed" | "failed";
export type JobStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type Stage = "init" | "probe" | "extract_audio" | "transcribe" | "regroup" | "translate" | "voice_cast" | "tts" | "timing_fit" | "mix" | "render" | "qa" | "export";

export interface PipelineConfig {
    source_language: string;
    target_language: string;
    translation_mode: string;
    translation_quality: string;
    translation_style: string;
    adaptation_level: string;
    voice_strategy: string;
    quality_gate: string;
    terminology_domain: string;
    target_audience: string;
    profanity_policy: string;
    units_policy: string;
    preserve_names: boolean;
    preserve_brand_names: boolean;
    original_audio_volume: number;
    background_ducking: boolean;
    subtitle_formats: string[];
    subtitle_embed_mode?: string;  // 'none' | 'soft' | 'burn'
    glossary_path?: string;
    timing_policy: string;
    target_chars_per_second: number;
    timing_fit_max_rewrites: number;
    use_cloud_timing_rewriter: boolean;
    rewrite_provider_order: string[];
    use_cloud_translation: boolean;
    translation_provider_order: string[];
    translation_provider_timeout: number;
    translation_allow_paid_fallback: boolean;
    professional_translation_provider: string;
    professional_translation_model: string;
    professional_rewrite_provider: string;
    professional_rewrite_model: string;
    professional_tts_provider: string;
    professional_tts_model: string;
    professional_tts_voice: string;
    professional_tts_voice_2: string;
    professional_tts_role: string;
    professional_tts_role_2: string;
    professional_tts_speed: number;
    professional_tts_speed_2: number;
    professional_tts_pitch: number;
    professional_tts_pitch_2: number;
    professional_tts_emotion: number;
    el_stability: number;
    el_similarity_boost: number;
    el_style: number;
    el_speed: number;
    allow_tts_rate_adaptation: boolean;
    allow_render_audio_speedup: boolean;
    allow_timeline_shift: boolean;
    max_timeline_shift: number;
    tts_base_rate: number;
    tts_max_rate: number;
    tts_rate_slack: number;
    render_max_speed: number;
    render_gap: number;
    allow_render_audio_trim: boolean;
    regroup_max_slot: number;
    do_not_translate: string[];
    dev_mode: boolean;
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
    tts_text?: string;
    qa_flags?: string[];
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
    progress_current?: number | null;
    progress_total?: number | null;
    progress_message?: string | null;
    metadata?: Record<string, unknown>;
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
    /** Прогресс выполнения 0–100 */
    progress_percent?: number | null;
    /** ETA до завершения в секундах */
    eta_seconds?: number | null;
    /** ISO-дата начала пайплайна */
    started_at?: string | null;
    /** Сообщение об ошибке (для failed статуса) */
    error?: string | null;
}

export interface ProjectListResponse {
    projects: VideoProject[];
}

export interface ArtifactsResponse {
    project_id: string;
    work_dir: string;
    artifacts: ArtifactRecord[];
}

export interface PreflightCheck {
    name: string;
    ok: boolean;
    message: string;
    details: Record<string, string>;
}

export interface CostEstimate {
    translation_usd: number;
    tts_usd: number;
    total_usd: number;
    currency: string;
    note: string;
}

export interface PreflightReport {
    input_video: string;
    provider: string;
    ok: boolean;
    duration_seconds?: number | null;
    /** Оценка стоимости обработки */
    cost_estimate?: CostEstimate | null;
    /** ETA всего пайплайна в секундах */
    duration_estimate_seconds?: number | null;
    checks: PreflightCheck[];
}

export interface ProviderModel {
    id: string;
    name: string;
}

export interface ProviderBalance {
    provider: string;
    configured: boolean;
    balance?: number | null;
    currency?: string | null;
    used?: number | null;
    source?: string | null;
    message?: string | null;
}
