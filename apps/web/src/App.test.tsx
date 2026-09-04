import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});
test("renders the architecture baseline and confirms API connectivity", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        status: "ok",
        service: "code-compliance-api",
        api_version: "v1",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  render(<App />);

  expect(
    screen.getByRole("heading", {
      name: /review building codes with evidence/i,
    }),
  ).toBeInTheDocument();

  await waitFor(() => {
    expect(screen.getByText("API connected")).toBeInTheDocument();
  });
});
