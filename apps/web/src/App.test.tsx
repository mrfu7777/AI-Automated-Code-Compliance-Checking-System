import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("renders the Chinese architect workspace and confirms API connectivity", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    if (url.endsWith("/health")) {
      return Promise.resolve(
        jsonResponse({ status: "ok", service: "code-compliance-api", api_version: "v1" }),
      );
    }
    return Promise.resolve(jsonResponse([]));
  });

  render(<App />);

  expect(
    screen.getByRole("heading", {
      name: "上传建筑资料，快速发现消防合规问题",
    }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "创建项目" })).toBeDisabled();

  await waitFor(() => {
    expect(screen.getByText("服务正常")).toBeInTheDocument();
  });
});

test("loads the guided demo into the existing project and rule workflow", async () => {
  const project = {
    id: "11111111-1111-1111-1111-111111111111",
    name: "[DEMO] Existing Office Renovation",
    code: "DEMO-V1-FIRE",
    jurisdiction: "Synthetic training jurisdiction",
    design_date: "2026-01-15",
    building_type: "Existing office renovation",
    status: "active",
    created_at: "2026-09-15T00:00:00Z",
    updated_at: "2026-09-15T00:00:00Z",
  };
  const pack = {
    id: "22222222-2222-2222-2222-222222222222",
    standard_version_id: "33333333-3333-3333-3333-333333333333",
    name: "Synthetic V1 Fire Review Rules",
    semantic_version: "1.0.0",
    lifecycle_status: "published",
    content_hash: "a".repeat(64),
    authority_level: "project",
  };
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/health")) {
      return Promise.resolve(
        jsonResponse({ status: "ok", service: "code-compliance-api", api_version: "v1" }),
      );
    }
    if (url.endsWith("/release")) {
      return Promise.resolve(jsonResponse({ app_version: "1.0.0", demo_mode_enabled: true }));
    }
    if (url.endsWith("/demo/scenario") && init?.method === "POST") {
      return Promise.resolve(jsonResponse({
        created: true,
        project_id: project.id,
        rule_pack_id: pack.id,
        project_name: project.name,
        rule_pack_name: pack.name,
        expected_statuses: {},
        next_steps: ["Run the existing compliance check."],
      }, 201));
    }
    if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([project]));
    if (url.endsWith("/rule-packs")) return Promise.resolve(jsonResponse([pack]));
    return Promise.resolve(jsonResponse([]));
  });

  render(<App />);
  const demoButton = await screen.findByRole("button", { name: "加载演示项目" });
  fireEvent.click(demoButton);

  await waitFor(() => {
    expect(screen.getAllByText("【演示】既有办公楼改造项目").length).toBeGreaterThan(0);
  });
  expect(screen.getByText("下一步请点击下方“开始消防合规审查”。")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "开始消防合规审查" })).toBeEnabled();
});

test("creates and selects a project through the real client contract", async () => {
  const project = {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Warehouse Renovation",
    code: null,
    jurisdiction: "Berlin",
    design_date: null,
    building_type: null,
    status: "active",
    created_at: "2026-09-09T00:00:00Z",
    updated_at: "2026-09-09T00:00:00Z",
  };
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/health")) {
      return Promise.resolve(
        jsonResponse({ status: "ok", service: "code-compliance-api", api_version: "v1" }),
      );
    }
    if (url.endsWith("/projects") && init?.method === "POST") {
      return Promise.resolve(jsonResponse(project, 201));
    }
    return Promise.resolve(jsonResponse([]));
  });

  render(<App />);
  fireEvent.change(screen.getByLabelText("项目名称"), {
    target: { value: "Warehouse Renovation" },
  });
  fireEvent.change(screen.getByLabelText("适用地区"), {
    target: { value: "Berlin" },
  });
  fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

  await waitFor(() => {
    expect(screen.getAllByText("Warehouse Renovation")).toHaveLength(3);
  });
  expect(screen.getByText("该项目尚未上传资料。")).toBeInTheDocument();
});

test("verifies an extracted candidate before exposing it as a project fact", async () => {
  const project = {
    id: "11111111-1111-1111-1111-111111111111",
    name: "M4 Pilot",
    code: null,
    jurisdiction: "China",
    design_date: null,
    building_type: null,
    status: "active",
    created_at: "2026-09-13T00:00:00Z",
    updated_at: "2026-09-13T00:00:00Z",
  };
  const candidate = {
    id: "22222222-2222-2222-2222-222222222222",
    project_id: project.id,
    key: "egress.door_clear_width_m",
    value: 120,
    unit: "cm",
    scope_data: {},
    source: "spreadsheet",
    verification_status: "candidate",
    confidence: 1,
    extractor_version: "m4.project-extraction.v1",
    supersedes_id: null,
    evidence: [{
      id: "33333333-3333-3333-3333-333333333333",
      file_version_id: "44444444-4444-4444-4444-444444444444",
      kind: "spreadsheet_range",
      location: { sheet: "Fire Design", range: "A2:C2" },
      excerpt: "Egress door clear width 120 cm",
    }],
  };
  let verified = false;
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/health")) {
      return Promise.resolve(
        jsonResponse({ status: "ok", service: "code-compliance-api", api_version: "v1" }),
      );
    }
    if (url.endsWith("/projects")) return Promise.resolve(jsonResponse([project]));
    if (url.endsWith("/fact-candidates") && init?.method === undefined) {
      return Promise.resolve(jsonResponse([{ ...candidate, verification_status: verified ? "verified" : "candidate" }]));
    }
    if (url.endsWith(`/fact-candidates/${candidate.id}/verify`)) {
      verified = true;
      return Promise.resolve(jsonResponse({ ...candidate, verification_status: "verified" }));
    }
    if (url.endsWith(`/projects/${project.id}/facts`)) {
      return Promise.resolve(jsonResponse(verified ? [candidate] : []));
    }
    return Promise.resolve(jsonResponse([]));
  });

  render(<App />);

  const verifyButton = await screen.findByRole("button", { name: "确认" });
  fireEvent.click(verifyButton);
  await waitFor(() => {
    expect(screen.getByText(/120 cm · 已确认/i)).toBeInTheDocument();
  });
  expect(fetchSpy).toHaveBeenCalledWith(
    expect.stringContaining(`/fact-candidates/${candidate.id}/verify`),
    expect.objectContaining({ method: "POST" }),
  );
});
