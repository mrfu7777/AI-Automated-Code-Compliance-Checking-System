import { FormEvent, MouseEvent as ReactMouseEvent, useCallback, useEffect, useState } from "react";

import {
  createProject,
  createDemoScenario,
  createCheckRun,
  createIncrementalCheckRun,
  createDrawingPath,
  createDrawingAnnotation,
  createManualFact,
  createPilotFeedback,
  createRuleFromTemplate,
  createRulePack,
  compareStandardVersions,
  Clause,
  decideFactCandidate,
  FactCandidate,
  getHealth,
  getRelease,
  getJob,
  getCheckRun,
  getCheckComparison,
  getWorkbench,
  getMissingInformation,
  Job,
  ingestRegulation,
  listClauses,
  listProjectFiles,
  listProjectJobs,
  listProjects,
  listRegulations,
  listFacts,
  listFactCandidates,
  listDrawingPages,
  listRulePacks,
  listRuleConflicts,
  listStandardRecommendations,
  listRules,
  listRuleTemplates,
  openDownload,
  openComparisonReport,
  openReport,
  Project,
  ProjectFile,
  publishVersion,
  publishRulePack,
  retryJob,
  resolveRuleConflict,
  Standard,
  startProjectExtraction,
  startDrawingExtraction,
  ProjectFact,
  Rule,
  RulePack,
  RuleTemplate,
  CheckRun,
  CheckComparison,
  RuleConflict,
  StandardRecommendation,
  StandardVersionComparison,
  reviewRule,
  updateClause,
  updateFinding,
  uploadProjectFile,
  DrawingPage,
  DemoScenario,
  ReleaseManifest,
  Workbench,
  MissingInformation,
  setApiKey,
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
  const [compareFromVersionId, setCompareFromVersionId] = useState("");
  const [compareToVersionId, setCompareToVersionId] = useState("");
  const [versionComparison, setVersionComparison] = useState<StandardVersionComparison | null>(null);
  const [clauses, setClauses] = useState<Clause[]>([]);
  const [query, setQuery] = useState("");
  const [editingClause, setEditingClause] = useState<Clause | null>(null);
  const [editedText, setEditedText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rulePacks, setRulePacks] = useState<RulePack[]>([]);
  const [selectedPackId, setSelectedPackId] = useState<string | null>(null);
  const [reviewPackIds, setReviewPackIds] = useState<string[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [templates, setTemplates] = useState<RuleTemplate[]>([]);
  const [facts, setFacts] = useState<ProjectFact[]>([]);
  const [factCandidates, setFactCandidates] = useState<FactCandidate[]>([]);
  const [factKey, setFactKey] = useState("egress.door_clear_width_m");
  const [factValue, setFactValue] = useState("1.1");
  const [factUnit, setFactUnit] = useState("m");
  const [checkRun, setCheckRun] = useState<CheckRun | null>(null);
  const [baselineRunId, setBaselineRunId] = useState<string | null>(null);
  const [comparison, setComparison] = useState<CheckComparison | null>(null);
  const [recommendations, setRecommendations] = useState<StandardRecommendation[]>([]);
  const [conflicts, setConflicts] = useState<RuleConflict[]>([]);
  const [selectedClauseId, setSelectedClauseId] = useState<string>("");
  const [drawingVersionId, setDrawingVersionId] = useState<string | null>(null);
  const [drawingPages, setDrawingPages] = useState<DrawingPage[]>([]);
  const [workbench, setWorkbench] = useState<Workbench | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [pathCoordinates, setPathCoordinates] = useState("20,20;220,20;220,160");
  const [pixelsPerMeter, setPixelsPerMeter] = useState("20");
  const [boxStart, setBoxStart] = useState<{ x: number; y: number } | null>(null);
  const [selectedBox, setSelectedBox] = useState<Record<string, number> | null>(null);
  const [annotationKind, setAnnotationKind] = useState<"object" | "dimension" | "scale">("dimension");
  const [annotationKey, setAnnotationKey] = useState("egress.door_clear_width_m");
  const [annotationValue, setAnnotationValue] = useState("0.9");
  const [annotationUnit, setAnnotationUnit] = useState("m");
  const [correctionTargetId, setCorrectionTargetId] = useState("");
  const [missingInformation, setMissingInformation] = useState<MissingInformation | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [feedbackCategory, setFeedbackCategory] = useState("value");
  const [feedbackSeverity, setFeedbackSeverity] = useState("low");
  const [feedbackSummary, setFeedbackSummary] = useState("");
  const [feedbackDetails, setFeedbackDetails] = useState("");
  const [feedbackSaved, setFeedbackSaved] = useState(false);
  const [release, setRelease] = useState<ReleaseManifest | null>(null);
  const [demoScenario, setDemoScenario] = useState<DemoScenario | null>(null);

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
    void getRelease(controller.signal).then(setRelease).catch(() => undefined);
    Promise.all([
      listProjects(controller.signal),
      listRegulations(controller.signal),
      listRulePacks(),
      listRuleTemplates(),
    ])
      .then(([items, standards, packs, availableTemplates]) => {
        setProjects((current) => current.length === 0 ? items : current);
        setRegulations(standards);
        if (items.length > 0) setSelectedProjectId(items[0].id);
        if (standards[0]?.versions[0]) setSelectedVersionId(standards[0].versions[0].id);
        setRulePacks(packs);
        setSelectedPackId(packs[0]?.id ?? null);
        setReviewPackIds(packs[0]?.id ? [packs[0].id] : []);
        setTemplates(availableTemplates);
      })
      .catch((requestError: unknown) => {
        if (!(requestError instanceof DOMException && requestError.name === "AbortError")) {
          setError(requestError instanceof Error ? requestError.message : "Unable to load projects");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedPackId) return;
    void listRules(selectedPackId).then(setRules).catch((requestError: unknown) => {
      setError(requestError instanceof Error ? requestError.message : "Unable to load rules");
    });
  }, [selectedPackId]);

  useEffect(() => {
    if (!selectedProjectId) return;
    void Promise.all([
      listFacts(selectedProjectId),
      listFactCandidates(selectedProjectId),
      listStandardRecommendations(selectedProjectId),
    ])
      .then(([verifiedFacts, candidates, suggestedStandards]) => {
        setFacts(verifiedFacts);
        setFactCandidates(candidates);
        setRecommendations(suggestedStandards);
      })
      .catch((requestError: unknown) => {
        setError(requestError instanceof Error ? requestError.message : "Unable to load facts");
      });
  }, [selectedProjectId]);

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
          if (updated.status === "succeeded" && updated.job_type === "check.run") {
            const runId = updated.output_data?.check_run_id;
            if (typeof runId === "string") {
              void getCheckRun(runId).then((completedRun) => {
                setCheckRun(completedRun);
                void listRuleConflicts(completedRun.review_package_id).then(setConflicts);
                if (completedRun.baseline_run_id) {
                  void getCheckComparison(runId, completedRun.baseline_run_id).then(setComparison);
                }
              });
              void getWorkbench(runId).then((value) => {
                setWorkbench(value);
                setSelectedFindingId(value.findings[0]?.result_id ?? null);
              });
              void getMissingInformation(runId).then(setMissingInformation);
            }
          }
          if (updated.status === "succeeded" && updated.job_type === "project.extract") {
            if (updated.project_id) {
              void listFactCandidates(updated.project_id).then(setFactCandidates);
            }
          }
          if (updated.status === "succeeded" && updated.job_type === "drawing.extract") {
            if (updated.project_id && updated.file_version_id) {
              setDrawingVersionId(updated.file_version_id);
              void Promise.all([
                listDrawingPages(updated.project_id, updated.file_version_id),
                listFactCandidates(updated.project_id),
              ]).then(([pages, candidates]) => {
                setDrawingPages(pages);
                setFactCandidates(candidates);
              });
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

  async function handleExtract(versionId: string) {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await startProjectExtraction(selectedProjectId, versionId);
      setJob(result.job);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to extract facts");
    } finally {
      setBusy(false);
    }
  }

  async function handleDrawingExtract(versionId: string) {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await startDrawingExtraction(selectedProjectId, versionId);
      setDrawingVersionId(versionId);
      setJob(result.job);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to extract drawing");
    } finally {
      setBusy(false);
    }
  }

  async function handlePathMeasurement(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !drawingVersionId || !drawingPages[0]) return;
    const points = pathCoordinates.split(";").map((pair) => {
      const [x, y] = pair.split(",").map(Number);
      return { x, y };
    });
    const calibration = Number(pixelsPerMeter);
    if (points.some((point) => !Number.isFinite(point.x) || !Number.isFinite(point.y)) || calibration <= 0) {
      setError("Use x,y coordinate pairs and a positive pixels-per-metre calibration.");
      return;
    }
    try {
      await createDrawingPath(
        selectedProjectId,
        drawingVersionId,
        drawingPages[0].page_number,
        points,
        calibration,
      );
      setFactCandidates(await listFactCandidates(selectedProjectId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save path");
    }
  }

  function drawingPoint(event: ReactMouseEvent<HTMLDivElement>) {
    const page = drawingPages[0];
    const bounds = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - bounds.left) / bounds.width) * page.width,
      y: page.height - ((event.clientY - bounds.top) / bounds.height) * page.height,
    };
  }

  function handleBoxStart(event: ReactMouseEvent<HTMLDivElement>) {
    if (!drawingPages[0]) return;
    setBoxStart(drawingPoint(event));
  }

  function handleBoxEnd(event: ReactMouseEvent<HTMLDivElement>) {
    if (!boxStart || !drawingPages[0]) return;
    const end = drawingPoint(event);
    setSelectedBox({
      x0: Math.min(boxStart.x, end.x),
      y0: Math.min(boxStart.y, end.y),
      x1: Math.max(boxStart.x, end.x),
      y1: Math.max(boxStart.y, end.y),
    });
    setBoxStart(null);
  }

  async function handleBoxAnnotation(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !drawingVersionId || !drawingPages[0]) return;
    const numeric = Number(annotationValue);
    const value = Number.isNaN(numeric) ? annotationValue : numeric;
    try {
      await createDrawingAnnotation(selectedProjectId, {
        file_version_id: drawingVersionId,
        page_number: drawingPages[0].page_number,
        annotation_kind: annotationKind,
        fact_key: annotationKey,
        value,
        unit: annotationUnit || null,
        label: "Architect-corrected drawing annotation",
        bbox: selectedBox,
        corrects_fact_id: correctionTargetId || null,
      });
      setFactCandidates(await listFactCandidates(selectedProjectId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save annotation");
    }
  }

  async function handleFindingStatus(resultId: string, workflowStatus: string) {
    if (!workbench) return;
    try {
      const updated = await updateFinding(resultId, workflowStatus, "Architect workbench update");
      setWorkbench({
        ...workbench,
        findings: workbench.findings.map((item) => item.result_id === resultId ? {
          ...item,
          workflow_status: updated.workflow_status,
          reviewer_notes: updated.reviewer_notes,
        } : item),
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to update finding");
    }
  }

  async function handleCandidateDecision(factId: string, decision: "verify" | "reject") {
    if (!selectedProjectId) return;
    setBusy(true);
    setError(null);
    try {
      await decideFactCandidate(factId, decision);
      const [verifiedFacts, candidates] = await Promise.all([
        listFacts(selectedProjectId),
        listFactCandidates(selectedProjectId),
      ]);
      setFacts(verifiedFacts);
      setFactCandidates(candidates);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to review candidate");
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

  async function handleCreatePack() {
    if (!selectedVersionId) return;
    try {
      const created = await createRulePack(selectedVersionId);
      setRulePacks((items) => [created, ...items]);
      setSelectedPackId(created.id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to create rule pack");
    }
  }

  async function handleAddRule(template: RuleTemplate) {
    const clauseId = selectedClauseId || clauses.find((item) => item.lifecycle_status === "published")?.id;
    if (!selectedPackId || !clauseId) return;
    try {
      const created = await createRuleFromTemplate(selectedPackId, clauseId, template);
      setRules((items) => [...items, created]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to create rule");
    }
  }

  async function handleReviewRule(ruleId: string) {
    try {
      const reviewed = await reviewRule(ruleId);
      setRules((items) => items.map((item) => item.id === ruleId ? reviewed : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to review rule");
    }
  }

  async function handlePublishPack() {
    if (!selectedPackId) return;
    try {
      const published = await publishRulePack(selectedPackId);
      setRulePacks((items) => items.map((item) => item.id === published.id ? published : item));
      setRules(await listRules(selectedPackId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to publish rule pack");
    }
  }

  async function handleFact(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !factKey.trim()) return;
    const numeric = Number(factValue);
    const value = Number.isNaN(numeric) ? factValue : numeric;
    try {
      const created = await createManualFact(
        selectedProjectId,
        factKey.trim(),
        value,
        factUnit.trim() || null,
      );
      setFacts(await listFacts(selectedProjectId));
      setFactValue("");
      if (created.supersedes_id) setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save fact");
    }
  }

  async function handleRunCheck() {
    if (!selectedProjectId || reviewPackIds.length === 0) return;
    try {
      const created = await createCheckRun(selectedProjectId, reviewPackIds);
      setCheckRun(created.run);
      setBaselineRunId(created.run.id);
      setComparison(null);
      setConflicts([]);
      setWorkbench(null);
      setMissingInformation(null);
      setJob(created.job);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to run check");
    }
  }

  async function handleIncrementalCheck() {
    if (!baselineRunId) return;
    try {
      const created = await createIncrementalCheckRun(baselineRunId);
      setCheckRun(created.run);
      setComparison(null);
      setWorkbench(null);
      setMissingInformation(null);
      setJob(created.job);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to run incremental check");
    }
  }

  async function handleVersionComparison() {
    if (!compareFromVersionId || !compareToVersionId) return;
    try {
      setVersionComparison(await compareStandardVersions(compareFromVersionId, compareToVersionId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to compare editions");
    }
  }

  async function handleConflictResolution(conflict: RuleConflict, ruleId: string) {
    if (!checkRun) return;
    const note = window.prompt("Reason for selecting this rule", "Architect applicability decision");
    if (!note) return;
    try {
      const resolved = await resolveRuleConflict(
        checkRun.review_package_id,
        conflict.id,
        ruleId,
        note,
      );
      setConflicts((current) => current.map((item) => item.id === resolved.id ? resolved : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to resolve conflict");
    }
  }

  function handleApiKey(event: FormEvent) {
    event.preventDefault();
    setApiKey(apiKeyInput);
    window.location.reload();
  }

  async function handlePilotFeedback(event: FormEvent) {
    event.preventDefault();
    if (!selectedProjectId || !feedbackSummary.trim() || !feedbackDetails.trim()) return;
    try {
      await createPilotFeedback(selectedProjectId, {
        category: feedbackCategory,
        severity: feedbackSeverity,
        summary: feedbackSummary.trim(),
        details: feedbackDetails.trim(),
        time_saved_minutes: null,
      });
      setFeedbackSummary("");
      setFeedbackDetails("");
      setFeedbackSaved(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to save feedback");
    }
  }

  async function handleLoadDemo() {
    setBusy(true);
    setError(null);
    try {
      const scenario = await createDemoScenario();
      const [availableProjects, availablePacks] = await Promise.all([
        listProjects(),
        listRulePacks(),
      ]);
      setDemoScenario(scenario);
      setProjects(availableProjects);
      setRulePacks(availablePacks);
      setSelectedProjectId(scenario.project_id);
      setSelectedPackId(scenario.rule_pack_id);
      setReviewPackIds([scenario.rule_pack_id]);
      setFacts(await listFacts(scenario.project_id));
      setFiles(await listProjectFiles(scenario.project_id));
      setCheckRun(null);
      setWorkbench(null);
      setMissingInformation(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load demo");
    } finally {
      setBusy(false);
    }
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const selectedFinding = workbench?.findings.find(
    (finding) => finding.result_id === selectedFindingId,
  ) ?? workbench?.findings[0] ?? null;

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
        {release && <span className="release-badge">V{release.app_version}</span>}
      </nav>

      <section className="hero hero--compact">
        <p className="eyebrow">V1.0 · Evidence-backed fire review demonstration</p>
        <h1>Start with a complete scenario, then inspect every conclusion.</h1>
        <p className="hero-copy">
          Load a clearly labelled synthetic project into the real M1–M7 data model, run the existing
          deterministic review job, and trace findings back to both drawing and rule evidence.
        </p>
        {release?.demo_mode_enabled && (
          <button disabled={busy} onClick={() => void handleLoadDemo()} type="button">
            {busy ? "Preparing demo…" : "Load guided V1 demo"}
          </button>
        )}
        {demoScenario && (
          <div className="demo-guide" aria-label="Guided demo">
            <strong>{demoScenario.project_name}</strong>
            <span>{demoScenario.rule_pack_name}</span>
            <ol>
              {demoScenario.next_steps.map((step) => <li key={step}>{step}</li>)}
            </ol>
          </div>
        )}
        <form className="api-key-form" onSubmit={handleApiKey}>
          <label>
            Pilot API key
            <input
              aria-label="Pilot API key"
              autoComplete="off"
              type="password"
              value={apiKeyInput}
              onChange={(event) => setApiKeyInput(event.target.value)}
            />
          </label>
          <button type="submit">Use key for this browser session</button>
        </form>
      </section>

      <section className="regulation-workspace" aria-label="M3 compliance workspace">
        <div className="panel regulation-library">
          <div className="panel-heading">
            <p className="eyebrow">06 · Reviewed rule packs</p>
            <h2>Author and publish</h2>
          </div>
          <button disabled={!selectedVersionId} onClick={() => void handleCreatePack()} type="button">
            Create pack from selected standard
          </button>
          <select
            aria-label="Rule pack"
            value={selectedPackId ?? ""}
            onChange={(event) => setSelectedPackId(event.target.value || null)}
          >
            <option value="">Select a rule pack</option>
            {rulePacks.map((pack) => (
              <option key={pack.id} value={pack.id}>{pack.name} {pack.semantic_version} · {pack.lifecycle_status}</option>
            ))}
          </select>
          <select
            aria-label="Source clause"
            value={selectedClauseId || clauses.find((item) => item.lifecycle_status === "published")?.id || ""}
            onChange={(event) => setSelectedClauseId(event.target.value)}
          >
            <option value="">Select a published source clause</option>
            {clauses.filter((clause) => clause.lifecycle_status === "published").map((clause) => (
              <option key={clause.id} value={clause.id}>{clause.clause_number} · p.{clause.page_number}</option>
            ))}
          </select>
          <p className="empty">Templates are authoring aids. Bind and verify every threshold against the selected clause.</p>
          <div className="file-list">
            {templates.slice(0, 10).map((template) => (
              <button
                className="version-row"
                disabled={!selectedPackId || !(selectedClauseId || clauses.some((item) => item.lifecycle_status === "published"))}
                key={template.key}
                onClick={() => void handleAddRule(template)}
                type="button"
              ><span>{template.title}</span><span>Add</span></button>
            ))}
          </div>
          {rules.map((rule) => (
            <div className="version-actions" key={rule.id}>
              <span>{rule.code} · {rule.lifecycle_status}</span>
              {rule.lifecycle_status === "draft" && (
                <button className="secondary-button" onClick={() => void handleReviewRule(rule.id)} type="button">Review</button>
              )}
            </div>
          ))}
          <button disabled={!selectedPackId || rules.length === 0} onClick={() => void handlePublishPack()} type="button">
            Publish reviewed pack
          </button>
        </div>

        <div className="panel clause-review">
          <div className="panel-heading">
            <p className="eyebrow">07 · Facts and results</p>
            <h2>Run an immutable review</h2>
          </div>
          <div className="file-list">
            {factCandidates.map((candidate) => (
              <article className="file-card" key={candidate.id}>
                <div>
                  <strong>{candidate.key}</strong>
                  <span>{String(candidate.value)} {candidate.unit ?? ""} · {candidate.verification_status}</span>
                </div>
                <p>
                  Confidence {candidate.confidence === null ? "—" : `${Math.round(candidate.confidence * 100)}%`}
                  {candidate.evidence[0]?.excerpt ? ` · ${candidate.evidence[0].excerpt}` : ""}
                </p>
                {candidate.evidence[0] && (
                  <span>{candidate.evidence[0].kind} · {JSON.stringify(candidate.evidence[0].location)}</span>
                )}
                {(candidate.verification_status === "candidate" || candidate.verification_status === "conflicting") && (
                  <div className="version-actions">
                    <button disabled={busy} onClick={() => void handleCandidateDecision(candidate.id, "verify")} type="button">Verify</button>
                    <button className="secondary-button" disabled={busy} onClick={() => void handleCandidateDecision(candidate.id, "reject")} type="button">Reject</button>
                  </div>
                )}
              </article>
            ))}
            {selectedProjectId && factCandidates.length === 0 && (
              <p className="empty">Extract a project document to create reviewable fact candidates.</p>
            )}
          </div>
          <form className="stack" onSubmit={handleFact}>
            <label>Fact key<input value={factKey} onChange={(event) => setFactKey(event.target.value)} /></label>
            <label>Value<input value={factValue} onChange={(event) => setFactValue(event.target.value)} /></label>
            <label>Unit<input value={factUnit} onChange={(event) => setFactUnit(event.target.value)} /></label>
            <button disabled={!selectedProjectId || !factValue} type="submit">Save verified fact</button>
          </form>
          <div className="file-list">
            {facts.map((fact) => (
              <div className="version-row" key={fact.id}>
                <span>{fact.key}</span><span>{String(fact.value)} {fact.unit ?? ""}</span>
              </div>
            ))}
          </div>
          <button disabled={!selectedProjectId || reviewPackIds.length === 0} onClick={() => void handleRunCheck()} type="button">
            Run compliance check
          </button>
          <div className="file-list" aria-label="Review package rule packs">
            {rulePacks.filter((pack) => pack.lifecycle_status === "published").map((pack) => (
              <label className="version-row" key={pack.id}>
                <input
                  checked={reviewPackIds.includes(pack.id)}
                  onChange={(event) => setReviewPackIds((current) => event.target.checked
                    ? [...new Set([...current, pack.id])]
                    : current.filter((id) => id !== pack.id))}
                  type="checkbox"
                />
                <span>{pack.authority_level} · {pack.name} {pack.semantic_version}</span>
              </label>
            ))}
          </div>
          <button disabled={!baselineRunId || checkRun?.status !== "completed"} onClick={() => void handleIncrementalCheck()} type="button">
            Run incremental recheck
          </button>
          {checkRun && <p className="empty">Run {checkRun.status} · {checkRun.input_hash.slice(0, 12)}</p>}
          {checkRun?.run_mode === "incremental" && (
            <p className="empty">
              Changed facts: {checkRun.changed_fact_keys.join(", ") || "none"} · re-executed {checkRun.affected_rule_ids.length} rules
            </p>
          )}
          {comparison && (
            <div className="file-card">
              <p className="empty">
                Comparison: {Object.entries(comparison.summary).map(([key, value]) => `${key} ${value}`).join(" · ")}
              </p>
              <button
                className="secondary-button"
                onClick={() => void openComparisonReport(
                  comparison.run_id,
                  comparison.baseline_run_id,
                ).catch((requestError: unknown) => {
                  setError(requestError instanceof Error ? requestError.message : "Unable to download comparison");
                })}
                type="button"
              >Download comparison JSON</button>
            </div>
          )}
          {conflicts.map((conflict) => (
            <div className="file-card" key={conflict.id}>
              <p className="empty">
                Conflict: {conflict.rule_codes.join(" / ")} · {conflict.resolution ? "resolved" : "human decision required"}
              </p>
              {!conflict.resolution && conflict.rule_ids.map((ruleId, index) => (
                <button
                  className="secondary-button"
                  key={ruleId}
                  onClick={() => void handleConflictResolution(conflict, ruleId)}
                  type="button"
                >Use {conflict.authority_levels[index]} · {conflict.rule_codes[index]}</button>
              ))}
            </div>
          ))}
          {recommendations.slice(0, 3).map((item) => (
            <p className="empty" key={item.standard_version_id}>
              {item.recommended ? "Recommended" : "Confirm applicability"}: {item.standard_code} {item.edition}
            </p>
          ))}
          {checkRun && !workbench && <p className="empty">The evidence workbench will load when the background check completes.</p>}
          {missingInformation && (
            <div className="file-list" aria-label="Missing information actions">
              {missingInformation.items.map((item) => (
                <article className="file-card" key={item.fact_key}>
                  <strong>{item.fact_key} · {item.severity}</strong>
                  <p>{item.action}</p>
                  <span>Affects {item.affected_rules.join(", ")}</span>
                </article>
              ))}
              {missingInformation.items.length === 0 && (
                <p className="empty">No missing rule inputs were identified.</p>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="panel pilot-panel" aria-label="Pilot feedback">
        <div className="panel-heading">
          <p className="eyebrow">12 · Pilot acceptance</p>
          <h2>Record an architect's observed result</h2>
        </div>
        <p className="empty">
          Report false positives, false negatives, evidence problems, usability issues, or
          measured value. This record supports triage; it is not an automatic acceptance sign-off.
        </p>
        <form className="stack" onSubmit={handlePilotFeedback}>
          <label>
            Category
            <select value={feedbackCategory} onChange={(event) => setFeedbackCategory(event.target.value)}>
              <option value="value">Value</option>
              <option value="false_positive">False positive</option>
              <option value="false_negative">False negative</option>
              <option value="evidence">Evidence</option>
              <option value="usability">Usability</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>
            Severity
            <select value={feedbackSeverity} onChange={(event) => setFeedbackSeverity(event.target.value)}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </label>
          <label>
            Summary
            <input value={feedbackSummary} onChange={(event) => setFeedbackSummary(event.target.value)} />
          </label>
          <label>
            Observed workflow and expected result
            <textarea value={feedbackDetails} onChange={(event) => setFeedbackDetails(event.target.value)} />
          </label>
          <button
            disabled={!selectedProjectId || !feedbackSummary.trim() || !feedbackDetails.trim()}
            type="submit"
          >Save pilot feedback</button>
          {feedbackSaved && <p className="success">Feedback saved for triage.</p>}
        </form>
      </section>

      <section className="drawing-workspace" aria-label="M5 drawing and finding workbench">
        <div className="panel drawing-viewer">
          <div className="panel-heading">
            <p className="eyebrow">08 · Drawing evidence</p>
            <h2>Page viewer and calibration</h2>
          </div>
          {drawingPages[0]?.image_url ? (
            <div className="drawing-canvas" onMouseDown={handleBoxStart} onMouseUp={handleBoxEnd} role="presentation">
              <img className="drawing-page" src={drawingPages[0].image_url} alt={`Drawing page ${drawingPages[0].page_number}`} draggable={false} />
              {selectedBox && (
                <span
                  className="drawing-selection"
                  style={{
                    left: `${(selectedBox.x0 / drawingPages[0].width) * 100}%`,
                    top: `${(1 - selectedBox.y1 / drawingPages[0].height) * 100}%`,
                    width: `${((selectedBox.x1 - selectedBox.x0) / drawingPages[0].width) * 100}%`,
                    height: `${((selectedBox.y1 - selectedBox.y0) / drawingPages[0].height) * 100}%`,
                  }}
                >Selected region</span>
              )}
            </div>
          ) : <p className="empty">Run drawing extraction on a PDF to create positioned page evidence.</p>}
          <form className="stack" onSubmit={handleBoxAnnotation}>
            <label>Annotation type<select value={annotationKind} onChange={(event) => setAnnotationKind(event.target.value as "object" | "dimension" | "scale")}><option value="object">Object</option><option value="dimension">Dimension</option><option value="scale">Scale</option></select></label>
            <label>Fact key<input value={annotationKey} onChange={(event) => setAnnotationKey(event.target.value)} /></label>
            <label>Corrected value<input value={annotationValue} onChange={(event) => setAnnotationValue(event.target.value)} /></label>
            <label>Unit<input value={annotationUnit} onChange={(event) => setAnnotationUnit(event.target.value)} /></label>
            <label>Corrects candidate<select value={correctionTargetId} onChange={(event) => setCorrectionTargetId(event.target.value)}><option value="">New annotation</option>{factCandidates.filter((item) => item.source === "drawing").map((item) => <option key={item.id} value={item.id}>{item.key} · {String(item.value)}</option>)}</select></label>
            <button disabled={!drawingPages[0] || !annotationKey || !annotationValue} type="submit">Save selected-region candidate</button>
          </form>
          <form className="stack" onSubmit={handlePathMeasurement}>
            <label>Path points (x,y; x,y)<input value={pathCoordinates} onChange={(event) => setPathCoordinates(event.target.value)} /></label>
            <label>Pixels per metre<input value={pixelsPerMeter} onChange={(event) => setPixelsPerMeter(event.target.value)} /></label>
            <button disabled={!drawingPages[0]} type="submit">Create travel-distance candidate</button>
          </form>
        </div>

        <div className="workbench-grid">
          <section className="workbench-column">
            <p className="eyebrow">09 · Findings</p>
            {workbench?.findings.map((finding) => (
              <button
                className={finding.result_id === selectedFinding?.result_id ? "finding-card is-selected" : "finding-card"}
                key={finding.result_id}
                onClick={() => setSelectedFindingId(finding.result_id)}
                type="button"
              >
                <strong>{finding.status} · {finding.severity}</strong>
                <span>{finding.message}</span>
              </button>
            ))}
            {!workbench && <p className="empty">Run a published rule pack to open the review workbench.</p>}
          </section>
          <section className="workbench-column">
            <p className="eyebrow">10 · Project evidence</p>
            {selectedFinding?.project_evidence.map((evidence) => (
              <article className="evidence-card" key={evidence.id}>
                <strong>Drawing page {String(evidence.location.page ?? "—")}</strong>
                <span>{evidence.excerpt ?? "No excerpt"}</span>
                {evidence.image_url && <a href={evidence.image_url} target="_blank" rel="noreferrer">Open positioned page</a>}
              </article>
            ))}
            {selectedFinding && selectedFinding.project_evidence.length === 0 && <p className="empty">No project evidence was used.</p>}
          </section>
          <section className="workbench-column">
            <p className="eyebrow">11 · Regulation basis</p>
            {selectedFinding && (
              <article className="evidence-card">
                <strong>{selectedFinding.trace.clause?.number ?? "Clause"} · page {selectedFinding.trace.clause?.page_number ?? "—"}</strong>
                <span>{selectedFinding.trace.clause?.original_text ?? "No clause snapshot"}</span>
                {selectedFinding.regulation_evidence[0]?.image_url && (
                  <a href={selectedFinding.regulation_evidence[0].image_url} target="_blank" rel="noreferrer">Open regulation page</a>
                )}
                <select value={selectedFinding.workflow_status} onChange={(event) => void handleFindingStatus(selectedFinding.result_id, event.target.value)}>
                  <option value="open">Open</option>
                  <option value="in_review">In review</option>
                  <option value="resolved">Resolved</option>
                  <option value="accepted_risk">Accepted risk</option>
                </select>
              </article>
            )}
            {workbench && (
              <div className="report-actions">
                <button
                  onClick={() => void openReport(workbench.run_id, "pdf").catch(
                    (requestError: unknown) => setError(
                      requestError instanceof Error ? requestError.message : "Unable to download PDF",
                    ),
                  )}
                  type="button"
                >PDF report</button>
                <button
                  className="secondary-button"
                  onClick={() => void openReport(workbench.run_id, "xlsx").catch(
                    (requestError: unknown) => setError(
                      requestError instanceof Error ? requestError.message : "Unable to download workbook",
                    ),
                  )}
                  type="button"
                >Excel report</button>
              </div>
            )}
          </section>
        </div>
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
              PDF, DOCX, XLSX, or IFC · up to 150 MB
              <input
                accept="application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.xlsx,application/x-step,.ifc"
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
                    {item.purpose === "project_document" && (
                      <div className="version-actions">
                        <button
                          className="secondary-button"
                          disabled={busy}
                          onClick={() => void handleExtract(version.id)}
                          type="button"
                        >Extract facts</button>
                        {version.original_filename.toLowerCase().endsWith(".pdf") && (
                          <button
                            className="secondary-button"
                            disabled={busy}
                            onClick={() => void handleDrawingExtract(version.id)}
                            type="button"
                          >Extract drawing</button>
                        )}
                      </div>
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
          {!job && <p className="empty">Upload a supported document to create a real Celery job.</p>}
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
          <div className="stack" aria-label="Standard edition comparison">
            <label>Earlier edition
              <select value={compareFromVersionId} onChange={(event) => setCompareFromVersionId(event.target.value)}>
                <option value="">Select an edition</option>
                {regulations.flatMap((standard) => standard.versions.map((version) => (
                  <option key={`from-${version.id}`} value={version.id}>{standard.code} · {version.edition}</option>
                )))}
              </select>
            </label>
            <label>Later edition
              <select value={compareToVersionId} onChange={(event) => setCompareToVersionId(event.target.value)}>
                <option value="">Select an edition</option>
                {regulations.flatMap((standard) => standard.versions.map((version) => (
                  <option key={`to-${version.id}`} value={version.id}>{standard.code} · {version.edition}</option>
                )))}
              </select>
            </label>
            <button disabled={!compareFromVersionId || !compareToVersionId} onClick={() => void handleVersionComparison()} type="button">
              Compare editions
            </button>
            {versionComparison && (
              <p className="empty">
                Clause changes: {Object.entries(versionComparison.summary).map(([key, value]) => `${key} ${value}`).join(" · ")}
              </p>
            )}
          </div>
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
