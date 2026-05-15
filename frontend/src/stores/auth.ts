import { defineStore } from "pinia";

import {
  changePassword,
  getProfile,
  login as loginRequest,
  register as registerRequest,
  updateProfile,
  type UserInfo,
} from "../api/auth";

interface UserState {
  user: UserInfo | null;
  token: string;
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
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token && state.user),
    isAdmin: (state) => state.user?.role === "admin",
  },
  actions: {
    setSession(token: string, user: UserInfo) {
      this.token = token;
      this.user = user;
      localStorage.setItem("bf_token", token);
      localStorage.setItem("bf_user", JSON.stringify(user));
    },
    async login(username: string, password: string) {
      const response = await loginRequest({ username, password });
      this.setSession(response.data.token, response.data.user);
    },
    async register(payload: { username: string; password: string; nickname: string; contact: string }) {
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
    },
    clearSession() {
      this.user = null;
      this.token = "";
      localStorage.removeItem("bf_token");
      localStorage.removeItem("bf_user");
    },
  },
});
