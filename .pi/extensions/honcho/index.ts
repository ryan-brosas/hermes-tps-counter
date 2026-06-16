import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';
import { bootstrap, clearHandles, getHandles } from './client.js';
import { registerCommands } from './commands.js';
import { resolveConfig } from './config.js';
import {
  clearCachedMemory,
  flushPending,
  getCachedMemory,
  isAutosyncEnabled,
  refreshMemoryCache,
  saveMessages,
} from './memory.js';
import { registerTools } from './tools.js';

interface StatusContext {
  ui: {
    setStatus: (id: string, text: string) => void;
    theme: any;
  };
}

const setStatus = (
  ctx: StatusContext,
  state: 'off' | 'connected' | 'syncing' | 'offline' | 'error',
): void => {
  const { theme } = ctx.ui;
  const labels: Record<string, string> = {
    off: theme.fg('dim', '🧠 Honcho off'),
    connected: theme.fg('success', '🧠 Connected'),
    syncing: theme.fg('warning', '🧠 Syncing'),
    offline: theme.fg('dim', '🧠 Offline'),
    error: theme.fg('error', '🧠 Error'),
  };
  ctx.ui.setStatus('honcho', labels[state]);
};

export default function honcho(pi: ExtensionAPI): void {
  let initializing: Promise<void> | null = null;
  let initGeneration = 0;

  // Register tools & commands (always, so they can show helpful errors if not connected)
  registerTools(pi);
  registerCommands(pi);

  const backgroundInit = (ctx: { ui: any; cwd: string }): void => {
    const gen = ++initGeneration;
    initializing = (async () => {
      try {
        const config = await resolveConfig();
        if (!config.enabled || !config.apiKey) {
          if (gen === initGeneration) setStatus(ctx, 'off');
          return;
        }

        const handles = await bootstrap(pi, config, ctx.cwd);

        if (gen !== initGeneration) return;

        setStatus(ctx, 'connected');

        await refreshMemoryCache(handles);
      } catch (err) {
        console.debug('honcho: background init failed:', err instanceof Error ? err.message : err);
        if (gen === initGeneration) setStatus(ctx, 'offline');
      } finally {
        if (gen === initGeneration) initializing = null;
      }
    })();
  };

  // --- Lifecycle events ---

  pi.on('session_start', (_event, ctx) => {
    clearHandles();
    clearCachedMemory();
    backgroundInit(ctx);
  });

  pi.on('session_switch', async (_event, ctx) => {
    await flushPending();
    clearHandles();
    clearCachedMemory();
    backgroundInit(ctx);
  });

  pi.on('session_fork', async (_event, ctx) => {
    await flushPending();
    clearHandles();
    clearCachedMemory();
    backgroundInit(ctx);
  });

  // --- Prompt path: inject cached memory + prompt-targeted context ---

  pi.on('before_agent_start', async (event) => {
    if (initializing) {
      await initializing;
    }

    const parts: string[] = [];

    const baseline = getCachedMemory();
    if (baseline) {
      parts.push(baseline);
    }

    // Prompt-targeted supplement: fetch relevant context for the user's question
    if (event.prompt && event.prompt.length > 10) {
      const handles = getHandles();
      if (handles) {
        try {
          const targeted = await Promise.race([
            handles.aiPeer.representation({
              target: handles.userPeer,
              searchQuery: event.prompt,
            }),
            new Promise<null>((_resolve, reject) =>
              setTimeout(() => reject(new Error('timeout')), 2000),
            ),
          ]);
          if (targeted) {
            parts.push(`[Relevant context]\n${targeted}`);
          }
        } catch (err) {
          // Timeout or error — baseline is sufficient
          console.debug('honcho: targeted context fetch failed:', err instanceof Error ? err.message : err);
        }
      }
    }

    if (parts.length === 0) return;

    return {
      systemPrompt: `${event.systemPrompt}\n\n${parts.join('\n\n')}`,
    };
  });

  // --- Post-response: save messages + refresh cache ---

  pi.on('agent_end', async (event, ctx) => {
    const handles = getHandles();
    if (!handles) return;

    if (!isAutosyncEnabled()) {
      setStatus(ctx, 'connected');
      return;
    }

    setStatus(ctx, 'syncing');

    saveMessages(handles, event.messages as any[])
      .then((success) => setStatus(ctx, success ? 'connected' : 'offline'))
      .catch(() => setStatus(ctx, 'offline'));
  });

  // --- Write-before-compaction: save compacted messages to Honcho ---

  pi.on('session_before_compact', async (event) => {
    await flushPending();

    const handles = getHandles();
    if (!handles || !isAutosyncEnabled()) return;

    const messages = event.preparation?.messagesToSummarize;
    if (messages && messages.length > 0) {
      await saveMessages(handles, messages as any[]);
      await flushPending();
    }
  });

  pi.on('session_before_switch', async () => {
    await flushPending();
  });

  pi.on('session_before_fork', async () => {
    await flushPending();
  });

  pi.on('session_shutdown', async () => {
    await flushPending();
  });
}
