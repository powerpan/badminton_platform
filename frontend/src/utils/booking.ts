import type { SlotItem } from "../api/court";

export interface TimeRange { start_time: string; end_time: string }

export function timeToMinutes(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

export function rangePrice(hourlyCents: number, range: TimeRange) {
  return Math.floor(hourlyCents * (timeToMinutes(range.end_time) - timeToMinutes(range.start_time)) / 60);
}

export function selectRange(
  slots: SlotItem[], current: TimeRange | null, clicked: SlotItem, maxMinutes: number,
): { range: TimeRange | null; error?: string } {
  if (clicked.status !== "available") return { range: current, error: "该时段不可预约" };
  if (current?.start_time === clicked.start_time && current.end_time === clicked.end_time) return { range: null };
  const range = !current || (clicked.start_time >= current.start_time && clicked.end_time <= current.end_time)
    ? { start_time: clicked.start_time, end_time: clicked.end_time }
    : { start_time: current.start_time < clicked.start_time ? current.start_time : clicked.start_time,
        end_time: current.end_time > clicked.end_time ? current.end_time : clicked.end_time };
  if (timeToMinutes(range.end_time) - timeToMinutes(range.start_time) > maxMinutes) {
    return { range: current, error: `单次最多预约 ${maxMinutes / 60} 小时，请重新选择起止时段` };
  }
  const covered = slots.filter(slot => slot.start_time < range.end_time && slot.end_time > range.start_time)
    .sort((a, b) => a.start_time.localeCompare(b.start_time));
  let next = range.start_time;
  for (const slot of covered) {
    if (slot.start_time !== next || slot.status !== "available") {
      return { range: current, error: "不能跨过不可用时段，请选择连续空闲时间" };
    }
    next = slot.end_time;
  }
  if (next !== range.end_time) return { range: current, error: "时间段不连续，请刷新后重试" };
  return { range };
}

export function remainingSeconds(value: string | null | undefined, now: number) {
  if (!value) return 0;
  const deadline = new Date(value.replace(" ", "T")).getTime();
  return Number.isFinite(deadline) ? Math.max(0, Math.ceil((deadline - now) / 1000)) : 0;
}

export function countdownText(value: string | null | undefined, now: number) {
  const seconds = remainingSeconds(value, now);
  if (!seconds) return "已到期，等待刷新";
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function formatDeadline(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value.replace(" ", "T"));
  if (!Number.isFinite(date.getTime())) return "-";
  return date.toLocaleString("zh-CN", { hour12: false, year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
