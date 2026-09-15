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

export interface RuleTemplate {
  key: string;
  title: string;
  severity: string;
  inputs: Record<string, unknown>[];
  applicability: Record<string, unknown>;
  expression: Record<string, unknown>;
}

export interface RulePack {
  id: string;
  standard_version_id: string;
  name: string;
  semantic_version: string;
  lifecycle_status: string;
  content_hash: string;
  authority_level: "national" | "local" | "enterprise" | "project";
}

export interface Rule {
  id: string;
  rule_pack_id: string;
  source_clause_id: string;
  code: string;
  title: string;
  severity: string;
  lifecycle_status: string;
}

export interface ProjectFact {
  id: string;
  key: string;
  value: unknown;
  unit: string | null;
  supersedes_id: string | null;
}

export interface FactEvidence {
  id: string;
  file_version_id: string;
  kind: string;
  location: Record<string, unknown>;
  excerpt: string | null;
}

export interface FactCandidate extends ProjectFact {
  project_id: string;
  scope_data: Record<string, unknown>;
  source: string;
  verification_status: string;
  confidence: number | null;
  extractor_version: string | null;
  evidence: FactEvidence[];
}

export interface CheckResult {
  id: string;
  status: string;
  severity: string;
  message: string;
  trace: { clause?: { number?: string; original_text?: string } };
  workflow_status: string;
  assignee_id: string | null;
  reviewer_notes: string | null;
}

export interface CheckRun {
  id: string;
  review_package_id: string;
  status: string;
  input_hash: string;
  run_mode: "full" | "incremental";
  baseline_run_id: string | null;
  changed_fact_keys: string[];
  affected_rule_ids: string[];
  conflict_resolution_snapshot: Record<string, unknown>;
  results: CheckResult[];
}

export interface ChangeImpact {
  baseline_run_id: string;
  changed_fact_keys: string[];
  affected_rule_ids: string[];
  unaffected_rule_ids: string[];
}

export interface CheckComparison {
  baseline_run_id: string;
  run_id: string;
  summary: Record<string, number>;
  items: {
    rule_code: string;
    title: string;
    change: string;
    before_status: string | null;
    after_status: string | null;
  }[];
}

export interface StandardRecommendation {
  standard_version_id: string;
  standard_code: string;
  edition: string;
  recommended: boolean;
  reasons: string[];
  warnings: string[];
}

export interface StandardVersionComparison {
  from_version_id: string;
  to_version_id: string;
  summary: Record<string, number>;
  differences: {
    clause_number: string;
    change: "added" | "removed" | "modified" | "unchanged";
    before_text: string | null;
    after_text: string | null;
  }[];
}

export interface RuleConflict {
  id: string;
  fact_key: string;
  rule_ids: string[];
  rule_codes: string[];
  authority_levels: string[];
  reason: string;
  resolution: Record<string, unknown> | null;
}

export interface DrawingPage {
  id: string;
  file_version_id: string;
  page_number: number;
  width: number;
  height: number;
  extraction_method: string;
  average_confidence: number | null;
  image_url: string | null;
}

export interface WorkbenchEvidence {
  id: string;
  kind: string;
  file_version_id: string | null;
  location: Record<string, unknown>;
  excerpt: string | null;
  image_url: string | null;
}

export interface WorkbenchFinding {
  result_id: string;
  rule_id: string;
  status: string;
  severity: string;
  message: string;
  workflow_status: string;
  assignee_id: string | null;
  reviewer_notes: string | null;
  trace: { clause?: { number?: string; original_text?: string; page_number?: number } };
  project_evidence: WorkbenchEvidence[];
  regulation_evidence: WorkbenchEvidence[];
}

export interface Workbench {
  run_id: string;
  findings: WorkbenchFinding[];
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

export function compareStandardVersions(
  fromVersionId: string,
  toVersionId: string,
): Promise<StandardVersionComparison> {
  return request<StandardVersionComparison>(
    `/regulations/versions/${fromVersionId}/compare/${toVersionId}`,
  );
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

export function listRuleTemplates(): Promise<RuleTemplate[]> {
  return request<RuleTemplate[]>("/rule-templates");
}

export function listRulePacks(): Promise<RulePack[]> {
  return request<RulePack[]>("/rule-packs");
}

export function createRulePack(standardVersionId: string): Promise<RulePack> {
  return request<RulePack>("/rule-packs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      standard_version_id: standardVersionId,
      name: "Pilot fire compliance rules",
      semantic_version: "1.0.0",
    }),
  });
}

export function listRules(packId: string): Promise<Rule[]> {
  return request<Rule[]>(`/rule-packs/${packId}/rules`);
}

export function createRuleFromTemplate(
  packId: string,
  clauseId: string,
  template: RuleTemplate,
): Promise<Rule> {
  return request<Rule>(`/rule-packs/${packId}/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_clause_id: clauseId,
      code: template.key.toUpperCase().replaceAll(".", "-"),
      title: template.title,
      severity: template.severity,
      applicability: template.applicability,
      inputs: template.inputs,
      expression: template.expression,
      missing_data_status: "insufficient_information",
    }),
  });
}

export function reviewRule(ruleId: string): Promise<Rule> {
  return request<Rule>(`/rules/${ruleId}/review`, { method: "POST" });
}

export function publishRulePack(packId: string): Promise<RulePack> {
  return request<RulePack>(`/rule-packs/${packId}/publish`, { method: "POST" });
}

export function listFacts(projectId: string): Promise<ProjectFact[]> {
  return request<ProjectFact[]>(`/projects/${projectId}/facts`);
}

export function startProjectExtraction(
  projectId: string,
  fileVersionId: string,
): Promise<{ document_kind: string; job: Job }> {
  return request<{ document_kind: string; job: Job }>(`/projects/${projectId}/extractions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_version_id: fileVersionId }),
  });
}

