import { http } from "./http";

export interface HealthResponse {
  api: { status: string };
  mysql: { status: string; message?: string };
  redis: { status: string; message?: string };
  env: string;
  checked_at: string;
}

export function getHealth() {
  return http.get<unknown, { code: number; message: string; data: HealthResponse }>("/health");
}
