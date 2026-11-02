// HA conversation IDs stay on the server, scoped to an authenticated browser tab.
export class Conversations {
  constructor(ttl = 5 * 60000) { this.ttl = ttl; this.items = new Map(); }
  get(key, now = Date.now()) {
    const item = this.items.get(key);
    if (item && item.expires > now) return item.id;
    this.items.delete(key);
  }
  set(key, id, now = Date.now()) {
    this.prune(now);
    this.items.set(key, { id, expires: now + this.ttl });
  }
  prune(now = Date.now()) {
    for (const [key, item] of this.items) if (item.expires <= now) this.items.delete(key);
  }
}
