// Thin fetch wrapper matching API Design v0.1's contract exactly.
// Base URL is configurable via VITE_API_BASE_URL (see .env.example) so
// this points at localhost during development and wherever the API is
// actually deployed for the demo without a code change.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    // Every error response from the API includes a plain-language
    // `detail` field (API Design v0.1's cross-cutting rule) — surface
    // that directly rather than a generic "request failed".
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `Request failed (${res.status})`, res.status);
  }
  return res.json();
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export const api = {
  listPorts: () => request("/ports"),
  listVesselClasses: () => request("/vessel-classes"),
  listRoutes: () => request("/routes"),
  submitQuery: (payload) =>
    request("/queries", { method: "POST", body: JSON.stringify(payload) }),
};
