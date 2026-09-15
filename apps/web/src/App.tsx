import { FormEvent, MouseEvent as ReactMouseEvent, useCallback, useEffect, useRef, useState } from "react";

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
type SimpleReviewStep = "home" | "upload" | "ready" | "reviewing" | "finished";

const connectionLabels: Record<ConnectionState, string> = {
  checking: "正在连接",
  connected: "服务正常",
  unavailable: "服务不可用",
};

const statusLabels: Record<string, string> = {
  queued: "等待处理",
  running: "处理中",
  succeeded: "处理成功",
  failed: "处理失败",
  completed: "审查完成",
  compliant: "符合",
  non_compliant: "不符合",
  insufficient_information: "资料不足",
  open: "待处理",
  in_review: "复核中",
  resolved: "已解决",
  accepted_risk: "接受风险",
  candidate: "待确认",
  conflicting: "存在冲突",
  verified: "已确认",
  rejected: "已驳回",
  draft: "草稿",
  reviewed: "已复核",
  published: "已发布",
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
  national: "国家标准",
  industry: "行业标准",
  local: "地方标准",
  project: "项目要求",
  "regulation.parse": "规范解析",
  "check.run": "合规审查",
  "project.extract": "项目资料提取",
  "drawing.extract": "图纸提取",
  object: "对象",
  dimension: "尺寸",
  scale: "比例尺",
};

const factLabels: Record<string, string> = {
  "exit.count": "安全出口数量",
  "egress.door_clear_width_m": "疏散门净宽",
  "building.height_m": "建筑高度",
  "fire_compartment.area_m2": "防火分区面积",
};

const ruleTitleLabels: Record<string, string> = {
  "At least two exits": "安全出口数量不少于两个",
  "Exit clear width": "疏散门净宽要求",
  "Building height limit": "建筑高度限制",
  "Fire compartment area": "防火分区面积限制",
  "Building height scope": "建筑高度适用范围",
  "Fire compartment area limit": "防火分区面积上限",
  "Minimum number of safety exits": "安全出口最少数量",
  "Egress door clear width": "疏散门最小净宽",
  "Egress corridor clear width": "疏散走道最小净宽",
  "Egress stair clear width": "疏散楼梯最小净宽",
  "Maximum evacuation travel distance": "最大疏散距离",
  "Fire elevator provision": "消防电梯设置要求",
  "Required fire resistance rating": "建筑耐火等级要求",
  "Automatic sprinkler provision": "自动喷水灭火系统设置要求",
};

const demoTextLabels: Record<string, string> = {
  "Synthetic training jurisdiction": "演示用途（非真实适用地区）",
  "Synthetic project note": "演示项目资料",
  "Synthetic fire review standard": "演示消防审查规范",
  "Synthetic existing office plan": "演示既有办公楼图纸",
  "Synthetic Fire Safety Demonstration Standard": "演示消防安全规范",
  "D1 Exit count: the demo floor shall have at least two exits.": "D1 安全出口：演示楼层应至少设置两个安全出口。",
  "D2 Exit width: the demo exit clear width shall be at least 1.10 m.": "D2 出口宽度：演示项目疏散出口净宽不应小于 1.10 米。",
  "D3 Height: the demo building height shall not exceed 24 m.": "D3 建筑高度：演示建筑高度不应超过 24 米。",
  "D4 Compartment: the demo compartment area shall not exceed 2500 square metres.": "D4 防火分区：演示项目防火分区面积不应超过 2500 平方米。",
};

function localizedStatus(value: string) {
  return statusLabels[value] ?? value;
}

function localizedFact(value: string) {
  return factLabels[value] ?? value;
}

function localizedProjectName(value: string) {
  return value === "[DEMO] Existing Office Renovation" ? "【演示】既有办公楼改造项目" : value;
}

function localizedPackName(value: string) {
  return value === "Synthetic V1 Fire Review Rules" ? "演示用消防审查规则集" : value;
}

function localizedDemoText(value: string) {
  return demoTextLabels[value] ?? value;
}

