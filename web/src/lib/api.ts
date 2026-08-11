const API_PREFIX = "/api";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API_PREFIX + path, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error ?? `Erreur HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function jsonRequest(
  method: "POST" | "PUT",
  body: unknown,
): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}
