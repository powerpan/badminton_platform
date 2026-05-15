import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 10000,
});

const refreshHttp = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 10000,
});

let refreshPromise: Promise<string> | null = null;

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

function clearLocalSession() {
  localStorage.removeItem("bf_token");
  localStorage.removeItem("bf_refresh_token");
  localStorage.removeItem("bf_user");
}

function isPublicAuthRequest(url: string) {
  return [
    "/auth/captcha",
    "/auth/login",
    "/auth/register",
    "/auth/refresh",
    "/auth/logout",
    "/auth/password-reset/request",
    "/auth/password-reset/confirm",
  ].some((path) => url.includes(path));
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem("bf_refresh_token");
  if (!refreshToken) {
    throw new Error("请重新登录");
  }
  if (!refreshPromise) {
    refreshPromise = refreshHttp
      .post("/auth/refresh", { refresh_token: refreshToken })
      .then((response) => {
        const data = response.data.data;
        const token = data.access_token || data.token;
        localStorage.setItem("bf_token", token);
        localStorage.setItem("bf_refresh_token", data.refresh_token);
        localStorage.setItem("bf_user", JSON.stringify(data.user));
        return token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("bf_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const responseData = error.response?.data as { message?: string } | undefined;
    const message = responseData?.message || "请求失败";
    const originalConfig = error.config as RetryConfig | undefined;
    const requestUrl = originalConfig?.url || "";
    if (status === 401 && originalConfig && !originalConfig._retry && !requestUrl.includes("/auth/")) {
      originalConfig._retry = true;
      try {
        const token = await refreshAccessToken();
        originalConfig.headers.Authorization = `Bearer ${token}`;
        return http(originalConfig);
      } catch {
        clearLocalSession();
        if (window.location.pathname !== "/login") {
          window.location.assign("/login");
        }
      }
    } else if (status === 401 && !isPublicAuthRequest(requestUrl)) {
      clearLocalSession();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    } else if (status === 403 && window.location.pathname.startsWith("/admin")) {
      window.location.assign("/");
    }
    return Promise.reject(new Error(message));
  },
);
