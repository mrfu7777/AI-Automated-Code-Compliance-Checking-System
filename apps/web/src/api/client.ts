export interface HealthResponse {
  status: "ok";
  service: string;
  api_version: "v1";
}
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(API_BASE_URL + "/health", { signal });

  if (!response.ok) {
    throw new Error("Health request failed with status " + response.status);
  }

  return response.json() as Promise<HealthResponse>;
}
