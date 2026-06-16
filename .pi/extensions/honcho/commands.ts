import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';
import { bootstrap, clearHandles, getHandles } from './client.js';
import {
  getConfigPath,
  getSessionStrategyLabel,
  normalizeSessionStrategy,
  readConfigFile,
  resolveConfig,
} from './config.js';
import { getCachedMemory } from './memory.js';

const MASKED_KEY = '••••••••';
const JSON_INDENT = 2;

const errorMessage = (err: unknown): string => {
  if (err instanceof Error) return err.message;
  return String(err);
};

const enabledLabel = (flag: boolean): string => (flag ? '✅ yes' : '❌ no');

const memoryCacheLabel = (cached: string | null): string =>
  cached ? `${cached.length} chars` : 'empty';

const buildStatusLines = (
  config: Awaited<ReturnType<typeof resolveConfig>>,
  handles: ReturnType<typeof getHandles>,
  cached: string | null,
): string[] => {
  const lines: string[] = [];
  lines.push(`Enabled:      ${enabledLabel(config.enabled)}`);
  lines.push(`Connected:    ${enabledLabel(Boolean(handles))}`);
  lines.push(`Workspace:    ${config.workspaceId}`);
  lines.push(`User peer:    ${config.userPeerId}`);
  lines.push(`AI peer:      ${config.aiPeerId}`);
  lines.push(`Session mode: ${getSessionStrategyLabel(config.sessionStrategy)}`);
  lines.push(`Context toks: ${config.contextTokens}`);
  lines.push(`Msg max len:  ${config.maxMessageLength}`);
  lines.push(`Search limit: ${config.searchLimit}`);
  lines.push(`Tool preview: ${config.toolPreviewLength}`);
  if (handles) lines.push(`Session key:  ${handles.sessionKey}`);
  lines.push(`Memory cache: ${memoryCacheLabel(cached)}`);
  if (config.baseURL) lines.push(`Endpoint:     ${config.baseURL}`);
  return lines;
};

const buildConfigFile = (
  fileContents: Record<string, unknown>,
  apiKey: string | null | undefined,
  peerName: string | null | undefined,
  endpoint: string | null | undefined,
  sessionStrategy: string | null | undefined,
  existing: Awaited<ReturnType<typeof resolveConfig>>,
): Record<string, unknown> => {
  const updated = { ...fileContents };
  if (apiKey && apiKey !== MASKED_KEY) updated.apiKey = apiKey;
  if (peerName) updated.peerName = peerName;

  const hosts = (
    typeof updated.hosts === 'object' && updated.hosts !== null ? updated.hosts : {}
  ) as Record<string, unknown>;
  const piHost = (typeof hosts.pi === 'object' && hosts.pi !== null ? hosts.pi : {}) as Record<
    string,
    unknown
  >;
  piHost.sessionStrategy = normalizeSessionStrategy(sessionStrategy || existing.sessionStrategy);
  if (endpoint) piHost.endpoint = endpoint;
  hosts.pi = piHost;
  updated.hosts = hosts;
  return updated;
};

const testConnection = async (pi: ExtensionAPI, ctx: { ui: any; cwd: string }): Promise<void> => {
  ctx.ui.notify('Testing connection...', 'info');
  try {
    clearHandles();
    const newConfig = await resolveConfig();
    await bootstrap(pi, newConfig, ctx.cwd);
    ctx.ui.notify('✅ Connected to Honcho!', 'info');
    ctx.ui.setStatus('honcho', ctx.ui.theme.fg('success', '🧠 Connected'));
  } catch (err) {
    ctx.ui.notify(`❌ Connection failed: ${errorMessage(err)}`, 'error');
    ctx.ui.setStatus('honcho', ctx.ui.theme.fg('error', '🧠 Error'));
  }
};

export const registerCommands = (pi: ExtensionAPI): void => {
  // --- /honcho-status ---
  pi.registerCommand('honcho-status', {
    description: 'Show Honcho memory connection status',
    handler: async (_args, ctx) => {
      const config = await resolveConfig();
      const handles = getHandles();
      const cached = getCachedMemory();
      const lines = buildStatusLines(config, handles, cached);
      ctx.ui.notify(lines.join('\n'), 'info');
    },
  });

  // --- /honcho-setup ---
  pi.registerCommand('honcho-setup', {
    description: 'Configure Honcho memory integration',
    handler: async (_args, ctx) => {
      const existing = await resolveConfig();

      const defaultKey = existing.apiKey ? MASKED_KEY : 'hch-...';
      const apiKey = await ctx.ui.input('Honcho API key:', defaultKey);
      if (!apiKey || apiKey === MASKED_KEY) {
        if (!existing.apiKey) {
          ctx.ui.notify('API key is required.', 'error');
          return;
        }
      }

      const peerName = await ctx.ui.input('Your peer name:', existing.userPeerId);
      const endpoint = await ctx.ui.input(
        'Honcho endpoint (leave blank for default):',
        existing.baseURL || '',
      );
      const sessionStrategyInput = await ctx.ui.input(
        'Session strategy (repo/git-branch/directory):',
        existing.sessionStrategy,
      );
      const sessionStrategy = normalizeSessionStrategy(
        sessionStrategyInput || existing.sessionStrategy,
      );

      if (
        sessionStrategyInput &&
        sessionStrategyInput !== sessionStrategy &&
        sessionStrategyInput !== existing.sessionStrategy
      ) {
        ctx.ui.notify(
          `Unknown session strategy '${sessionStrategyInput}'. Using ${sessionStrategy}.`,
          'warning',
        );
      }

      const configPath = getConfigPath();
      const fileContents = ((await readConfigFile()) ?? {}) as Record<string, unknown>;
      const updated = buildConfigFile(
        fileContents,
        apiKey,
        peerName,
        endpoint,
        sessionStrategy,
        existing,
      );

      await mkdir(dirname(configPath), { recursive: true });
      await writeFile(configPath, `${JSON.stringify(updated, null, JSON_INDENT)}\n`, 'utf-8');

      ctx.ui.notify(`Config saved to ${configPath}`, 'info');
      await testConnection(pi, ctx);
    },
  });
};
