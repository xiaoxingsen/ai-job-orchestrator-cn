import {
  PersistentCommandExecutor,
  type CommandStorage,
} from "../src/commands/persistent";


class MemoryStorage implements CommandStorage {
  readonly values = new Map<string, unknown>();

  async get<T>(key: string): Promise<T | undefined> {
    return this.values.get(key) as T | undefined;
  }

  async set(key: string, value: unknown): Promise<void> {
    this.values.set(key, value);
  }
}


it("persists completed command results across extension worker restarts", async () => {
  const storage = new MemoryStorage();
  let calls = 0;
  const firstWorker = new PersistentCommandExecutor(storage);
  const first = await firstWorker.execute("cmd-1", async () => {
    calls += 1;
    return { status: "submitted", remoteId: "chat-1" };
  });

  const restartedWorker = new PersistentCommandExecutor(storage);
  const second = await restartedWorker.execute("cmd-1", async () => {
    calls += 1;
    return { status: "submitted", remoteId: "chat-2" };
  });

  expect(first).toEqual(second);
  expect(calls).toBe(1);
});


it("does not replay a command left pending by a worker crash", async () => {
  const storage = new MemoryStorage();
  await storage.set("job-command:cmd-pending", { state: "pending" });
  let calls = 0;

  const result = await new PersistentCommandExecutor(storage).execute("cmd-pending", async () => {
    calls += 1;
    return { status: "submitted" };
  });

  expect(result).toEqual({
    status: "unknown",
    recovery: "observe_result",
    commandId: "cmd-pending",
  });
  expect(calls).toBe(0);
});

