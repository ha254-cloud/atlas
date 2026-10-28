import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from "axios";
import { getToken, clearToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// Attach JWT to every request
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401 clear the token and redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Extracts a human-readable message from a FastAPI error response, falling
 * back to a generic message if the shape is unexpected. */
export function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

/** Typed convenience helpers that return response.data directly */
export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) =>
    apiClient.get<T>(path, { params }).then((r) => r.data),

  post: <T>(path: string, body?: unknown) =>
    apiClient.post<T>(path, body).then((r) => r.data),

  put: <T>(path: string, body?: unknown) =>
    apiClient.put<T>(path, body).then((r) => r.data),

  patch: <T>(path: string, body?: unknown) =>
    apiClient.patch<T>(path, body).then((r) => r.data),

  delete: <T>(path: string) =>
    apiClient.delete<T>(path).then((r) => r.data),

  /** Multipart form upload (e.g. file uploads). Lets the browser set the boundary. */
  upload: <T>(path: string, formData: FormData) =>
    apiClient
      .post<T>(path, formData, { headers: { "Content-Type": undefined } })
      .then((r) => r.data),
};
