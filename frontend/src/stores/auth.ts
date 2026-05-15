import { defineStore } from "pinia";

import {
  changePassword,
  getProfile,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  updateProfile,
  type UserInfo,
} from "../api/auth";

interface UserState {
  user: UserInfo | null;
  token: string;
  refreshToken: string;
}

function readStoredUser(): UserInfo | null {
  const rawUser = localStorage.getItem("bf_user");
  if (!rawUser) {
    return null;
  }
  try {
    return JSON.parse(rawUser) as UserInfo;
  } catch {
    localStorage.removeItem("bf_user");
    return null;
  }
}

export const useAuthStore = defineStore("auth", {
  state: (): UserState => ({
    user: readStoredUser(),
    token: localStorage.getItem("bf_token") || "",
    refreshToken: localStorage.getItem("bf_refresh_token") || "",
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token && state.user),
    isAdmin: (state) => state.user?.role === "admin",
  },
  actions: {
    setSession(token: string, refreshToken: string, user: UserInfo) {
      this.token = token;
      this.refreshToken = refreshToken;
      this.user = user;
      localStorage.setItem("bf_token", token);
      localStorage.setItem("bf_refresh_token", refreshToken);
      localStorage.setItem("bf_user", JSON.stringify(user));
    },
    async login(username: string, password: string, captchaId: string, captchaCode: string) {
      const response = await loginRequest({
        username,
        password,
        captcha_id: captchaId,
        captcha_code: captchaCode,
      });
      this.setSession(response.data.access_token || response.data.token, response.data.refresh_token, response.data.user);
    },
    async register(payload: {
      username: string;
      password: string;
      nickname: string;
      contact: string;
      captcha_id: string;
      captcha_code: string;
    }) {
      await registerRequest(payload);
    },
    async fetchProfile() {
      if (!this.token) {
        return null;
      }
      const response = await getProfile();
      this.user = response.data;
      localStorage.setItem("bf_user", JSON.stringify(response.data));
      return response.data;
    },
    async updateProfile(payload: { nickname: string; contact: string }) {
      const response = await updateProfile(payload);
      this.user = response.data;
      localStorage.setItem("bf_user", JSON.stringify(response.data));
    },
    async changePassword(payload: { old_password: string; new_password: string }) {
      await changePassword(payload);
      await this.fetchProfile();
    },
    async logout() {
      const refreshToken = this.refreshToken || localStorage.getItem("bf_refresh_token") || "";
      this.clearSession();
      if (refreshToken) {
        try {
          await logoutRequest({ refresh_token: refreshToken });
        } catch {
          // Local session is already cleared; logout should not block navigation.
        }
      }
    },
    clearSession() {
      this.user = null;
      this.token = "";
      this.refreshToken = "";
      localStorage.removeItem("bf_token");
      localStorage.removeItem("bf_refresh_token");
      localStorage.removeItem("bf_user");
    },
  },
});
