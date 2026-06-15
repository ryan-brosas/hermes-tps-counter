import type { HonchoHandles } from './client.js';

const PERSISTENT_MEMORY_HEADER = '[Persistent memory]';
const USER_PROFILE_LABEL = 'User profile';
const PROJECT_SUMMARY_LABEL = 'Project summary';
const PEER_CARD_LABEL = 'Peer card';

interface CachedMemoryParts {
  userProfile: string | null;
  projectSummary: string | null;
  peerCard: string[] | null;
  shortSummary: string | null;
  longSummary: string | null;
  messageCount: number;
  generatedAt: number;
  accessCount: number;
  lastAccessedAt: number;
}

interface CachedHonchoContext {
  peerRepresentation?: string | null;
  summary?: { content?: string | null } | null;
  peerCard?: string[] | null;
}

const EMPTY_MEMORY: CachedMemoryParts = {
  userProfile: null,
  projectSummary: null,
  peerCard: null,
  shortSummary: null,
  longSummary: null,
  messageCount: 0,
  generatedAt: 0,
  accessCount: 0,
  lastAccessedAt: 0,
};

let cachedMemory = EMPTY_MEMORY;

const buildSection = (label: string, value: string | null): string | null => {
  if (!value) return null;
  return `${PERSISTENT_MEMORY_HEADER}\n${label}:\n${value}`;
};

const normalizeMemoryText = (value?: string | null): string | null => {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return trimmed;
};

export const buildCachedMemoryParts = (context: CachedHonchoContext): CachedMemoryParts => ({
  userProfile: normalizeMemoryText(context.peerRepresentation),
  projectSummary: normalizeMemoryText(context.summary?.content),
  peerCard:
    Array.isArray(context.peerCard) && context.peerCard.length > 0 ? context.peerCard : null,
  shortSummary: null,
  longSummary: null,
  messageCount: 0,
  generatedAt: Date.now(),
  accessCount: 0,
  lastAccessedAt: Date.now(),
});

const buildCombinedMemoryText = (parts: CachedMemoryParts): string | null => {
  const sections = [
    parts.userProfile ? `${USER_PROFILE_LABEL}:\n${parts.userProfile}` : null,
    parts.projectSummary ? `${PROJECT_SUMMARY_LABEL}:\n${parts.projectSummary}` : null,
    parts.peerCard && parts.peerCard.length > 0
      ? `${PEER_CARD_LABEL}:\n${parts.peerCard.map((c) => `• ${c}`).join('\n')}`
      : null,
  ].filter((section): section is string => section !== null);

  if (sections.length === 0) return null;
  return `${PERSISTENT_MEMORY_HEADER}\n${sections.join('\n\n')}`;
};

export const buildMemoryText = (context: CachedHonchoContext): string | null =>
  buildCombinedMemoryText(buildCachedMemoryParts(context));

export const getCachedMemory = (): string | null => {
  cachedMemory.accessCount++;
  cachedMemory.lastAccessedAt = Date.now();
  return buildCombinedMemoryText(cachedMemory);
};

export const clearCachedMemory = (): void => {
  cachedMemory = EMPTY_MEMORY;
};

export const getAttractorStrength = (): {
  strength: number;
  accessCount: number;
  lastAccessedAt: number;
} => {
  const ageMs = Date.now() - cachedMemory.lastAccessedAt;
  const ageHours = ageMs / (1000 * 60 * 60);
  const recency = Math.max(0.1, 1.0 - (ageHours / 24) * 0.9);
  const frequency = 1 + Math.log2(Math.max(1, cachedMemory.accessCount));
  const strength = recency * frequency;
  return {
    strength: Math.round(strength * 100) / 100,
    accessCount: cachedMemory.accessCount,
    lastAccessedAt: cachedMemory.lastAccessedAt,
  };
};

export const isAutosyncEnabled = (): boolean => {
  const save = process.env.HONCHO_SAVE_MESSAGES;
  const override = process.env.PI_ALLOW_HONCHO_AUTOSYNC_ENV_OVERRIDE;
  return save === 'true' && override === 'true';
};

let pendingSave: Promise<void> = Promise.resolve();

const enqueue = (fn: () => Promise<void>): Promise<void> => {
  pendingSave = pendingSave.then(fn, () => fn());
  return pendingSave;
};

export const flushPending = (): Promise<void> => pendingSave;

export const refreshMemoryCache = async (handles: HonchoHandles): Promise<void> => {
  try {
    const [ctx, summaries] = await Promise.all([
      handles.session.context({
        summary: true,
        peerPerspective: handles.aiPeer,
        peerTarget: handles.userPeer,
        tokens: handles.config.contextTokens,
        limitToSession: true,
      }),
      handles.session.summaries().catch(() => null),
    ]);

    cachedMemory = buildCachedMemoryParts(ctx);

    if (summaries) {
      cachedMemory.shortSummary = summaries.shortSummary?.content ?? null;
      cachedMemory.longSummary = summaries.longSummary?.content ?? null;
    }
  } catch (err) {
    // Keep stale cache on failure rather than clearing it
    console.debug('honcho: refreshMemoryCache failed (stale cache retained):', err instanceof Error ? err.message : err);
  }
};

interface ContentBlock {
  type?: string;
  text?: string;
}

const isTextBlock = (block: ContentBlock): block is ContentBlock & { text: string } =>
  block.type === 'text' && typeof block.text === 'string';

const extractText = (content: unknown): string => {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return (content as ContentBlock[])
    .filter(isTextBlock)
    .map((block) => block.text)
    .join('\n')
    .trim();
};

interface ConversationAgentMessage {
  role?: string;
  content?: unknown;
}

export const extractConversationalPairs = (
  messages: ConversationAgentMessage[],
  maxMessageLength: number,
): { role: 'user' | 'assistant'; text: string }[] => {
  const pairs: { role: 'user' | 'assistant'; text: string }[] = [];
  for (const msg of messages) {
    if (msg.role !== 'user' && msg.role !== 'assistant') continue;
    const text = extractText(msg.content);
    if (!text || text.length > maxMessageLength) continue;
    pairs.push({ role: msg.role, text });
  }
  return pairs;
};

export const saveMessages = (
  handles: HonchoHandles,
  messages: ConversationAgentMessage[],
): Promise<boolean> => {
  const pairs = extractConversationalPairs(messages, handles.config.maxMessageLength);
  if (pairs.length === 0) return Promise.resolve(true);

  return enqueue(async () => {
    try {
      const honchoMessages = pairs.map((pair) => {
        if (pair.role === 'user') return handles.userPeer.message(pair.text);
        return handles.aiPeer.message(pair.text);
      });
      await handles.session.addMessages(honchoMessages);
      await refreshMemoryCache(handles);
      return true;
    } catch (err) {
      console.debug('honcho: saveMessages failed:', err instanceof Error ? err.message : err);
      return false;
    }
  });
};
