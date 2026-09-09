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

test("renders the M2 workspace and confirms API connectivity", async () => {
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
    screen.getByRole("heading", { name: /from source PDF to citable clauses/i }),
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
