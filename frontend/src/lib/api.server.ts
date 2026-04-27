import { cookies } from "next/headers";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || "http://backend:8000";

export async function serverFetch(path: string, options: RequestInit = {}) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Cookie"] = `access_token=${accessToken}`;
  }

  const response = await fetch(`${INTERNAL_API_URL}/api/v1${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  return response;
}

export async function serverGet<T>(path: string): Promise<T | null> {
  try {
    const response = await serverFetch(path);
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}
