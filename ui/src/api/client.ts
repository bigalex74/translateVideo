import type {
    ArtifactsResponse,
    PipelineConfig,
    PipelineConfigDraft,
    PreflightReport,
    ProviderBalance,
    ProviderModel,
    Segment,
    VideoProject,
} from "../types/schemas";

// Vite dev-сервер не проксирует API, поэтому в dev используем backend 8002.
// Если UI отдан самим FastAPI (fullstack E2E/production), работаем через origin.
const isViteDevServer = ['5173', '5174'].includes(window.location.port);
const API_BASE = isViteDevServer ? "http://localhost:8002/api/v1" : "/api/v1";

async function readError(res: Response): Promise<string> {
    const text = await res.text();
    try {
        const payload = JSON.parse(text) as { detail?: string };
        return payload.detail || text;
    } catch {
        return text;
    }
}

export async function createProject(input_video: string, project_id?: string, config?: PipelineConfigDraft): Promise<VideoProject> {
    const res = await fetch(`${API_BASE}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_video, project_id, config })
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function uploadProject(file: File, project_id?: string, config?: PipelineConfigDraft): Promise<VideoProject> {
    const formData = new FormData();
    formData.append("file", file);
    if (project_id) formData.append("project_id", project_id);
    if (config) formData.append("config", JSON.stringify(config));

    const res = await fetch(`${API_BASE}/projects/upload`, {
        method: "POST",
        body: formData
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function listProjects(params?: {
    search?: string;
    sort_by?: 'created_at' | 'name' | 'status';
    sort_dir?: 'asc' | 'desc';
    tag?: string;
    page_size?: number;
}): Promise<VideoProject[]> {
    const q = new URLSearchParams();
    if (params?.search)   q.set('search', params.search);
    if (params?.sort_by)  q.set('sort_by', params.sort_by);
    if (params?.sort_dir) q.set('sort_dir', params.sort_dir);
    if (params?.tag)      q.set('tag', params.tag);
    if (params?.page_size) q.set('page_size', String(params.page_size));
    const url = q.toString() ? `${API_BASE}/projects?${q}` : `${API_BASE}/projects`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(await readError(res));
    const data = await res.json() as { projects: VideoProject[] };
    return data.projects;
}

export async function getProjectStatus(project_id: string): Promise<VideoProject> {
    const res = await fetch(`${API_BASE}/projects/${project_id}`);
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function runPipeline(
    project_id: string,
    force: boolean = false,
    provider?: string,
    webhookUrl?: string,
    from_stage?: string | null,
): Promise<{status: string, message: string}> {
    // Читаем сохранённые настройки если не переданы явно
    const effectiveProvider = provider ?? localStorage.getItem('tv_default_provider') ?? 'legacy';
    const effectiveWebhook  = webhookUrl ?? localStorage.getItem('tv_webhook_url') ?? undefined;

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (effectiveWebhook) {
        headers["X-Webhook-Url"] = effectiveWebhook;
    }

    const body: Record<string, unknown> = { force, provider: effectiveProvider };
    if (from_stage) body.from_stage = from_stage;

    const res = await fetch(`${API_BASE}/projects/${project_id}/run`, {
        method: "POST",
        headers,
        body: JSON.stringify(body)
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function getProjectArtifacts(project_id: string): Promise<ArtifactsResponse> {
    const res = await fetch(`${API_BASE}/projects/${project_id}/artifacts`);
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function saveProjectSegments(project_id: string, segments: Segment[]): Promise<VideoProject> {
    const res = await fetch(`${API_BASE}/projects/${project_id}/segments`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ translated: true, segments })
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function patchProjectConfig(
    project_id: string,
    config: Partial<PipelineConfig>,
): Promise<{ ok: boolean; config: PipelineConfig }> {
    const res = await fetch(`${API_BASE}/projects/${project_id}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config }),
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function preflightVideo(input_video: string, provider: string = "fake"): Promise<PreflightReport> {
    const res = await fetch(`${API_BASE}/preflight`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_video, provider })
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export async function fetchProviderModels(provider: string): Promise<ProviderModel[]> {
    const res = await fetch(`${API_BASE}/providers/${encodeURIComponent(provider)}/models`);
    if (!res.ok) throw new Error(await readError(res));
    const data = await res.json() as { models: ProviderModel[] };
    return data.models;
}

