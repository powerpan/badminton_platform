import axios from "axios";

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 10000,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("bf_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || "请求失败";
    if (error.response?.status === 401) {
      localStorage.removeItem("bf_token");
      localStorage.removeItem("bf_user");
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(new Error(message));
  },
);
