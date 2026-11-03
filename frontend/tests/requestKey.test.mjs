import { readFileSync } from "node:fs";
import { webcrypto } from "node:crypto";
import { runInNewContext } from "node:vm";
import test from "node:test";
import assert from "node:assert/strict";
import ts from "typescript";

const source = readFileSync(new URL("../src/utils/requestKey.ts", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
function load(crypto) {
  const context = { exports: {}, crypto, Uint8Array };
  runInNewContext(code, context);
  return context.exports.createRequestKey;
}

test("uses native randomUUID with its Crypto receiver", () => {
  const expected = "12345678-1234-4234-8234-123456789abc";
  const crypto = {
    randomUUID() { assert.equal(this, crypto); return expected; },
    getRandomValues() { assert.fail("native UUID should be used"); },
  };
  assert.equal(load(crypto)(), expected);
});

test("HTTP-compatible fallback preserves random bytes and sets UUID version and variant", () => {
  for (const fill of [0x00, 0xff]) {
    const crypto = {
      getRandomValues(bytes) {
        assert.equal(this, crypto);
        assert.equal(bytes.length, 16);
        return bytes.fill(fill);
      },
    };
    assert.equal(load(crypto)(), fill === 0
      ? "00000000-0000-4000-8000-000000000000"
      : "ffffffff-ffff-4fff-bfff-ffffffffffff");
  }
});

test("missing randomUUID generates distinct backend-compatible request keys", () => {
  const createRequestKey = load({ getRandomValues: bytes => webcrypto.getRandomValues(bytes) });
  const keys = Array.from({ length: 1000 }, () => createRequestKey());
  assert.equal(new Set(keys).size, keys.length);
  for (const key of keys) {
    assert.match(key, uuidV4);
    assert.match(key, /^[A-Za-z0-9_.:-]{8,64}$/);
  }
});

test("non-callable randomUUID also uses the secure random byte fallback", () => {
  assert.match(load({ randomUUID: null, getRandomValues: bytes => webcrypto.getRandomValues(bytes) })(), uuidV4);
});

test("unsupported browsers receive an actionable error rather than a weak random key", () => {
  for (const crypto of [undefined, {}, { getRandomValues: null }]) {
    assert.throws(load(crypto), /当前浏览器不支持安全随机数/);
  }
});

test("a failed secure random source is not replaced by an unsafe generator", () => {
  assert.throws(load({ getRandomValues() { throw new Error("random source unavailable"); } }), /random source unavailable/);
});
