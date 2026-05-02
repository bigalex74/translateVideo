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
    const effectiveProvider = provider ?? localStorage.getItem('tv_default_provider') ?? 'legacy';
    const effectiveWebhook  = webhookUrl ?? localStorage.getItem('tv_webhook_url') ?? undefined;

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (effectiveWebhook) {
        headers["X-Webhook-Url"] = effectiveWebhook;
    }

    const res = await fetch(`${API_BASE}/projects/${project_id}/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({ force, provider: effectiveProvider })
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
