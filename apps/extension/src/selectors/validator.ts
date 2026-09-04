import type { SelectorBundle } from "../adapters/types";


const TOP_LEVEL_KEYS = new Set(["schemaVersion", "selectorVersion", "platform", "selectors"]);
const PLATFORMS = new Set(["boss", "liepin", "zhilian"]);


export function validateSelectorBundle(input: unknown): SelectorBundle {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new Error("selector bundle must be a data-only object");
  }
  const record = input as Record<string, unknown>;
  if (Object.keys(record).some((key) => !TOP_LEVEL_KEYS.has(key))) {
    throw new Error("selector bundle must be data-only; executable or unknown fields are forbidden");
  }
  if (record.schemaVersion !== 1) throw new Error("unsupported selector schema version");
  if (typeof record.selectorVersion !== "string" || !record.selectorVersion) {
    throw new Error("selectorVersion is required");
  }
  if (typeof record.platform !== "string" || !PLATFORMS.has(record.platform)) {
    throw new Error("unsupported selector platform");
  }
  if (!record.selectors || typeof record.selectors !== "object" || Array.isArray(record.selectors)) {
    throw new Error("selectors must be a data-only object");
  }
  for (const [name, selector] of Object.entries(record.selectors)) {
    if (!name || typeof selector !== "string" || !selector.trim()) {
      throw new Error("every selector must be a non-empty string");
    }
  }
  return record as unknown as SelectorBundle;
}

