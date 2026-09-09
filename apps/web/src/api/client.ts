export interface HealthResponse {
  status: "ok";
  service: string;
  api_version: "v1";
}

export interface Project {
  id: string;
  name: string;
  code: string | null;
  jurisdiction: string | null;
  design_date: string | null;
  building_type: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface FileVersion {
  id: string;
  project_file_id: string;
  version_number: number;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface ProjectFile {
  id: string;
  project_id: string;
  logical_name: string;
  purpose: string;
  created_at: string;
  versions: FileVersion[];
}

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface Job {
  id: string;
  project_id: string | null;
  file_version_id: string | null;
  job_type: string;
  status: JobStatus;
  progress: number;
  attempts: number;
  max_attempts: number;
  output_data: Record<string, unknown> | null;
  error_data: { code?: string; message?: string } | null;
  request_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadResult {
  project_file: ProjectFile;
  file_version: FileVersion;
  job: Job;
}

export interface StandardVersion {
  id: string;
  standard_id: string;
  edition: string;
  lifecycle_status: string;
  source_file_version_id: string;
  parser_version: string | null;
}

export interface Standard {
  id: string;
  code: string;
  title: string;
  jurisdiction: string;
  versions: StandardVersion[];
}

export interface Clause {
  id: string;
  clause_number: string;
  level: string;
  heading: string | null;
  original_text: string;
  page_number: number;
  confidence: number | null;
  lifecycle_status: string;
}

export interface RegulationIngestResult {
  standard: Standard;
  version: StandardVersion;
  job: Job;
}

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API_BASE_URL + path, init);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(payload?.error?.message ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { signal });
}

export function listProjects(signal?: AbortSignal): Promise<Project[]> {
  return request<Project[]>("/projects", { signal });
}

export function createProject(name: string, jurisdiction: string): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, jurisdiction: jurisdiction || null }),
  });
}

export function listProjectFiles(projectId: string, signal?: AbortSignal): Promise<ProjectFile[]> {
  return request<ProjectFile[]>(`/projects/${projectId}/files`, { signal });
}

export function listProjectJobs(projectId: string, signal?: AbortSignal): Promise<Job[]> {
  return request<Job[]>(`/projects/${projectId}/jobs`, { signal });
}

export function uploadProjectFile(
  projectId: string,
  file: File,
  logicalName: string,
  purpose = "project_document",
): Promise<UploadResult> {
  const form = new FormData();
  form.append("upload", file);
  if (logicalName.trim()) form.append("logical_name", logicalName.trim());
  form.append("purpose", purpose);
  return request<UploadResult>(`/projects/${projectId}/files`, {
    method: "POST",
    body: form,
  });
}

export function listRegulations(signal?: AbortSignal): Promise<Standard[]> {
  return request<Standard[]>("/regulations", { signal });
}

export function ingestRegulation(
  fileVersionId: string,
  code: string,
  title: string,
  edition: string,
  jurisdiction: string,
): Promise<RegulationIngestResult> {
  return request<RegulationIngestResult>("/regulations/ingestions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_version_id: fileVersionId,
      code,
      title,
      edition,
      jurisdiction,
    }),
  });
}

export function listClauses(versionId: string, query = ""): Promise<Clause[]> {
  const suffix = query ? `?query=${encodeURIComponent(query)}` : "";
  return request<Clause[]>(`/regulations/versions/${versionId}/clauses${suffix}`);
}

export function updateClause(
  clauseId: string,
  originalText: string,
  changeReason: string,
): Promise<Clause> {
  return request<Clause>(`/regulations/clauses/${clauseId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ original_text: originalText, change_reason: changeReason }),
  });
}

export function publishVersion(versionId: string): Promise<StandardVersion> {
  return request<StandardVersion>(`/regulations/versions/${versionId}/publish`, {
    method: "POST",
  });
}

export function getJob(jobId: string, signal?: AbortSignal): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`, { signal });
}

export function retryJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}/retry`, { method: "POST" });
}

export async function openDownload(fileVersionId: string): Promise<void> {
  const result = await request<{ url: string }>(`/file-versions/${fileVersionId}/download`);
  window.open(result.url, "_blank", "noopener,noreferrer");
}