function localizedFindingMessage(value: string) {
  if (value.startsWith("Missing required facts:")) {
    return `缺少审查所需资料：${localizedFact(value.replace("Missing required facts:", "").trim())}`;
  }
  const [title, result] = value.split(":", 2);
  const localizedTitle = ruleTitleLabels[title] ?? title;
  if (result?.includes("requirement satisfied")) return `${localizedTitle}：符合要求`;
  if (result?.includes("requirement not satisfied")) return `${localizedTitle}：不符合要求`;
  return value;
}

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
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [simpleStep, setSimpleStep] = useState<SimpleReviewStep>("home");
  const [simpleProjectId, setSimpleProjectId] = useState<string | null>(null);
  const [simplePackId, setSimplePackId] = useState<string | null>(null);
  const [simpleFileName, setSimpleFileName] = useState("");
  const [simpleFileSize, setSimpleFileSize] = useState(0);
  const [reportDownloaded, setReportDownloaded] = useState(false);
  const autoDownloadReport = useRef(false);

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
          setError(requestError instanceof Error ? requestError.message : "无法加载项目");
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selectedPackId) return;
    void listRules(selectedPackId).then(setRules).catch((requestError: unknown) => {
      setError(requestError instanceof Error ? requestError.message : "无法加载规则");
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
        setError(requestError instanceof Error ? requestError.message : "无法加载项目数据");
      });
  }, [selectedProjectId]);

  useEffect(() => {
    if (!selectedVersionId) {
      return;
    }
    void listClauses(selectedVersionId, query).then(setClauses).catch((requestError: unknown) => {
      setError(requestError instanceof Error ? requestError.message : "无法加载规范条文");
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
          setError(requestError instanceof Error ? requestError.message : "无法加载文件");
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
          if (updated.status === "failed" && autoDownloadReport.current) {
            autoDownloadReport.current = false;
            setSimpleStep("ready");
            setError(updated.error_data?.message ?? "消防审查失败，请重新开始检查。");
          }
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
                if (autoDownloadReport.current) {
                  autoDownloadReport.current = false;
                  setSimpleStep("finished");
                  void openReport(runId, "pdf")
                    .then(() => setReportDownloaded(true))
                    .catch((reportError: unknown) => {
                      setError(reportError instanceof Error ? reportError.message : "报告自动下载失败");
                    });
                }
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
            setError(requestError instanceof Error ? requestError.message : "无法刷新处理进度");
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
      setError(requestError instanceof Error ? requestError.message : "无法创建项目");
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
      setError(requestError instanceof Error ? requestError.message : "无法上传文件");
    } finally {
      setBusy(false);
    }
  }

  async function handleIngest(versionId: string) {
    const code = window.prompt("规范编号", "GB 55037-2022");
    if (!code) return;
    const edition = window.prompt("规范版本", "2022");
    if (!edition) return;
    setBusy(true);
    setError(null);
    try {
      const result = await ingestRegulation(
        versionId,
        code,
        code === "GB 55037-2022" ? "建筑防火通用规范" : code,
        edition,
        selectedProject?.jurisdiction ?? "中国",
      );
      setJob(result.job);
      setSelectedVersionId(result.version.id);
      setRegulations(await listRegulations());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法解析规范");
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
      setError(requestError instanceof Error ? requestError.message : "无法提取项目数据");
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
      setError(requestError instanceof Error ? requestError.message : "无法解析图纸");
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
      setError("请输入 x,y 坐标点，并填写大于零的每米像素数。");
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
      setError(requestError instanceof Error ? requestError.message : "无法保存路径测量");
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
        label: "建筑师修正的图纸标注",
        bbox: selectedBox,
        corrects_fact_id: correctionTargetId || null,
      });
      setFactCandidates(await listFactCandidates(selectedProjectId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法保存图纸标注");
    }
  }

  async function handleFindingStatus(resultId: string, workflowStatus: string) {
    if (!workbench) return;
    try {
      const updated = await updateFinding(resultId, workflowStatus, "建筑师审查工作台更新");
      setWorkbench({
        ...workbench,
        findings: workbench.findings.map((item) => item.result_id === resultId ? {
          ...item,
          workflow_status: updated.workflow_status,
          reviewer_notes: updated.reviewer_notes,
        } : item),
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法更新审查问题");
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
      setError(requestError instanceof Error ? requestError.message : "无法确认候选数据");
    } finally {
      setBusy(false);
    }
  }

  async function handleClauseSave() {
    if (!editingClause) return;
    setBusy(true);
    try {
      const updated = await updateClause(editingClause.id, editedText, "建筑师复核");
      setClauses((items) => items.map((item) => item.id === updated.id ? updated : item));
      setEditingClause(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法保存规范条文");
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
      setError(requestError instanceof Error ? requestError.message : "无法发布规范版本");
    }
  }

  async function handleRetry() {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      setJob(await retryJob(job.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法重试处理任务");
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
      setError(requestError instanceof Error ? requestError.message : "无法创建规则集");
    }
  }

  async function handleAddRule(template: RuleTemplate) {
    const clauseId = selectedClauseId || clauses.find((item) => item.lifecycle_status === "published")?.id;
    if (!selectedPackId || !clauseId) return;
    try {
      const created = await createRuleFromTemplate(selectedPackId, clauseId, template);
      setRules((items) => [...items, created]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法创建规则");
    }
  }

  async function handleReviewRule(ruleId: string) {
    try {
      const reviewed = await reviewRule(ruleId);
      setRules((items) => items.map((item) => item.id === ruleId ? reviewed : item));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法复核规则");
    }
  }

  async function handlePublishPack() {
    if (!selectedPackId) return;
    try {
      const published = await publishRulePack(selectedPackId);
      setRulePacks((items) => items.map((item) => item.id === published.id ? published : item));
      setRules(await listRules(selectedPackId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法发布规则集");
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
      setError(requestError instanceof Error ? requestError.message : "无法保存项目数据");
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
      setError(requestError instanceof Error ? requestError.message : "无法启动合规审查");
    }
  }

  async function handleSimpleUpload(event: FormEvent) {
    event.preventDefault();
    if (!upload) return;
    setBusy(true);
    setError(null);
    try {
      let packId = rulePacks.find((pack) => pack.lifecycle_status === "published")?.id ?? null;
      if (!packId && release?.demo_mode_enabled) {
        const scenario = await createDemoScenario();
        packId = scenario.rule_pack_id;
        setDemoScenario(scenario);
        const availablePacks = await listRulePacks();
        setRulePacks(availablePacks);
      }
      if (!packId) throw new Error("系统中还没有可用的消防审查规则，请先配置规则集。");

      const baseName = upload.name.replace(/\.[^.]+$/, "") || "建筑图纸";
      const created = await createProject(`消防审查-${baseName}-${Date.now()}`, "中国");
      const result = await uploadProjectFile(created.id, upload, upload.name, "project_drawing");
      setProjects((current) => [created, ...current]);
      setSelectedProjectId(created.id);
      setSimpleProjectId(created.id);
      setSimplePackId(packId);
      setSelectedPackId(packId);
      setReviewPackIds([packId]);
      setSimpleFileName(upload.name);
      setSimpleFileSize(upload.size);
      setFiles([result.project_file]);
      setJob(result.job);
      setUpload(null);
      setSimpleStep("ready");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法上传图纸");
    } finally {
      setBusy(false);
    }
  }

  async function handleSimpleReview() {
    if (!simpleProjectId || !simplePackId) return;
    setBusy(true);
    setError(null);
    setReportDownloaded(false);
    try {
      const created = await createCheckRun(simpleProjectId, [simplePackId]);
      setCheckRun(created.run);
      setWorkbench(null);
      setMissingInformation(null);
      autoDownloadReport.current = true;
      setJob(created.job);
      setSimpleStep("reviewing");
    } catch (requestError) {
      autoDownloadReport.current = false;
      setError(requestError instanceof Error ? requestError.message : "无法开始消防审查");
    } finally {
      setBusy(false);
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
      setError(requestError instanceof Error ? requestError.message : "无法启动增量复查");
    }
  }

  async function handleVersionComparison() {
    if (!compareFromVersionId || !compareToVersionId) return;
    try {
      setVersionComparison(await compareStandardVersions(compareFromVersionId, compareToVersionId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法比较规范版本");
    }
  }

  async function handleConflictResolution(conflict: RuleConflict, ruleId: string) {
    if (!checkRun) return;
    const note = window.prompt("选择此规则的原因", "建筑师适用性判断");
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
      setError(requestError instanceof Error ? requestError.message : "无法解决规则冲突");
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
      setError(requestError instanceof Error ? requestError.message : "无法保存反馈");
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
      setError(requestError instanceof Error ? requestError.message : "无法加载演示项目");
    } finally {
      setBusy(false);
    }
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const selectedFinding = workbench?.findings.find(
    (finding) => finding.result_id === selectedFindingId,
  ) ?? workbench?.findings[0] ?? null;
  const resultCounts = workbench?.findings.reduce<Record<string, number>>((counts, finding) => {
    counts[finding.status] = (counts[finding.status] ?? 0) + 1;
    return counts;
  }, {}) ?? {};

  return (
    <main className="shell">
      <nav className="topbar legacy-hidden" aria-label="主导航">
        <a className="brand" href="/" aria-label="建筑消防智能审查首页">
          <span className="brand-mark">建审</span>
          <span>建筑消防智能审查</span>
        </a>
        <span className={`connection connection--${connection}`}>
          <span className="connection-dot" aria-hidden="true" />
          {connectionLabels[connection]}
        </span>
        {release && <span className="release-badge">V{release.app_version}</span>}
      </nav>

      <section className="simple-review" aria-label="消防审查">
        {simpleStep === "home" && (
          <div className="simple-home">
            <h1>消防审查</h1>
            <p>
              上传一份建筑图纸，系统会按照已经配置好的消防规则逐条检查。
              审查结束后，PDF 报告会自动下载。审查结果仅供建筑师初步复核，不能替代法定消防审查。
            </p>
            <button
              className="simple-main-button"
              disabled={connection !== "connected"}
              onClick={() => setSimpleStep("upload")}
              type="button"
            >{connection === "connected" ? "开始审查" : "正在连接审查服务…"}</button>
          </div>
        )}

        {simpleStep === "upload" && (
          <form className="simple-card" onSubmit={handleSimpleUpload}>
            <p className="simple-step-label">第 1 步，共 2 步</p>
            <h1>上传建筑图纸</h1>
            <p>请选择一份需要审查的图纸文件。当前支持 PDF、DOCX、XLSX 和 IFC，建议优先上传 PDF。</p>
            <label className="simple-file-picker">
              <span>{upload ? "已选择图纸" : "选择图纸文件"}</span>
              <strong>{upload ? upload.name : "点击这里选择文件"}</strong>
              {upload && <small>{readableBytes(upload.size)}</small>}
              <input
                accept=".pdf,.docx,.xlsx,.ifc"
                aria-label="选择建筑图纸"
                onChange={(event) => setUpload(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <button className="simple-main-button" disabled={!upload || busy} type="submit">
              {busy ? "正在上传…" : "确认上传图纸"}
            </button>
            <button className="simple-text-button" onClick={() => setSimpleStep("home")} type="button">返回首页</button>
          </form>
        )}

        {simpleStep === "ready" && (
          <div className="simple-card">
            <p className="simple-step-label">第 2 步，共 2 步</p>
            <h1>图纸上传完成</h1>
            <div className="simple-file-confirmed">
              <span aria-hidden="true">✓</span>
              <div><strong>{simpleFileName}</strong><small>{readableBytes(simpleFileSize)}</small></div>
            </div>
            <div className="simple-explanation">
              <strong>点击开始后，系统会做什么？</strong>
              <p>系统会使用已配置的消防规则检查这份图纸。能确认的项目给出“符合”或“不符合”，无法从图纸确认的项目标记为“资料不足”。完成后自动下载 PDF 报告。</p>
            </div>
            <button className="simple-main-button" disabled={busy} onClick={() => void handleSimpleReview()} type="button">
              开始检查这份图纸
            </button>
            <button className="simple-text-button" onClick={() => setSimpleStep("upload")} type="button">重新选择图纸</button>
          </div>
        )}

        {simpleStep === "reviewing" && (
          <div className="simple-card simple-status" aria-live="polite">
            <span className="simple-spinner" aria-hidden="true" />
            <h1>正在检查图纸</h1>
            <p>系统正在逐条执行消防规则。检查完成后会自动下载 PDF 报告，请不要关闭此页面。</p>
            <div className="progress"><span style={{ width: `${Math.max(job?.progress ?? 0.08, 0.08) * 100}%` }} /></div>
          </div>
        )}

        {simpleStep === "finished" && (
          <div className="simple-card simple-status" aria-live="polite">
            <span className="simple-success" aria-hidden="true">✓</span>
            <h1>消防审查完成</h1>
            <p>{reportDownloaded ? "PDF 审查报告已经自动下载。" : "PDF 审查报告正在下载…"}</p>
            {workbench && (
              <div className="simple-result-summary">
                <span><strong>{resultCounts.compliant ?? 0}</strong>符合</span>
                <span><strong>{resultCounts.non_compliant ?? 0}</strong>不符合</span>
                <span><strong>{resultCounts.insufficient_information ?? 0}</strong>资料不足</span>
              </div>
            )}
            {workbench && <button className="simple-main-button" onClick={() => void openReport(workbench.run_id, "pdf")} type="button">再次下载报告</button>}
            <button
              className="simple-text-button"
              onClick={() => {
                setSimpleStep("upload");
                setSimpleFileName("");
                setSimpleFileSize(0);
                setWorkbench(null);
                setError(null);
              }}
              type="button"
            >审查另一份图纸</button>
          </div>
        )}

        {error && <div className="simple-error" role="alert">{error}</div>}
      </section>

      <section className="hero hero--compact legacy-hidden">
        <p className="eyebrow">V1.0 · 旧建筑改造消防合规辅助审查</p>
        <h1>上传建筑资料，快速发现消防合规问题</h1>
        <p className="hero-copy">
          系统将建筑图纸、项目资料与消防规范关联审查，给出符合、不符合或资料不足的判断，
          并保留图纸证据和规范依据，供建筑师复核。结果仅用于辅助初审，不能替代法定审查。
        </p>
        <div className="architect-flow" aria-label="使用流程">
          <div><strong>01</strong><span>上传建筑资料</span><small>图纸、说明、表格或 IFC</small></div>
          <div><strong>02</strong><span>选择审查规范</span><small>支持多个版本和规则集</small></div>
          <div><strong>03</strong><span>运行智能审查</span><small>后台自动提取并逐条判断</small></div>
          <div><strong>04</strong><span>复核问题证据</span><small>查看位置、条款和报告</small></div>
        </div>
        {release?.demo_mode_enabled && (
          <button className="primary-action" disabled={busy} onClick={() => void handleLoadDemo()} type="button">
            {busy ? "正在准备演示项目…" : "加载演示项目"}
          </button>
        )}
        {demoScenario && (
          <div className="demo-guide" aria-label="演示项目">
            <strong>演示资料已准备完成</strong>
            <span>{localizedProjectName(demoScenario.project_name)}</span>
            <span>采用规则：{localizedPackName(demoScenario.rule_pack_name)}</span>
            <p>下一步请点击下方“开始消防合规审查”。</p>
          </div>
        )}
      </section>

      <section className="review-console legacy-hidden" aria-label="消防合规审查">
        <div className="review-overview">
          <p className="eyebrow">当前审查项目</p>
          <h2>{selectedProject ? localizedProjectName(selectedProject.name) : "尚未选择项目"}</h2>
          <p>{selectedProject?.jurisdiction ? localizedDemoText(selectedProject.jurisdiction) : "加载演示项目，或在专业工具中创建并上传真实项目资料。"}</p>
          <div className="review-metrics">
            <span><strong>{files.length}</strong> 份资料</span>
            <span><strong>{facts.length}</strong> 项已确认数据</span>
            <span><strong>{reviewPackIds.length}</strong> 个规则集</span>
          </div>
          <button
            className="primary-action"
            disabled={busy || !selectedProjectId || reviewPackIds.length === 0}
            onClick={() => void handleRunCheck()}
            type="button"
          >{job?.status === "queued" || job?.status === "running" ? "正在审查…" : "开始消防合规审查"}</button>
          {job && (
            <div className="review-progress" aria-live="polite">
              <span>{localizedStatus(job.status)}</span>
              <div className="progress"><span style={{ width: `${job.progress * 100}%` }} /></div>
            </div>
          )}
        </div>

        <div className="result-overview">
          <p className="eyebrow">审查结果</p>
          {!workbench && <p className="empty">完成审查后，这里会显示问题数量、判断依据和图纸证据。</p>}
          {workbench && (
            <>
              <div className="result-counts">
                <span className="result-count result-count--ok"><strong>{resultCounts.compliant ?? 0}</strong>符合</span>
                <span className="result-count result-count--bad"><strong>{resultCounts.non_compliant ?? 0}</strong>不符合</span>
                <span className="result-count result-count--warn"><strong>{resultCounts.insufficient_information ?? 0}</strong>资料不足</span>
              </div>
              <div className="simple-findings">
                {workbench.findings.map((finding, index) => (
                  <button
                    className={finding.result_id === selectedFinding?.result_id ? "simple-finding is-selected" : "simple-finding"}
                    key={finding.result_id}
                    onClick={() => setSelectedFindingId(finding.result_id)}
                    type="button"
                  >
                    <span className={`finding-index finding-index--${finding.status}`}>{index + 1}</span>
                    <span><strong>{localizedStatus(finding.status)}</strong><small>{localizedFindingMessage(finding.message)}</small></span>
                  </button>
                ))}
              </div>
              <div className="report-actions">
                <button onClick={() => void openReport(workbench.run_id, "pdf")} type="button">下载 PDF 审查报告</button>
                <button className="secondary-button" onClick={() => void openReport(workbench.run_id, "xlsx")} type="button">下载 Excel 结果</button>
              </div>
            </>
          )}
        </div>
      </section>

      {selectedFinding && (
        <section className="evidence-summary legacy-hidden" aria-label="问题证据">
          <div>
            <p className="eyebrow">图纸与项目依据</p>
            {selectedFinding.project_evidence.map((evidence) => (
              <article className="evidence-card" key={evidence.id}>
                <strong>项目资料第 {String(evidence.location.page ?? "—")} 页</strong>
                <span>{evidence.excerpt ? localizedDemoText(evidence.excerpt) : "没有可显示的文字摘要"}</span>
                {evidence.image_url && <a href={evidence.image_url} target="_blank" rel="noreferrer">打开图纸定位页</a>}
              </article>
            ))}
            {selectedFinding.project_evidence.length === 0 && <p className="empty">本条结论没有引用项目证据，需要补充资料。</p>}
          </div>
          <div>
            <p className="eyebrow">规范依据</p>
            <article className="evidence-card">
              <strong>{selectedFinding.trace.clause?.number ?? "规范条文"} · 第 {selectedFinding.trace.clause?.page_number ?? "—"} 页</strong>
              <span>{selectedFinding.trace.clause?.original_text ? localizedDemoText(selectedFinding.trace.clause.original_text) : "没有可显示的条文摘要"}</span>
              {selectedFinding.regulation_evidence[0]?.image_url && <a href={selectedFinding.regulation_evidence[0].image_url} target="_blank" rel="noreferrer">打开规范原页</a>}
            </article>
          </div>
        </section>
      )}

      {error && <div className="alert legacy-hidden" role="alert">操作失败：{error}</div>}

      <details className="advanced-workspace legacy-hidden" open={showAdvanced} onToggle={(event) => setShowAdvanced(event.currentTarget.open)}>
        <summary>专业工具：项目资料、规范、规则与人工复核</summary>
        <form className="api-key-form" onSubmit={handleApiKey}>
          <label>
            试用 API 密钥
            <input aria-label="试用 API 密钥" autoComplete="off" type="password" value={apiKeyInput} onChange={(event) => setApiKeyInput(event.target.value)} />
          </label>
          <button type="submit">在本次浏览器会话中使用</button>
        </form>

      <section className="regulation-workspace" aria-label="规则与合规审查工具">
        <div className="panel regulation-library">
          <div className="panel-heading">
            <p className="eyebrow">06 · 已复核规则集</p>
            <h2>编制与发布规则</h2>
          </div>
          <button disabled={!selectedVersionId} onClick={() => void handleCreatePack()} type="button">
            根据所选规范创建规则集
          </button>
          <select
            aria-label="规则集"
            value={selectedPackId ?? ""}
            onChange={(event) => setSelectedPackId(event.target.value || null)}
          >
            <option value="">请选择规则集</option>
            {rulePacks.map((pack) => (
              <option key={pack.id} value={pack.id}>{localizedPackName(pack.name)} {pack.semantic_version} · {localizedStatus(pack.lifecycle_status)}</option>
            ))}
          </select>
          <select
            aria-label="来源条文"
            value={selectedClauseId || clauses.find((item) => item.lifecycle_status === "published")?.id || ""}
            onChange={(event) => setSelectedClauseId(event.target.value)}
          >
            <option value="">请选择已发布的来源条文</option>
            {clauses.filter((clause) => clause.lifecycle_status === "published").map((clause) => (
              <option key={clause.id} value={clause.id}>{clause.clause_number} · 第 {clause.page_number} 页</option>
            ))}
          </select>
          <p className="empty">模板仅用于辅助编制。每个阈值都必须与所选条文绑定并经过人工核对。</p>
          <div className="file-list">
            {templates.slice(0, 10).map((template) => (
              <button
                className="version-row"
                disabled={!selectedPackId || !(selectedClauseId || clauses.some((item) => item.lifecycle_status === "published"))}
                key={template.key}
                onClick={() => void handleAddRule(template)}
                type="button"
              ><span>{ruleTitleLabels[template.title] ?? template.title}</span><span>添加</span></button>
            ))}
          </div>
          {rules.map((rule) => (
            <div className="version-actions" key={rule.id}>
              <span>{rule.code} · {localizedStatus(rule.lifecycle_status)}</span>
              {rule.lifecycle_status === "draft" && (
                <button className="secondary-button" onClick={() => void handleReviewRule(rule.id)} type="button">复核</button>
              )}
            </div>
          ))}
          <button disabled={!selectedPackId || rules.length === 0} onClick={() => void handlePublishPack()} type="button">
            发布已复核规则集
          </button>
        </div>

        <div className="panel clause-review">
          <div className="panel-heading">
            <p className="eyebrow">07 · 项目数据与结果</p>
            <h2>运行可追溯审查</h2>
          </div>
          <div className="file-list">
            {factCandidates.map((candidate) => (
              <article className="file-card" key={candidate.id}>
                <div>
                  <strong>{candidate.key}</strong>
                  <span>{String(candidate.value)} {candidate.unit ?? ""} · {localizedStatus(candidate.verification_status)}</span>
                </div>
                <p>
                  置信度 {candidate.confidence === null ? "—" : `${Math.round(candidate.confidence * 100)}%`}
                  {candidate.evidence[0]?.excerpt ? ` · ${localizedDemoText(candidate.evidence[0].excerpt)}` : ""}
                </p>
                {candidate.evidence[0] && (
                  <span>{localizedStatus(candidate.evidence[0].kind)} · {JSON.stringify(candidate.evidence[0].location)}</span>
                )}
                {(candidate.verification_status === "candidate" || candidate.verification_status === "conflicting") && (
                  <div className="version-actions">
                    <button disabled={busy} onClick={() => void handleCandidateDecision(candidate.id, "verify")} type="button">确认</button>
                    <button className="secondary-button" disabled={busy} onClick={() => void handleCandidateDecision(candidate.id, "reject")} type="button">驳回</button>
                  </div>
                )}
              </article>
            ))}
            {selectedProjectId && factCandidates.length === 0 && (
              <p className="empty">请先解析项目资料，系统会在这里列出需要人工确认的数据。</p>
            )}
          </div>
          <form className="stack" onSubmit={handleFact}>
            <label>数据字段<input value={factKey} onChange={(event) => setFactKey(event.target.value)} /></label>
            <label>数值<input value={factValue} onChange={(event) => setFactValue(event.target.value)} /></label>
            <label>单位<input value={factUnit} onChange={(event) => setFactUnit(event.target.value)} /></label>
            <button disabled={!selectedProjectId || !factValue} type="submit">保存已确认数据</button>
          </form>
          <div className="file-list">
            {facts.map((fact) => (
              <div className="version-row" key={fact.id}>
                <span>{localizedFact(fact.key)}</span><span>{String(fact.value)} {fact.unit ?? ""}</span>
              </div>
            ))}
          </div>
          <button disabled={!selectedProjectId || reviewPackIds.length === 0} onClick={() => void handleRunCheck()} type="button">
            开始合规审查
          </button>
          <div className="file-list" aria-label="本次审查使用的规则集">
            {rulePacks.filter((pack) => pack.lifecycle_status === "published").map((pack) => (
              <label className="version-row" key={pack.id}>
                <input
                  checked={reviewPackIds.includes(pack.id)}
                  onChange={(event) => setReviewPackIds((current) => event.target.checked
                    ? [...new Set([...current, pack.id])]
                    : current.filter((id) => id !== pack.id))}
                  type="checkbox"
                />
                <span>{localizedStatus(pack.authority_level)} · {localizedPackName(pack.name)} {pack.semantic_version}</span>
              </label>
            ))}
          </div>
          <button disabled={!baselineRunId || checkRun?.status !== "completed"} onClick={() => void handleIncrementalCheck()} type="button">
            仅复查发生变化的内容
          </button>
          {checkRun && <p className="empty">审查状态：{localizedStatus(checkRun.status)} · 输入版本 {checkRun.input_hash.slice(0, 12)}</p>}
          {checkRun?.run_mode === "incremental" && (
            <p className="empty">
              变化数据：{checkRun.changed_fact_keys.map(localizedFact).join("、") || "无"} · 重新执行 {checkRun.affected_rule_ids.length} 条规则
            </p>
          )}
          {comparison && (
            <div className="file-card">
              <p className="empty">
                对比结果：{Object.entries(comparison.summary).map(([key, value]) => `${key} ${value}`).join(" · ")}
              </p>
              <button
                className="secondary-button"
                onClick={() => void openComparisonReport(
                  comparison.run_id,
                  comparison.baseline_run_id,
                ).catch((requestError: unknown) => {
                  setError(requestError instanceof Error ? requestError.message : "无法下载对比结果");
                })}
                type="button"
              >下载 JSON 对比结果</button>
            </div>
          )}
          {conflicts.map((conflict) => (
            <div className="file-card" key={conflict.id}>
              <p className="empty">
                规则冲突：{conflict.rule_codes.join(" / ")} · {conflict.resolution ? "已解决" : "需要人工选择"}
              </p>
              {!conflict.resolution && conflict.rule_ids.map((ruleId, index) => (
                <button
                  className="secondary-button"
                  key={ruleId}
                  onClick={() => void handleConflictResolution(conflict, ruleId)}
                  type="button"
                >采用 {localizedStatus(conflict.authority_levels[index])} · {conflict.rule_codes[index]}</button>
              ))}
            </div>
          ))}
          {recommendations.slice(0, 3).map((item) => (
            <p className="empty" key={item.standard_version_id}>
              {item.recommended ? "建议采用" : "请确认是否适用"}：{item.standard_code} {item.edition}
            </p>
          ))}
          {checkRun && !workbench && <p className="empty">后台审查完成后将自动加载证据工作台。</p>}
          {missingInformation && (
            <div className="file-list" aria-label="缺失资料处理建议">
              {missingInformation.items.map((item) => (
                <article className="file-card" key={item.fact_key}>
                  <strong>{localizedFact(item.fact_key)} · {localizedStatus(item.severity)}</strong>
                  <p>{item.action}</p>
                  <span>影响规则：{item.affected_rules.join("、")}</span>
                </article>
              ))}
              {missingInformation.items.length === 0 && (
                <p className="empty">没有发现规则所需资料缺失。</p>
              )}
            </div>
          )}
        </div>
      </section>

      <section className="panel pilot-panel" aria-label="试用反馈">
        <div className="panel-heading">
          <p className="eyebrow">12 · 建筑师试用反馈</p>
          <h2>记录实际使用中发现的问题</h2>
        </div>
        <p className="empty">
          可记录误报、漏报、证据问题、易用性问题或实际测量值。反馈用于后续处理，
          保存反馈不代表系统已经通过专业验收。
        </p>
        <form className="stack" onSubmit={handlePilotFeedback}>
          <label>
            问题类型
            <select value={feedbackCategory} onChange={(event) => setFeedbackCategory(event.target.value)}>
              <option value="value">数值问题</option>
              <option value="false_positive">误报</option>
              <option value="false_negative">漏报</option>
              <option value="evidence">证据问题</option>
              <option value="usability">易用性问题</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>
            严重程度
            <select value={feedbackSeverity} onChange={(event) => setFeedbackSeverity(event.target.value)}>
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">严重</option>
            </select>
          </label>
          <label>
            问题摘要
            <input value={feedbackSummary} onChange={(event) => setFeedbackSummary(event.target.value)} />
          </label>
          <label>
            实际操作过程与期望结果
            <textarea value={feedbackDetails} onChange={(event) => setFeedbackDetails(event.target.value)} />
          </label>
          <button
            disabled={!selectedProjectId || !feedbackSummary.trim() || !feedbackDetails.trim()}
            type="submit"
          >保存试用反馈</button>
          {feedbackSaved && <p className="success">反馈已保存，等待后续处理。</p>}
        </form>
      </section>

      <section className="drawing-workspace" aria-label="图纸与问题复核工作台">
        <div className="panel drawing-viewer">
          <div className="panel-heading">
            <p className="eyebrow">08 · 图纸证据</p>
            <h2>图纸查看与比例校准</h2>
          </div>
          {drawingPages[0]?.image_url ? (
            <div className="drawing-canvas" onMouseDown={handleBoxStart} onMouseUp={handleBoxEnd} role="presentation">
              <img className="drawing-page" src={drawingPages[0].image_url} alt={`图纸第 ${drawingPages[0].page_number} 页`} draggable={false} />
              {selectedBox && (
                <span
                  className="drawing-selection"
                  style={{
                    left: `${(selectedBox.x0 / drawingPages[0].width) * 100}%`,
                    top: `${(1 - selectedBox.y1 / drawingPages[0].height) * 100}%`,
                    width: `${((selectedBox.x1 - selectedBox.x0) / drawingPages[0].width) * 100}%`,
                    height: `${((selectedBox.y1 - selectedBox.y0) / drawingPages[0].height) * 100}%`,
                  }}
                >已选区域</span>
              )}
            </div>
          ) : <p className="empty">请先解析 PDF 图纸，系统会生成可定位的页面证据。</p>}
          <form className="stack" onSubmit={handleBoxAnnotation}>
            <label>标注类型<select value={annotationKind} onChange={(event) => setAnnotationKind(event.target.value as "object" | "dimension" | "scale")}><option value="object">构件</option><option value="dimension">尺寸</option><option value="scale">比例</option></select></label>
            <label>数据字段<input value={annotationKey} onChange={(event) => setAnnotationKey(event.target.value)} /></label>
            <label>修正后的值<input value={annotationValue} onChange={(event) => setAnnotationValue(event.target.value)} /></label>
            <label>单位<input value={annotationUnit} onChange={(event) => setAnnotationUnit(event.target.value)} /></label>
            <label>修正已有数据<select value={correctionTargetId} onChange={(event) => setCorrectionTargetId(event.target.value)}><option value="">新建标注</option>{factCandidates.filter((item) => item.source === "drawing").map((item) => <option key={item.id} value={item.id}>{localizedFact(item.key)} · {String(item.value)}</option>)}</select></label>
            <button disabled={!drawingPages[0] || !annotationKey || !annotationValue} type="submit">保存所选区域数据</button>
          </form>
          <form className="stack" onSubmit={handlePathMeasurement}>
            <label>路径坐标点（x,y; x,y）<input value={pathCoordinates} onChange={(event) => setPathCoordinates(event.target.value)} /></label>
            <label>每米像素数<input value={pixelsPerMeter} onChange={(event) => setPixelsPerMeter(event.target.value)} /></label>
            <button disabled={!drawingPages[0]} type="submit">计算疏散距离候选值</button>
          </form>
        </div>

        <div className="workbench-grid">
          <section className="workbench-column">
            <p className="eyebrow">09 · 审查问题</p>
            {workbench?.findings.map((finding) => (
              <button
                className={finding.result_id === selectedFinding?.result_id ? "finding-card is-selected" : "finding-card"}
                key={finding.result_id}
                onClick={() => setSelectedFindingId(finding.result_id)}
                type="button"
              >
                <strong>{localizedStatus(finding.status)} · {localizedStatus(finding.severity)}</strong>
                <span>{localizedFindingMessage(finding.message)}</span>
              </button>
            ))}
            {!workbench && <p className="empty">请选择已发布规则集并运行审查，以打开问题复核工作台。</p>}
          </section>
          <section className="workbench-column">
            <p className="eyebrow">10 · 项目证据</p>
            {selectedFinding?.project_evidence.map((evidence) => (
              <article className="evidence-card" key={evidence.id}>
                <strong>图纸第 {String(evidence.location.page ?? "—")} 页</strong>
                <span>{evidence.excerpt ? localizedDemoText(evidence.excerpt) : "没有文字摘要"}</span>
                {evidence.image_url && <a href={evidence.image_url} target="_blank" rel="noreferrer">打开定位页</a>}
              </article>
            ))}
            {selectedFinding && selectedFinding.project_evidence.length === 0 && <p className="empty">本条结论没有引用项目证据。</p>}
          </section>
          <section className="workbench-column">
            <p className="eyebrow">11 · 规范依据</p>
            {selectedFinding && (
              <article className="evidence-card">
                <strong>{selectedFinding.trace.clause?.number ?? "规范条文"} · 第 {selectedFinding.trace.clause?.page_number ?? "—"} 页</strong>
                <span>{selectedFinding.trace.clause?.original_text ? localizedDemoText(selectedFinding.trace.clause.original_text) : "没有条文快照"}</span>
                {selectedFinding.regulation_evidence[0]?.image_url && (
                  <a href={selectedFinding.regulation_evidence[0].image_url} target="_blank" rel="noreferrer">打开规范原页</a>
                )}
                <select value={selectedFinding.workflow_status} onChange={(event) => void handleFindingStatus(selectedFinding.result_id, event.target.value)}>
                  <option value="open">待处理</option>
                  <option value="in_review">复核中</option>
                  <option value="resolved">已解决</option>
                  <option value="accepted_risk">接受风险</option>
                </select>
              </article>
            )}
            {workbench && (
              <div className="report-actions">
                <button
                  onClick={() => void openReport(workbench.run_id, "pdf").catch(
                    (requestError: unknown) => setError(
                      requestError instanceof Error ? requestError.message : "无法下载 PDF 报告",
                    ),
                  )}
                  type="button"
                >下载 PDF 报告</button>
                <button
                  className="secondary-button"
                  onClick={() => void openReport(workbench.run_id, "xlsx").catch(
                    (requestError: unknown) => setError(
                      requestError instanceof Error ? requestError.message : "无法下载 Excel 报告",
                    ),
                  )}
                  type="button"
                >下载 Excel 报告</button>
              </div>
            )}
          </section>
        </div>
      </section>

      <section className="workspace" aria-label="项目资料工作台">
        <aside className="panel project-panel">
          <div className="panel-heading">
            <p className="eyebrow">01 · 项目</p>
            <h2>选择审查项目</h2>
          </div>
          <form className="stack" onSubmit={handleCreate}>
            <label>
              项目名称
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
            </label>
            <label>
              适用地区
              <input value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)} />
            </label>
            <button disabled={busy || !projectName.trim()} type="submit">创建项目</button>
          </form>
          <div className="project-list">
            {projects.map((project) => (
              <button
                className={project.id === selectedProjectId ? "project-item is-selected" : "project-item"}
                key={project.id}
                onClick={() => setSelectedProjectId(project.id)}
                type="button"
              >
                <strong>{localizedProjectName(project.name)}</strong>
                <span>{project.jurisdiction ? localizedDemoText(project.jurisdiction) : "尚未设置适用地区"}</span>
              </button>
            ))}
            {projects.length === 0 && <p className="empty">请创建第一个旧建筑改造项目。</p>}
          </div>
        </aside>

        <section className="panel file-panel">
          <div className="panel-heading">
            <p className="eyebrow">02 · 项目资料</p>
            <h2>{selectedProject ? localizedProjectName(selectedProject.name) : "请选择项目"}</h2>
          </div>
          <form className="stack upload-form" onSubmit={handleUpload}>
            <label>
              资料名称
              <input
                disabled={!selectedProject}
                placeholder="例如：既有建筑首层平面图"
                value={logicalName}
                onChange={(event) => setLogicalName(event.target.value)}
              />
            </label>
            <label className="file-picker">
              支持 PDF、DOCX、XLSX 或 IFC · 最大 150 MB
              <input
                accept="application/pdf,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,.xlsx,application/x-step,.ifc"
                disabled={!selectedProject}
                onChange={(event) => setUpload(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <label>
              资料用途
              <select value={purpose} onChange={(event) => setPurpose(event.target.value)}>
                <option value="project_document">建筑项目资料</option>
                <option value="regulation_source">规范文件</option>
              </select>
            </label>
            <button disabled={busy || !selectedProject || !upload} type="submit">上传资料</button>
          </form>
          <div className="file-list">
            {files.map((item) => (
              <article className="file-card" key={item.id}>
                <div>
                  <strong>{localizedDemoText(item.logical_name)}</strong>
                  <span>{item.versions.length} 个版本</span>
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
                      >解析规范条文</button>
                    )}
                    {item.purpose === "project_document" && (
                      <div className="version-actions">
                        <button
                          className="secondary-button"
                          disabled={busy}
                          onClick={() => void handleExtract(version.id)}
                          type="button"
                        >提取项目数据</button>
                        {version.original_filename.toLowerCase().endsWith(".pdf") && (
                          <button
                            className="secondary-button"
                            disabled={busy}
                            onClick={() => void handleDrawingExtract(version.id)}
                            type="button"
                          >解析图纸</button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </article>
            ))}
            {selectedProject && files.length === 0 && <p className="empty">该项目尚未上传资料。</p>}
          </div>
        </section>

        <aside className="panel job-panel">
          <div className="panel-heading">
            <p className="eyebrow">03 · 后台处理</p>
            <h2>处理进度</h2>
          </div>
          {!job && <p className="empty">上传支持的资料后，系统将在后台自动处理。</p>}
          {job && (
            <article className="job-card" aria-live="polite">
              <div className="job-state">
                <span className={`status status--${job.status}`}>{localizedStatus(job.status)}</span>
                <span>{Math.round(job.progress * 100)}%</span>
              </div>
              <div className="progress"><span style={{ width: `${job.progress * 100}%` }} /></div>
              <dl>
                <div><dt>任务类型</dt><dd>{localizedStatus(job.job_type)}</dd></div>
                <div><dt>尝试次数</dt><dd>{job.attempts} / {job.max_attempts}</dd></div>
                <div><dt>请求编号</dt><dd>{job.request_id ?? "—"}</dd></div>
              </dl>
              {job.error_data?.message && <p className="job-error">{job.error_data.message}</p>}
              {job.status === "failed" && job.attempts < job.max_attempts && (
                <button disabled={busy} onClick={() => void handleRetry()} type="button">重试处理</button>
              )}
            </article>
          )}
        </aside>
      </section>

      <section className="regulation-workspace" aria-label="规范管理工作台">
        <div className="panel regulation-library">
          <div className="panel-heading">
            <p className="eyebrow">04 · 规范版本</p>
            <h2>规范资料库</h2>
          </div>
          {regulations.map((standard) => (
            <article className="file-card" key={standard.id}>
              <strong>{standard.code}</strong>
              <span>{localizedDemoText(standard.title)}</span>
              {standard.versions.map((version) => (
                <button
                  className="version-row"
                  key={version.id}
                  onClick={() => setSelectedVersionId(version.id)}
                  type="button"
                >
                  <span>{version.edition}</span><span>{localizedStatus(version.lifecycle_status)}</span>
                </button>
              ))}
            </article>
          ))}
          {regulations.length === 0 && <p className="empty">尚未导入规范版本。</p>}
          <div className="stack" aria-label="规范版本对比">
            <label>较早版本
              <select value={compareFromVersionId} onChange={(event) => setCompareFromVersionId(event.target.value)}>
                <option value="">请选择版本</option>
                {regulations.flatMap((standard) => standard.versions.map((version) => (
                  <option key={`from-${version.id}`} value={version.id}>{standard.code} · {version.edition}</option>
                )))}
              </select>
            </label>
            <label>较新版本
              <select value={compareToVersionId} onChange={(event) => setCompareToVersionId(event.target.value)}>
                <option value="">请选择版本</option>
                {regulations.flatMap((standard) => standard.versions.map((version) => (
                  <option key={`to-${version.id}`} value={version.id}>{standard.code} · {version.edition}</option>
                )))}
              </select>
            </label>
            <button disabled={!compareFromVersionId || !compareToVersionId} onClick={() => void handleVersionComparison()} type="button">
              对比规范版本
            </button>
            {versionComparison && (
              <p className="empty">
                条文变化：{Object.entries(versionComparison.summary).map(([key, value]) => `${key} ${value}`).join(" · ")}
              </p>
            )}
          </div>
        </div>

        <div className="panel clause-review">
          <div className="panel-heading">
            <p className="eyebrow">05 · 人工复核</p>
            <h2>检索并修正规范条文</h2>
          </div>
          <div className="clause-toolbar">
            <input
              aria-label="搜索规范条文"
              placeholder="输入条文编号或内容"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <button disabled={!selectedVersionId} onClick={() => void handlePublish()} type="button">
              发布已复核版本
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
                <span>第 {clause.page_number} 页 · {localizedStatus(clause.lifecycle_status)}</span>
                <p>{localizedDemoText(clause.original_text)}</p>
              </button>
            ))}
          </div>
          {editingClause && (
            <div className="clause-editor">
              <strong>复核条文 {editingClause.clause_number}</strong>
              <textarea value={editedText} onChange={(event) => setEditedText(event.target.value)} />
              <button disabled={busy || !editedText.trim()} onClick={() => void handleClauseSave()} type="button">
                保存并标记为已复核
              </button>
            </div>
          )}
        </div>
      </section>
      </details>
    </main>
  );
}

export default App;
