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

test("renders the M6 workspace and confirms API connectivity", async () => {
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
      name: /freeze exact code editions, then recheck only what changed/i,
    }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /create project/i })).toBeDisabled();

  await waitFor(() => {
    expect(screen.getByText("API connected")).toBeInTheDocument();
  });
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
  fireEvent.change(screen.getByLabelText("Project name"), {
    target: { value: "Warehouse Renovation" },
  });
  fireEvent.change(screen.getByLabelText("Jurisdiction"), {
    target: { value: "Berlin" },
  });
  fireEvent.click(screen.getByRole("button", { name: /create project/i }));

  await waitFor(() => {
    expect(screen.getAllByText("Warehouse Renovation")).toHaveLength(2);
  });
  expect(screen.getByText("No files uploaded yet.")).toBeInTheDocument();
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

  const verifyButton = await screen.findByRole("button", { name: "Verify" });
  fireEvent.click(verifyButton);
  await waitFor(() => {
    expect(screen.getByText(/120 cm · verified/i)).toBeInTheDocument();
  });
  expect(fetchSpy).toHaveBeenCalledWith(
    expect.stringContaining(`/fact-candidates/${candidate.id}/verify`),
    expect.objectContaining({ method: "POST" }),
  );
});
