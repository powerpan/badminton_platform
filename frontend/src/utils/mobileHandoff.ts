export function createDeviceSecret(): string {
  if (!globalThis.crypto?.getRandomValues) throw new Error('当前浏览器不支持安全授权，请更新浏览器');
  return Array.from(globalThis.crypto.getRandomValues(new Uint8Array(32)), byte => byte.toString(16).padStart(2, '0')).join('');
}
export function pickupPath(id: number): string {
  if (!Number.isSafeInteger(id) || id <= 0) throw new Error('订单编号无效');
  return `/shop/orders/${id}/pickup`;
}
export function terminalHandoff(status: string): boolean {
  return ['consumed', 'denied', 'failed'].includes(status);
}
export function currentBrowserAccount(): number | null {
  try {
    if (!localStorage.getItem('bf_token')) return null;
    const id = JSON.parse(localStorage.getItem('bf_user') || 'null')?.id;
    return Number.isSafeInteger(id) && id > 0 ? id : null;
  } catch { return null; }
}
