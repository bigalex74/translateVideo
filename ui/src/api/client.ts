import type { VideoProject } from "../types/schemas";

const API_BASE = "http://localhost:8000/api/v1";

export async function createProject(input_video: string, project_id?: string, config?: any): Promise<VideoProject> {
    const res = await fetch(`${API_BASE}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_video, project_id, config })
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
