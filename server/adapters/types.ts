import type {
  AgentRunSettings,
  CompactResult,
  ContextUsage,
  ScheduledTask,
  ScheduledTaskInput,
  SessionMetadata,
  TaskMessage,
} from '../../shared/types.js';

export type { AgentRunSettings, ContextUsage };

export interface AgentRunOptions {
  systemMessage?: string;
  settings?: AgentRunSettings;
  task?: {
    id: string;
    title?: string | null;
  };
}

export interface StreamEvent {
  type: 'text_delta' | 'thinking_delta' | 'tool_progress' | 'done' | 'error';
  content?: string;
  error?: string;
  code?: string;
  sessionId?: string;
  tool?: string;
  status?: 'running' | 'completed' | 'error';
  duration?: number;
  label?: string;
  context?: ContextUsage | null;
}

export interface AgentAdapter {
  chat(
    sessionId: string,
    message: string,
    options?: AgentRunOptions,
  ): Promise<{ text: string; sessionId: string }>;

  chatStream(
    sessionId: string,
    message: string,
    options?: AgentRunOptions,
  ): AsyncIterable<StreamEvent>;

  healthCheck(): Promise<boolean>;

  getMessages(sessionId: string, taskId: string): Promise<TaskMessage[]>;

  getSessionMetadata(sessionId: string): Promise<SessionMetadata | null>;

  judgeCompletion(
    taskTitle: string,
    taskDescription: string | null,
    responseText: string,
  ): Promise<{ done: boolean; reason: string }>;

  generateTitle(description: string): Promise<{ title: string }>;

  compressSession(
    sessionId: string,
    options?: {
      focusTopic?: string | null;
      currentTokens?: number | null;
      systemMessage?: string;
      settings?: AgentRunSettings;
    },
  ): Promise<CompactResult>;

  listScheduledTasks(includeDisabled?: boolean): Promise<ScheduledTask[]>;

  getScheduledTask(scheduledTaskId: string): Promise<ScheduledTask | null>;

  createScheduledTask(input: ScheduledTaskInput): Promise<ScheduledTask>;

  updateScheduledTask(scheduledTaskId: string, updates: Partial<ScheduledTaskInput>): Promise<ScheduledTask | null>;

  pauseScheduledTask(scheduledTaskId: string, reason?: string): Promise<ScheduledTask | null>;

  resumeScheduledTask(scheduledTaskId: string): Promise<ScheduledTask | null>;

  runScheduledTask(scheduledTaskId: string): Promise<ScheduledTask | null>;

  removeScheduledTask(scheduledTaskId: string): Promise<boolean>;

  tickScheduledTasks(): Promise<number>;
}