export async function fetchProviderBalance(provider: string): Promise<ProviderBalance> {
    const res = await fetch(`${API_BASE}/providers/${encodeURIComponent(provider)}/balance`);
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

export function artifactDownloadUrl(project_id: string, kind: string): string {
    return `${API_BASE}/projects/${encodeURIComponent(project_id)}/artifacts/${encodeURIComponent(kind)}`;
}

/** Запросить отмену запущенного пайплайна. Бросает ошибку если проект не запущен. */
export async function cancelPipeline(project_id: string): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/projects/${project_id}/cancel`, {
        method: 'POST',
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

/**
 * Синтезировать фрагмент текста и вернуть Blob URL для воспроизведения.
 * Используется кнопкой «▶ Прослушать» в редакторе сегментов.
 * Caller отвечает за вызов URL.revokeObjectURL() после использования.
 */
export async function previewTTS(
    project_id: string,
    text: string,
    is_ssml: boolean = false,
): Promise<string> {
    const res = await fetch(`${API_BASE}/projects/${project_id}/tts-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, is_ssml }),
    });
    if (!res.ok) throw new Error(await readError(res));
    const blob = await res.blob();
    return URL.createObjectURL(blob);
}

/** О1: Переименовать проект (задать display_name). */
export async function renameProject(
    project_id: string,
    display_name: string,
): Promise<{ project_id: string; display_name: string; status: string }> {
    const res = await fetch(`${API_BASE}/projects/${project_id}/rename`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name }),
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

/** А6: URL для скачивания субтитров в конкретном формате (srt/vtt/ass/sbv). */
export function subtitleExportUrl(project_id: string, format: 'srt' | 'vtt' | 'ass' | 'sbv'): string {
    return `${API_BASE}/projects/${project_id}/subtitles?format=${format}`;
}

/** А6: URL для скачивания всех субтитров в ZIP (SRT+VTT+ASS+SBV). */
export function subtitleExportZipUrl(project_id: string): string {
    return `${API_BASE}/projects/${project_id}/subtitles/all`;
}

/** R7-И1: Удаление проекта целиком. */
export async function deleteProject(project_id: string): Promise<{ deleted: string; ok: boolean }> {
    const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(project_id)}`, {
        method: 'DELETE',
    });
    if (!res.ok) throw new Error(await readError(res));
    return res.json();
}

/** R7-И4: Safari-совместимое скачивание через fetch+blob (обходит ограничения Safari на <a download>). */
export async function safariSafeDownload(url: string, filename: string): Promise<void> {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = objUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { URL.revokeObjectURL(objUrl); document.body.removeChild(a); }, 1000);
    } catch {
        // Fallback: открыть в новой вкладке (Safari не поддерживает download через Blob)
        window.open(url, '_blank');
    }
}

/** R8-И4: Batch создание проектов (Z5.4 backend). Загружает несколько видео URL одним запросом. */
export interface BatchItem {
    input_video: string;
    project_id?: string;
    config?: Record<string, unknown>;
}
export interface BatchResult {
    project_id: string;
    status: string;
    error?: string;
}
export async function batchCreateProjects(
    items: BatchItem[],
    auto_run = false
): Promise<BatchResult[]> {
    const res = await fetch(`${API_BASE}/projects/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items, auto_run }),
    });
    if (!res.ok) throw new Error(`Batch error: HTTP ${res.status}`);
    return (await res.json()).results ?? [];
}
