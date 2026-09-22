import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";

// Exercise the actual TS module without adding a test framework or requiring TS runtime support.
const source = readFileSync(new URL("../src/utils/booking.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText;
const { selectRange, rangePrice, remainingSeconds } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const slots = [17, 18, 19, 20].map(hour => ({ start_time: `${hour}:00`, end_time: `${hour + 1}:00`, status: "available", price_cents: 12000 }));

test("select adjacent slots into a continuous two-hour interval", () => {
  const first = selectRange(slots, null, slots[1], 120).range;
  assert.deepEqual(selectRange(slots, first, slots[2], 120).range, { start_time: "18:00", end_time: "20:00" });
});
test("supports selecting backwards and deselecting a single slot", () => {
  assert.deepEqual(selectRange(slots, slots[2], slots[1], 120).range, { start_time: "18:00", end_time: "20:00" });
  assert.equal(selectRange(slots, slots[1], slots[1], 120).range, null);
});
test("refuses a range crossing an occupied slot", () => {
  const blocked = slots.map((slot, index) => ({ ...slot, status: index === 1 ? "reserved" : "available" }));
  const result = selectRange(blocked, slots[0], slots[2], 240);
  assert.match(result.error, /不可用/);
  assert.equal(result.range, slots[0]);
});
test("refuses a missing slot and a range beyond the duration limit", () => {
  assert.ok(selectRange([slots[0], slots[2]], slots[0], slots[2], 240).error);
  assert.match(selectRange(slots, slots[0], slots[2], 120).error, /最多/);
});
test("half-hour pricing and final total use the backend integer rounding rule", () => {
  assert.equal(rangePrice(13000, { start_time: "18:00", end_time: "18:30" }), 6500);
  assert.equal(rangePrice(13000, { start_time: "18:00", end_time: "20:00" }), 26000);
  assert.equal(rangePrice(10001, { start_time: "18:00", end_time: "18:30" }), 5000);
});
test("expiry is exact and invalid timestamps cannot be paid", () => {
  const now = Date.parse("2026-09-17T18:00:00+08:00");
  assert.equal(remainingSeconds("2026-09-17T18:00:01+08:00", now), 1);
  assert.equal(remainingSeconds("2026-09-17T18:00:00+08:00", now), 0);
  assert.equal(remainingSeconds("bad value", now), 0);
});
