import { defineStore } from "pinia";

import {
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "../api/notification";

export const useNotificationStore = defineStore("notification", {
  state: () => ({
    unreadCount: 0,
  }),
  actions: {
    async fetchUnreadCount() {
      const response = await getUnreadCount();
      this.unreadCount = response.data.unread_count;
      return this.unreadCount;
    },
    async markRead(notificationId: number) {
      const response = await markNotificationRead(notificationId);
      await this.fetchUnreadCount();
      return response.data;
    },
    async markAllRead() {
      const response = await markAllNotificationsRead();
      await this.fetchUnreadCount();
      return response.data;
    },
    clear() {
      this.unreadCount = 0;
    },
  },
});
