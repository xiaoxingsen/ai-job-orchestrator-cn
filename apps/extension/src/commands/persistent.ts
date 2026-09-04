export interface CommandStorage {
  get<T>(key: string): Promise<T | undefined>;
  set(key: string, value: unknown): Promise<void>;
}

interface PendingCommand {
  state: "pending";
}

interface CompletedCommand<T> {
  state: "completed";
  result: T;
}

type StoredCommand<T> = PendingCommand | CompletedCommand<T>;

export interface ObserveRecovery {
  status: "unknown";
  recovery: "observe_result";
  commandId: string;
}


export class PersistentCommandExecutor {
  private readonly inflight = new Map<string, Promise<unknown>>();

  constructor(private readonly storage: CommandStorage) {}

  execute<T>(commandId: string, operation: () => Promise<T>): Promise<T | ObserveRecovery> {
    if (!commandId.trim()) throw new Error("command_id is required");
    const existing = this.inflight.get(commandId);
    if (existing) return existing as Promise<T | ObserveRecovery>;
    const promise = this.executeStored(commandId, operation);
    this.inflight.set(commandId, promise);
    return promise;
  }

  private async executeStored<T>(
    commandId: string,
    operation: () => Promise<T>,
  ): Promise<T | ObserveRecovery> {
    const key = `job-command:${commandId}`;
    const stored = await this.storage.get<StoredCommand<T>>(key);
    if (stored?.state === "completed") return stored.result;
    if (stored?.state === "pending") {
      return { status: "unknown", recovery: "observe_result", commandId };
    }
    await this.storage.set(key, { state: "pending" } satisfies PendingCommand);
    const result = await operation();
    await this.storage.set(key, { state: "completed", result } satisfies CompletedCommand<T>);
    return result;
  }
}


export class ChromeCommandStorage implements CommandStorage {
  async get<T>(key: string): Promise<T | undefined> {
    const values = await chrome.storage.local.get(key);
    return values[key] as T | undefined;
  }

  async set(key: string, value: unknown): Promise<void> {
    await chrome.storage.local.set({ [key]: value });
  }
}