export function startDrawingExtraction(
  projectId: string,
  fileVersionId: string,
): Promise<{ job: Job }> {
  return request<{ job: Job }>(`/projects/${projectId}/drawing-extractions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_version_id: fileVersionId }),
  });
}

export function listDrawingPages(projectId: string, fileVersionId: string): Promise<DrawingPage[]> {
  return request<DrawingPage[]>(`/projects/${projectId}/drawings/${fileVersionId}/pages`);
}

export function createDrawingPath(
  projectId: string,
  fileVersionId: string,
  pageNumber: number,
  points: { x: number; y: number }[],
  pixelsPerMeter: number,
): Promise<{ candidate: FactCandidate }> {
  return request<{ candidate: FactCandidate }>(`/projects/${projectId}/drawing-annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_version_id: fileVersionId,
      page_number: pageNumber,
      annotation_kind: "path",
      fact_key: "egress.travel_distance_m",
      label: "Architect-measured evacuation path",
      points,
      pixels_per_meter: pixelsPerMeter,
    }),
  });
}

export function createDrawingAnnotation(
  projectId: string,
  payload: {
    file_version_id: string;
    page_number: number;
    annotation_kind: "object" | "dimension" | "scale";
    fact_key: string;
    value: unknown;
    unit: string | null;
    label: string;
    bbox: Record<string, number> | null;
    corrects_fact_id: string | null;
  },
): Promise<{ candidate: FactCandidate }> {
  return request<{ candidate: FactCandidate }>(`/projects/${projectId}/drawing-annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listFactCandidates(projectId: string): Promise<FactCandidate[]> {
  return request<FactCandidate[]>(`/projects/${projectId}/fact-candidates`);
}

export function decideFactCandidate(
  factId: string,
  decision: "verify" | "reject",
): Promise<FactCandidate> {
  return request<FactCandidate>(`/fact-candidates/${factId}/${decision}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: `Architect ${decision}ed the extracted candidate` }),
  });
}

export function createManualFact(
  projectId: string,
  key: string,
  value: unknown,
  unit: string | null,
): Promise<ProjectFact> {
  return request<ProjectFact>(`/projects/${projectId}/facts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, value, unit, justification: "Architect-entered project fact" }),
  });
}

export function createCheckRun(projectId: string, packIds: string[]): Promise<{ run: CheckRun; job: Job }> {
  return request<{ run: CheckRun; job: Job }>("/check-runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId, rule_pack_ids: packIds, name: "M6 review package" }),
  });
}

export function createIncrementalCheckRun(
  baselineRunId: string,
): Promise<{ run: CheckRun; job: Job; impact: ChangeImpact }> {
  return request<{ run: CheckRun; job: Job; impact: ChangeImpact }>("/check-runs/incremental", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ baseline_run_id: baselineRunId }),
  });
}

export function getCheckComparison(runId: string, baselineRunId: string): Promise<CheckComparison> {
  return request<CheckComparison>(`/check-runs/${runId}/compare/${baselineRunId}`);
}

export function listStandardRecommendations(projectId: string): Promise<StandardRecommendation[]> {
  return request<StandardRecommendation[]>(`/projects/${projectId}/standard-version-recommendations`);
}

export function listRuleConflicts(packageId: string): Promise<RuleConflict[]> {
  return request<RuleConflict[]>(`/review-packages/${packageId}/conflicts`);
}

export function resolveRuleConflict(
  packageId: string,
  conflictId: string,
  selectedRuleId: string,
  note: string,
): Promise<RuleConflict> {
  return request<RuleConflict>(
    `/review-packages/${packageId}/conflicts/${encodeURIComponent(conflictId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_rule_id: selectedRuleId, note }),
    },
  );
}

export function getCheckRun(runId: string): Promise<CheckRun> {
  return request<CheckRun>(`/check-runs/${runId}`);
}

export function getWorkbench(runId: string): Promise<Workbench> {
  return request<Workbench>(`/check-runs/${runId}/workbench`);
}

export function updateFinding(
  resultId: string,
  workflowStatus: string,
  reviewerNotes: string,
): Promise<CheckResult> {
  return request<CheckResult>(`/check-results/${resultId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workflow_status: workflowStatus, reviewer_notes: reviewerNotes }),
  });
}

export function openReport(runId: string, format: "pdf" | "xlsx"): void {
  window.open(`${API_BASE_URL}/check-runs/${runId}/reports/${format}`, "_blank", "noopener,noreferrer");
}

export function openComparisonReport(runId: string, baselineRunId: string): void {
  window.open(
    `${API_BASE_URL}/check-runs/${runId}/comparison-report/${baselineRunId}`,
    "_blank",
    "noopener,noreferrer",
  );
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
