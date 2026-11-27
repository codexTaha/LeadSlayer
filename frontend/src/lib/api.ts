import type {
  DeliveryMode,
  DispatchResponse,
  HarveyStatusResponse,
  HealthResponse,
  ParseCsvResponse,
  PipelineStartResponse,
  PresetResponse,
  ResurrectResponse,
  RunStateSnapshot,
  StartupInput,
} from "@/types/contracts";

const API_BASE = "";

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const errBody = (await res.json()) as { detail?: string };
      if (errBody.detail) detail = errBody.detail;
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  return handleJson<HealthResponse>(res);
}

export async function fetchDemoPreset(): Promise<PresetResponse> {
  const res = await fetch(`${API_BASE}/api/demo/preset`, { cache: "no-store" });
  return handleJson<PresetResponse>(res);
}

export async function parseCsvLeads(file: File): Promise<ParseCsvResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/leads/parse-csv`, {
    method: "POST",
    body: form,
  });
  return handleJson<ParseCsvResponse>(res);
}

export async function startPipeline(
  input: StartupInput
): Promise<PipelineStartResponse> {
  const res = await fetch(`${API_BASE}/api/pipeline/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return handleJson<PipelineStartResponse>(res);
}

export async function fetchRunState(runId: string): Promise<RunStateSnapshot> {
  const res = await fetch(`${API_BASE}/api/pipeline/${runId}/state`, {
    cache: "no-store",
  });
  return handleJson<RunStateSnapshot>(res);
}

export async function resurrectLead(
  runId: string,
  leadId: string
): Promise<ResurrectResponse> {
  const res = await fetch(`${API_BASE}/api/pipeline/${runId}/resurrect/${leadId}`, {
    method: "POST",
  });
  return handleJson<ResurrectResponse>(res);
}

export async function fetchHarveyStatus(): Promise<HarveyStatusResponse> {
  const res = await fetch(`${API_BASE}/api/pipeline/harvey-status`, {
    cache: "no-store",
  });
  return handleJson<HarveyStatusResponse>(res);
}

export async function dispatchEmails(
  runId: string,
  leadIds: string[],
  deliveryMode: DeliveryMode = "SANDBOX"
): Promise<DispatchResponse> {
  const res = await fetch(`${API_BASE}/api/pipeline/${runId}/dispatch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lead_ids: leadIds, delivery_mode: deliveryMode }),
  });
  return handleJson<DispatchResponse>(res);
}

export function getStreamUrl(runId: string): string {
  const origin = process.env.NEXT_PUBLIC_SSE_ORIGIN || "";
  return `${origin}/api/pipeline/${runId}/stream`;
}

export function getExportUrl(runId: string, format: "csv" | "json"): string {
  return `${API_BASE}/api/pipeline/${runId}/export?format=${format}`;
}
