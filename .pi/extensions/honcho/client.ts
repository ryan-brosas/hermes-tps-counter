import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';
import type { Peer, Session } from '@honcho-ai/sdk';
import { Honcho } from '@honcho-ai/sdk';
import type { HonchoExtensionConfig } from './config.js';
import { deriveSessionKey } from './session-key.js';

export interface HonchoHandles {
  honcho: Honcho;
  userPeer: Peer;
  aiPeer: Peer;
  session: Session;
  sessionKey: string;
  config: HonchoExtensionConfig;
}

let cachedHandles: HonchoHandles | null = null;

export const getHandles = (): HonchoHandles | null => cachedHandles;

export const clearHandles = (): void => {
  cachedHandles = null;
};

/**
 * Bootstrap the Honcho client and resolve all handles.
 * Throws on failure — callers must catch and degrade gracefully.
 */
export const bootstrap = async (
  pi: ExtensionAPI,
  config: HonchoExtensionConfig,
  cwd: string,
): Promise<HonchoHandles> => {
  const honcho = new Honcho({
    apiKey: config.apiKey,
    baseURL: config.baseURL,
    workspaceId: config.workspaceId,
    timeout: config.httpTimeoutMs,
    maxRetries: config.httpMaxRetries,
  });

  const sessionKey = await deriveSessionKey(pi, cwd, config.sessionStrategy);

  const [userPeer, aiPeer, session] = await Promise.all([
    honcho.peer(config.userPeerId),
    honcho.peer(config.aiPeerId),
    honcho.session(sessionKey),
  ]);

  await session.addPeers([userPeer, aiPeer]);

  if (config.observationMode === 'selective') {
    try {
      await session.setPeerConfiguration(aiPeer, { observeOthers: false });
    } catch (err) {
      // Non-fatal: default observation will apply
      console.debug('honcho: setPeerConfiguration failed (non-fatal):', err instanceof Error ? err.message : err);
    }
  }

  try {
    await session.setConfiguration({
      reasoning: { enabled: true },
      peerCard: { use: true, create: true },
      summary: {
        enabled: true,
        messagesPerShortSummary: 10,
        messagesPerLongSummary: 40,
      },
      dream: { enabled: true },
    });
  } catch (err) {
    // Non-fatal: session will use workspace/global defaults
    console.debug('honcho: session.setConfiguration failed (non-fatal):', err instanceof Error ? err.message : err);
  }

  cachedHandles = { honcho, userPeer, aiPeer, session, sessionKey, config };
  return cachedHandles;
};
