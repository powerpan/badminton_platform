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

const defaultMember = {
  level: "normal" as const,
  level_label: "普通会员",
  balance_cents: 0,
  points: 0,
  expires_at: null,
  discount_rate: 100,
  effective_level: "normal" as const,
  effective_discount_rate: 100,
};

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
    const user = JSON.parse(rawUser) as UserInfo;
    return normalizeUser(user);
  } catch {
    localStorage.removeItem("bf_user");
    return null;
  }
}

function normalizeUser(user: UserInfo): UserInfo {
  user.member = { ...defaultMember, ...(user.member || {}) };
  return user;
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
      this.user = normalizeUser(user);
      localStorage.setItem("bf_token", token);
      localStorage.setItem("bf_refresh_token", refreshToken);
      localStorage.setItem("bf_user", JSON.stringify(this.user));
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
    setProfile(user: UserInfo) {
      this.user = normalizeUser(user);
      localStorage.setItem('bf_user', JSON.stringify(this.user));
    },
    async fetchProfile() {
      if (!this.token) {
        return null;
      }
      const response = await getProfile();
      this.setProfile(response.data);
      return this.user;
    },
    async updateProfile(payload: { nickname: string; contact: string }) {
      const response = await updateProfile(payload);
      this.setProfile(response.data);
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
