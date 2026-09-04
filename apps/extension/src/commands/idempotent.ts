export class IdempotentCommandExecutor {
  private readonly commands = new Map<string, Promise<unknown>>();

  execute<T>(commandId: string, operation: () => Promise<T>): Promise<T> {
    if (!commandId.trim()) throw new Error("command_id is required");
    const existing = this.commands.get(commandId);
    if (existing) return existing as Promise<T>;
    const result = operation();
    this.commands.set(commandId, result);
    return result;
  }
}

