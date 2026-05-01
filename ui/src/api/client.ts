import type {
    ArtifactsResponse,
    PipelineConfig,
    PipelineConfigDraft,
    PreflightReport,
    Segment,
    VideoProject,
} from "../types/schemas";

// Если приложение запущено на домене, используем относительный путь, 
// иначе fallback на localhost (для локальной разработки)
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE = isLocalhost ? "http://localhost:8002/api/v1" : "/api/v1";

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

export async function listProjects(): Promise<VideoProject[]> {
    const res = await fetch(`${API_BASE}/projects`);
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
): Promise<{status: string, message: string}> {
    // Читаем сохранённые настройки если не переданы явно
    const effectiveProvider = provider ?? localStorage.getItem('tv_default_provider') ?? 'fake';
    const effectiveWebhook  = webhookUrl ?? localStorage.getItem('tv_webhook_url') ?? undefined;

    const body: Record<string, unknown> = { force, provider: effectiveProvider };
    if (effectiveWebhook) body['webhook_url'] = effectiveWebhook;

    const res = await fetch(`${API_BASE}/projects/${project_id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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

export function artifactDownloadUrl(project_id: string, kind: string): string {
    return `${API_BASE}/projects/${encodeURIComponent(project_id)}/artifacts/${encodeURIComponent(kind)}`;
}
