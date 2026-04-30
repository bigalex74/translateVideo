import type { VideoProject } from "../types/schemas";

// Если приложение запущено на домене, используем относительный путь, 
// иначе fallback на localhost (для локальной разработки)
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE = isLocalhost ? "http://localhost:8002/api/v1" : "/api/v1";

export async function createProject(input_video: string, project_id?: string, config?: any): Promise<VideoProject> {
    const res = await fetch(`${API_BASE}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_video, project_id, config })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function uploadProject(file: File, project_id?: string, config?: any): Promise<VideoProject> {
    const formData = new FormData();
    formData.append("file", file);
    if (project_id) formData.append("project_id", project_id);
    if (config) formData.append("config", JSON.stringify(config));

    const res = await fetch(`${API_BASE}/projects/upload`, {
        method: "POST",
        body: formData
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function getProjectStatus(project_id: string): Promise<VideoProject> {
    const res = await fetch(`${API_BASE}/projects/${project_id}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function runPipeline(project_id: string, force: boolean = false, provider: string = "fake"): Promise<{status: string, message: string}> {
    const res = await fetch(`${API_BASE}/projects/${project_id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force, provider })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}
