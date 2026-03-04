const DEFAULT_BACKEND_PORT = process.env.NEXT_PUBLIC_BACKEND_PORT ?? "8000";

function cleanBase(base: string): string {
  return base.replace(/\/+$/, "");
}

function inferHttpBaseFromLocation(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const protocol = window.location.protocol === "https:" ? "https:" : "http:";
  return `${protocol}//${window.location.hostname}:${DEFAULT_BACKEND_PORT}`;
}

export function getBackendHttpBase(): string {
  const envValue = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL;
  if (envValue) {
    return cleanBase(envValue);
  }
  const inferred = inferHttpBaseFromLocation();
  return cleanBase(inferred ?? `http://localhost:${DEFAULT_BACKEND_PORT}`);
}

export function getBackendWsBase(): string {
  const envValue = process.env.NEXT_PUBLIC_BACKEND_WS_URL;
  if (envValue) {
    return cleanBase(envValue);
  }
  const httpBase = getBackendHttpBase();
  if (httpBase.startsWith("https://")) {
    return httpBase.replace("https://", "wss://");
  }
  if (httpBase.startsWith("http://")) {
    return httpBase.replace("http://", "ws://");
  }
  return `ws://${httpBase}`;
}

export function toBackendAbsoluteUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getBackendHttpBase()}${normalizedPath}`;
}

export function getMapboxToken(): string {
  return process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
}
