import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  createProject,
  Clause,
  getHealth,
  getJob,
  Job,
  ingestRegulation,
  listClauses,
  listProjectFiles,
  listProjectJobs,
  listProjects,
  listRegulations,
  openDownload,
  Project,
  ProjectFile,
  publishVersion,
  retryJob,
  Standard,
  updateClause,
  uploadProjectFile,
} from "./api/client";

type ConnectionState = "checking" | "connected" | "unavailable";

function readableBytes(size: number) {
  if (size < 1024 * 1024) return `${Math.ceil(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function App() {
  const [connection, setConnection] = useState<ConnectionState>("checking");
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [projectName, setProjectName] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [logicalName, setLogicalName] = useState("");
  const [upload, setUpload] = useState<File | null>(null);
  const [purpose, setPurpose] = useState("project_document");
  const [regulations, setRegulations] = useState<Standard[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [query, setQuery] = useState("");
  const [editingClause, setEditingClause] = useState<Clause | null>(null);
  const [editedText, setEditedText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshFiles = useCallback(async (projectId: string, signal?: AbortSignal) => {
    setFiles(await listProjectFiles(projectId, signal));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then(() => setConnection("connected"))
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setConnection("unavailable");
      });
    Promise.all([listProjects(controller.signal), listRegulations(controller.signal)])
      .then(([items, standards]) => {
        setProjects((current) => current.length === 0 ? items : current);
        setRegulations(standards);
        if (items.length > 0) setSelectedProjectId(items[0].id);
        if (standards[0]?.versions[0]) setSelectedVersionId(standards[0].versions[0].id);
      })
      .catch((requestError: unknown) => {
        if (!(requestError instanceof DOMException && requestError.name === "AbortError")) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load projects");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }
    void listClauses(selectedVersionId, query).then(setClauses).catch((requestError: unknown) => {
      setError(requestError instanceof Error ? requestError.message : "Unable to load clauses");
    });
  }, [query, selectedVersionId]);

  useEffect(() => {
    if (!selectedProjectId) return;
    const controller = new AbortController();
    Promise.all([
      listProjectFiles(selectedProjectId, controller.signal),
      listProjectJobs(selectedProjectId, controller.signal),
    ])
      .then(([projectFiles, jobs]) => {
        setFiles(projectFiles);
        setJob(jobs[0] ?? null);
      })
      .catch((requestError: unknown) => {
        if (!(requestError instanceof DOMException && requestError.name === "AbortError")) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load files");
        }
      });
    return () => controller.abort();
  }, [refreshFiles, selectedProjectId]);

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      getJob(job.id, controller.signal)
        .then((updated) => {
          setJob(updated);
          if (updated.status === "succeeded" && updated.project_id) {
            void refreshFiles(updated.project_id);
          }
          if (updated.status === "succeeded" && updated.job_type === "regulation.parse") {
            const versionId = updated.output_data?.standard_version_id;
            if (typeof versionId === "string") {
              setSelectedVersionId(versionId);
              void listClauses(versionId).then(setClauses);
              void listRegulations().then(setRegulations);
            }
          }
        })
        .catch((requestError: unknown) => {
          if (!(requestError instanceof DOMException && requestError.name === "AbortError")) {
            setError(requestError instanceof Error ? requestError.message : "Unable to refresh job");
          }
        });
    }, 1000);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [job, refreshFiles]);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!projectName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createProject(projectName.trim(), jurisdiction.trim());
      setProjects((current) => [created, ...current]);
      setSelectedProjectId(created.id);
      setProjectName("");
      setJurisdiction("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to create project");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !upload) return;
    setBusy(true);
    setError(null);
    try {
      const result = await uploadProjectFile(selectedProjectId, upload, logicalName, purpose);
      setJob(result.job);
      setUpload(null);
      setLogicalName("");
      await refreshFiles(selectedProjectId);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to upload file");
    } finally {
      setBusy(false);
    }
  }

  async function handleIngest(versionId: string) {
    const code = window.prompt("Standard code", "GB 55037-2022");
    if (!code) return;
    const edition = window.prompt("Edition", "2022");
    if (!edition) return;
    setBusy(true);
    setError(null);
    try {
      const result = await ingestRegulation(
        versionId,
        code,
        code === "GB 55037-2022" ? "General Code for Fire Protection of Buildings" : code,
        edition,
        selectedProject?.jurisdiction ?? "China",
      );
      setJob(result.job);
      setSelectedVersionId(result.version.id);
      setRegulations(await listRegulations());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to ingest regulation");
    } finally {
      setBusy(false);
    }
  }

  async function handleClauseSave() {
    if (!editingClause) return;
    setBusy(true);
    try {
      const updated = await updateClause(editingClause.id, editedText, "Architect review");
      setClauses((items) => items.map((item) => item.id === updated.id ? updated : item));
      setEditingClause(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save clause");
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    if (!selectedVersionId) return;
    try {
      await publishVersion(selectedVersionId);
      setRegulations(await listRegulations());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to publish version");
    }
  }

  async function handleRetry() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      setJob(await retryJob(job.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to retry job");
    } finally {
      setBusy(false);
    }
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;

  return (
    <main className="shell">
      <nav className="topbar" aria-label="Primary navigation">
        <a className="brand" href="/" aria-label="Code Compliance home">
          <span className="brand-mark">CC</span>
          <span>Code Compliance</span>
        </a>
        <span className={`connection connection--${connection}`}>
          <span className="connection-dot" aria-hidden="true" />
          API {connection}
        </span>
      </nav>

      <section className="hero hero--compact">
        <p className="eyebrow">M2 · Regulation digitization</p>
        <h1>From source PDF to citable clauses.</h1>
        <p className="hero-copy">
          Reuse an immutable source file, extract text or OCR, review every clause, and publish a
          traceable regulation version for later compliance checks.
        </p>
      </section>

      {error && <div className="alert" role="alert">{error}</div>}

      <section className="workspace" aria-label="M1 project workspace">
        <aside className="panel project-panel">
          <div className="panel-heading">
            <p className="eyebrow">01 · Projects</p>
            <h2>Choose a project</h2>
          </div>
          <form className="stack" onSubmit={handleCreate}>
            <label>
              Project name
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
            </label>
            <label>
              Jurisdiction
              <input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} />
            </label>
            <button disabled={busy || !projectName.trim()} type="submit">Create project</button>
          </form>
          <div className="project-list">
            {projects.map((project) => (
              <button
                className={project.id === selectedProjectId ? "project-item is-selected" : "project-item"}
                key={project.id}
                onClick={() => setSelectedProjectId(project.id)}
                type="button"
              >
                <strong>{project.name}</strong>
                <span>{project.jurisdiction ?? "Jurisdiction not set"}</span>
              </button>
            ))}
            {projects.length === 0 && <p className="empty">Create the first renovation project.</p>}
          </div>
        </aside>

        <section className="panel file-panel">
          <div className="panel-heading">
            <p className="eyebrow">02 · Immutable files</p>
            <h2>{selectedProject?.name ?? "Select a project"}</h2>
          </div>
          <form className="stack upload-form" onSubmit={handleUpload}>
            <label>
              Logical document name
              <input
                disabled={!selectedProject}
                placeholder="Existing floor plan"
                value={logicalName}
                onChange={(event) => setLogicalName(event.target.value)}
              />
            </label>
            <label className="file-picker">
              PDF file · up to 150 MB
              <input
                accept="application/pdf,.pdf"
                disabled={!selectedProject}
                onChange={(event) => setUpload(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <label>
              Document purpose
              <select value={purpose} onChange={(event) => setPurpose(event.target.value)}>
                <option value="project_document">Project document</option>
                <option value="regulation_source">Regulation source</option>
              </select>
            </label>
            <button disabled={busy || !selectedProject || !upload} type="submit">Upload version</button>
          </form>
          <div className="file-list">
            {files.map((item) => (
              <article className="file-card" key={item.id}>
                <div>
                  <strong>{item.logical_name}</strong>
                  <span>{item.versions.length} version{item.versions.length === 1 ? "" : "s"}</span>
                </div>
                {item.versions.map((version) => (
                  <div className="version-actions" key={version.id}>
                    <button
                      className="version-row"
                      onClick={() => void openDownload(version.id)}
                      type="button"
                    >
                      <span>v{version.version_number} · {version.original_filename}</span>
                      <span>{readableBytes(version.size_bytes)}</span>
                    </button>
                    {item.purpose === "regulation_source" && (
                      <button
                        className="secondary-button"
                        disabled={busy}
                        onClick={() => void handleIngest(version.id)}
                        type="button"
                      >Digitize this version</button>
                    )}
                  </div>
                ))}
              </article>
            ))}
            {selectedProject && files.length === 0 && <p className="empty">No files uploaded yet.</p>}
          </div>
        </section>

        <aside className="panel job-panel">
          <div className="panel-heading">
            <p className="eyebrow">03 · Background job</p>
            <h2>Processing trace</h2>
          </div>
          {!job && <p className="empty">Upload a PDF to create a real Celery job.</p>}
          {job && (
            <article className="job-card" aria-live="polite">
              <div className="job-state">
                <span className={`status status--${job.status}`}>{job.status}</span>
                <span>{Math.round(job.progress * 100)}%</span>
              </div>
              <div className="progress"><span style={{ width: `${job.progress * 100}%` }} /></div>
              <dl>
                <div><dt>Type</dt><dd>{job.job_type}</dd></div>
                <div><dt>Attempts</dt><dd>{job.attempts} / {job.max_attempts}</dd></div>
                <div><dt>Request</dt><dd>{job.request_id ?? "—"}</dd></div>
              </dl>
              {job.error_data?.message && <p className="job-error">{job.error_data.message}</p>}
              {job.status === "failed" && job.attempts < job.max_attempts && (
                <button disabled={busy} onClick={() => void handleRetry()} type="button">Retry job</button>
              )}
            </article>
          )}
        </aside>
      </section>

      <section className="regulation-workspace" aria-label="M2 regulation workspace">
        <div className="panel regulation-library">
          <div className="panel-heading">
            <p className="eyebrow">04 · Regulation versions</p>
            <h2>Controlled library</h2>
          </div>
          {regulations.map((standard) => (
            <article className="file-card" key={standard.id}>
              <strong>{standard.code}</strong>
              <span>{standard.title}</span>
              {standard.versions.map((version) => (
                <button
                  className="version-row"
                  key={version.id}
                  onClick={() => setSelectedVersionId(version.id)}
                  type="button"
                >
                  <span>{version.edition}</span><span>{version.lifecycle_status}</span>
                </button>
              ))}
            </article>
          ))}
          {regulations.length === 0 && <p className="empty">No regulation version yet.</p>}
        </div>

        <div className="panel clause-review">
          <div className="panel-heading">
            <p className="eyebrow">05 · Human review gate</p>
            <h2>Search and correct clauses</h2>
          </div>
          <div className="clause-toolbar">
            <input
              aria-label="Search clauses"
              placeholder="Clause number or text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <button disabled={!selectedVersionId} onClick={() => void handlePublish()} type="button">
              Publish reviewed version
            </button>
          </div>
          <div className="clause-list">
            {clauses.map((clause) => (
              <button
                className="clause-row"
                key={clause.id}
                onClick={() => { setEditingClause(clause); setEditedText(clause.original_text); }}
                type="button"
              >
                <strong>{clause.clause_number}</strong>
                <span>p.{clause.page_number} · {clause.lifecycle_status}</span>
                <p>{clause.original_text}</p>
              </button>
            ))}
          </div>
          {editingClause && (
            <div className="clause-editor">
              <strong>Review {editingClause.clause_number}</strong>
              <textarea value={editedText} onChange={(event) => setEditedText(event.target.value)} />
              <button disabled={busy || !editedText.trim()} onClick={() => void handleClauseSave()} type="button">
                Save and mark reviewed
              </button>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

export default App;
