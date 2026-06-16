import { StringEnum } from '@earendil-works/pi-ai';
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';
import { Type } from '@sinclair/typebox';
import type { HonchoHandles } from './client.js';
import { getHandles } from './client.js';
import { getAttractorStrength } from './memory.js';

const ensureConnected = (): HonchoHandles => {
  const handles = getHandles();
  if (!handles) {
    throw new Error('Honcho is not connected. Run /honcho-setup to configure.');
  }
  return handles;
};

const formatResults = (
  results: { peerId: string; content: string }[],
  previewLength: number,
): string =>
  results
    .map((mem, idx) => `${idx + 1}. [${mem.peerId}] ${mem.content.slice(0, previewLength)}`)
    .join('\n\n');

export const registerTools = (pi: ExtensionAPI): void => {
  // --- honcho_search ---
  pi.registerTool({
    name: 'honcho_search',
    label: 'Honcho Search',
    description:
      'Search persistent memory for prior conversations, decisions, and historical context',
    promptSnippet:
      'Search persistent memory for prior conversations, decisions, and historical context',
    promptGuidelines: [
      'Use honcho_search for factual recall of past conversations or decisions.',
      'Do not save secrets, tokens, or transient debugging details to Honcho.',
    ],
    parameters: Type.Object({
      query: Type.String({ description: 'Search query' }),
      scope: Type.Optional(
        StringEnum(['session', 'workspace'] as const, {
          description:
            'Search scope: session (current session only) or workspace (cross-session). Default: session.',
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();

      if (params.scope === 'workspace') {
        const results = await handles.honcho.search(params.query, {
          limit: handles.config.searchLimit,
        });
        if (results.length === 0) {
          return {
            content: [{ type: 'text' as const, text: 'No relevant memory found across workspace.' }],
            details: { scope: 'workspace' },
          };
        }
        return {
          content: [
            {
              type: 'text' as const,
              text: results
                .map((m) => `[${m.peerId}] ${m.content.slice(0, handles.config.toolPreviewLength)}`)
                .join('\n\n'),
            },
          ],
          details: { scope: 'workspace', count: results.length },
        };
      }

      const results = await handles.session.search(params.query, {
        limit: handles.config.searchLimit,
      });
      if (results.length === 0) {
        return {
          content: [{ type: 'text' as const, text: 'No relevant memory found for this query.' }],
          details: {},
        };
      }
      return {
        content: [{ type: 'text' as const, text: formatResults(results, handles.config.toolPreviewLength) }],
        details: { count: results.length },
      };
    },
  });

  // --- honcho_chat ---
  pi.registerTool({
    name: 'honcho_chat',
    label: 'Honcho Chat',
    description:
      'Ask Honcho to reason over memory — for deeper questions about user preferences, patterns, and history',
    promptSnippet:
      'Reason over persistent memory for deeper questions about user preferences and patterns',
    promptGuidelines: ['Use honcho_chat for reasoning over memory, not simple lookup.'],
    parameters: Type.Object({
      query: Type.String({ description: 'Question to reason over' }),
      reasoningLevel: Type.Optional(
        StringEnum(['minimal', 'low', 'medium', 'high', 'max'] as const),
      ),
      stream: Type.Optional(
        Type.Boolean({ description: 'Stream the response incrementally (default: false)' }),
      ),
    }),
    async execute(_toolCallId, params, _signal, onUpdate, _ctx) {
      const handles = ensureConnected();

      const REASONING_LEVELS = ['minimal', 'low', 'medium', 'high', 'max'] as const;
      const requested = params.reasoningLevel ?? handles.config.reasoningLevel;
      const capIndex = REASONING_LEVELS.indexOf(
        handles.config.reasoningLevelCap as (typeof REASONING_LEVELS)[number],
      );
      const requestedIndex = REASONING_LEVELS.indexOf(
        requested as (typeof REASONING_LEVELS)[number],
      );
      const effectiveLevel =
        requestedIndex > capIndex ? handles.config.reasoningLevelCap : requested;

      const chatOptions = {
        target: handles.userPeer,
        session: handles.session,
        reasoningLevel: effectiveLevel,
      };

      if (params.stream) {
        try {
          const stream = await handles.aiPeer.chatStream(params.query, chatOptions);
          let full = '';
          for await (const chunk of stream) {
            full += chunk;
            onUpdate?.({
              content: [{ type: 'text' as const, text: full }],
              details: { streaming: true },
            });
          }
          return {
            content: [{ type: 'text' as const, text: full }],
            details: { streamed: true },
          };
        } catch (err) {
          // Fall through to non-streaming
          console.debug('honcho: chatStream failed, falling back to non-streaming:', err instanceof Error ? err.message : err);
        }
      }

      const result = await handles.aiPeer.chat(params.query, chatOptions);
      if (result === null) {
        return {
          content: [{ type: 'text' as const, text: 'No relevant memory found for this query.' }],
          details: {},
        };
      }
      return {
        content: [{ type: 'text' as const, text: result }],
        details: {},
      };
    },
  });

  // --- honcho_remember ---
  pi.registerTool({
    name: 'honcho_remember',
    label: 'Honcho Remember',
    description: 'Write an explicit durable fact, preference, or decision to persistent memory',
    promptSnippet: 'Save a durable fact, preference, or decision to persistent memory',
    promptGuidelines: [
      'Use honcho_remember only for durable preferences, conventions, or decisions worth persisting.',
      'Do not save secrets, tokens, or transient debugging details to Honcho.',
    ],
    parameters: Type.Object({
      content: Type.String({
        description: 'The fact, preference, or decision to remember',
      }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();
      await handles.aiPeer.conclusionsOf(handles.userPeer).create({
        content: params.content,
        sessionId: handles.session,
      });
      return {
        content: [{ type: 'text' as const, text: `Remembered: ${params.content}` }],
        details: {},
      };
    },
  });

  // --- honcho_conclusions ---
  pi.registerTool({
    name: 'honcho_conclusions',
    label: 'Honcho Conclusions',
    description:
      'Query or list persistent conclusions about a peer. Faster than honcho_chat (no LLM call).',
    promptSnippet: 'Query or list persistent conclusions about a peer for targeted fact retrieval',
    promptGuidelines: [
      "Use honcho_conclusions for fast, targeted fact retrieval when you don't need synthesis.",
      'Prefer over honcho_chat when you need raw conclusions, not reasoned summaries.',
    ],
    parameters: Type.Object({
      query: Type.Optional(Type.String({ description: 'Semantic search query for conclusions' })),
      target: Type.Optional(Type.String({ description: 'Target peer ID (default: user peer)' })),
      limit: Type.Optional(Type.Number({ description: 'Max results (default: 10)' })),
      list: Type.Optional(Type.Boolean({ description: 'List all conclusions instead of searching' })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();
      const target = params.target ?? handles.userPeer.id;
      const scope = handles.aiPeer.conclusionsOf(target);

      try {
        if (params.list) {
          const page = await scope.list({ size: params.limit ?? 20 });
          const items = page.items.map((c) => `[${c.id.slice(0, 8)}] ${c.content}`).join('\n');
          return {
            content: [{ type: 'text' as const, text: items || 'No conclusions found.' }],
            details: { count: page.items.length },
          };
        }
        if (params.query) {
          const results = await scope.query(params.query, params.limit ?? 10);
          const items = results.map((c) => `[${c.id.slice(0, 8)}] ${c.content}`).join('\n');
          return {
            content: [{ type: 'text' as const, text: items || 'No matching conclusions.' }],
            details: { count: results.length },
          };
        }
        return {
          content: [{ type: 'text' as const, text: 'Provide either query or list parameter.' }],
          details: {},
        };
      } catch {
        return {
          content: [{ type: 'text' as const, text: 'Failed to query conclusions.' }],
          details: {},
        };
      }
    },
  });

  // --- honcho_represent ---
  pi.registerTool({
    name: 'honcho_represent',
    label: 'Honcho Representation',
    description:
      'Get the computed representation of a peer — synthesized conclusions about what Honcho knows.',
    promptSnippet:
      'Get the computed representation of a peer — synthesized conclusions about identity and patterns',
    promptGuidelines: [
      'Use honcho_represent when you need a holistic view of what Honcho knows about a peer.',
    ],
    parameters: Type.Object({
      peer: Type.Optional(Type.String({ description: 'Peer ID (default: user peer)' })),
      sessionScoped: Type.Optional(
        Type.Boolean({ description: 'Scope representation to current session only' }),
      ),
      searchQuery: Type.Optional(
        Type.String({ description: 'Semantic search within representation' }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();
      try {
        if (params.sessionScoped) {
          const rep = await handles.session.representation(params.peer ?? handles.userPeer, {
            searchQuery: params.searchQuery,
          });
          return {
            content: [{ type: 'text' as const, text: rep || 'No representation available.' }],
            details: {},
          };
        }
        const rep = await handles.aiPeer.representation({
          target: params.peer ?? handles.userPeer,
          searchQuery: params.searchQuery,
        });
        return {
          content: [{ type: 'text' as const, text: rep || 'No representation available.' }],
          details: {},
        };
      } catch {
        return {
          content: [{ type: 'text' as const, text: 'Failed to get representation.' }],
          details: {},
        };
      }
    },
  });

  // --- honcho_status ---
  pi.registerTool({
    name: 'honcho_status',
    label: 'Honcho Status',
    description: 'Check if Honcho is connected.',
    promptSnippet: 'Check if Honcho persistent memory is connected',
    promptGuidelines: ['Use honcho_status for availability checks, not honcho_search "ping".'],
    parameters: Type.Object({
      detailed: Type.Optional(
        Type.Boolean({ description: 'Include queue status and processing info' }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const handles = getHandles();
      if (!handles) {
        return {
          content: [{ type: 'text' as const, text: 'Honcho: not connected' }],
          details: { connected: false },
        };
      }
      if (params.detailed) {
        try {
          const queue = await handles.session.queueStatus();
          const attractor = getAttractorStrength();
          return {
            content: [
              {
                type: 'text' as const,
                text: `Honcho: connected (workspace: ${handles.config.workspaceId}, session: ${handles.sessionKey})\nQueue: ${queue.status ?? 'unknown'}\nAttractor: strength=${attractor.strength} (accessed ${attractor.accessCount}x, last ${new Date(attractor.lastAccessedAt).toISOString()})`,
              },
            ],
            details: { connected: true, workspace: handles.config.workspaceId, session: handles.sessionKey, queueStatus: queue.status, attractor },
          };
        } catch (err) {
          // Fall through to basic status
          console.debug('honcho: detailed status fetch failed:', err instanceof Error ? err.message : err);
        }
      }
      return {
        content: [
          {
            type: 'text' as const,
            text: `Honcho: connected (workspace: ${handles.config.workspaceId}, session: ${handles.sessionKey})`,
          },
        ],
        details: { connected: true, workspace: handles.config.workspaceId, session: handles.sessionKey },
      };
    },
  });

  // --- honcho_summaries ---
  pi.registerTool({
    name: 'honcho_summaries',
    label: 'Honcho Summaries',
    description: 'Get session summaries — short and long auto-generated summaries.',
    promptSnippet: 'Get auto-generated session summaries from Honcho',
    promptGuidelines: [
      'Use honcho_summaries to check conversation summary state for debugging or context review.',
    ],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();
      try {
        const summaries = await handles.session.summaries();
        const lines: string[] = [];
        if (summaries.shortSummary) lines.push(`Short summary: ${summaries.shortSummary.content}`);
        if (summaries.longSummary) lines.push(`Long summary: ${summaries.longSummary.content}`);
        if (lines.length === 0) {
          return {
            content: [{ type: 'text' as const, text: 'No summaries available yet.' }],
            details: { hasShort: false, hasLong: false },
          };
        }
        return {
          content: [{ type: 'text' as const, text: lines.join('\n\n') }],
          details: { hasShort: !!summaries.shortSummary, hasLong: !!summaries.longSummary },
        };
      } catch {
        return {
          content: [{ type: 'text' as const, text: 'Failed to get summaries.' }],
          details: {},
        };
      }
    },
  });

  // --- honcho_card ---
  pi.registerTool({
    name: 'honcho_card',
    label: 'Honcho Peer Card',
    description: 'Get or set the peer card — structured identity facts about a peer.',
    promptSnippet: 'Get or set the peer card for structured peer identity',
    promptGuidelines: ['Use honcho_card to inspect or update structured peer identity facts.'],
    parameters: Type.Object({
      peer: Type.Optional(Type.String({ description: 'Target peer ID (default: user peer)' })),
      set: Type.Optional(
        Type.Array(Type.String(), {
          description: 'Set the card to these strings (replaces existing)',
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();
      const target = params.peer ?? handles.userPeer;
      try {
        if (params.set) {
          const result = await handles.aiPeer.setCard(params.set, target);
          return {
            content: [
              {
                type: 'text' as const,
                text: result ? `Card updated: ${result.join(', ')}` : 'Card update failed.',
              },
            ],
            details: {},
          };
        }
        const card = await handles.aiPeer.getCard(target);
        if (!card || card.length === 0) {
          return {
            content: [{ type: 'text' as const, text: 'No peer card available.' }],
            details: { hasCard: false },
          };
        }
        return {
          content: [{ type: 'text' as const, text: card.map((c) => `• ${c}`).join('\n') }],
          details: { hasCard: true, count: card.length },
        };
      } catch {
        return {
          content: [{ type: 'text' as const, text: 'Failed to get/set peer card.' }],
          details: {},
        };
      }
    },
  });

  // --- honcho_config ---
  pi.registerTool({
    name: 'honcho_config',
    label: 'Honcho Workspace Config',
    description: 'Inspect Honcho workspace configuration. Read-only.',
    promptSnippet: 'Inspect Honcho workspace configuration',
    promptGuidelines: [
      'Use honcho_config to inspect workspace-level Honcho settings for debugging.',
    ],
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();
      try {
        const config = await handles.honcho.getConfiguration();
        const lines: string[] = ['Workspace configuration:'];
        if (config.reasoning) lines.push(`  Reasoning: enabled=${config.reasoning.enabled ?? 'default'}`);
        if (config.peerCard) lines.push(`  Peer card: use=${config.peerCard.use ?? 'default'}, create=${config.peerCard.create ?? 'default'}`);
        if (config.summary) lines.push(`  Summary: enabled=${config.summary.enabled ?? 'default'}`);
        if (config.dream) lines.push(`  Dream: enabled=${config.dream.enabled ?? 'default'}`);
        if (lines.length === 1) lines.push('  (using defaults)');
        return {
          content: [{ type: 'text' as const, text: lines.join('\n') }],
          details: {},
        };
      } catch {
        return {
          content: [{ type: 'text' as const, text: 'Failed to get workspace configuration.' }],
          details: {},
        };
      }
    },
  });

  // --- honcho_upload ---
  pi.registerTool({
    name: 'honcho_upload',
    label: 'Honcho File Upload',
    description: 'Upload a file to the Honcho session for memory ingestion.',
    promptSnippet: 'Upload a file to Honcho session memory',
    promptGuidelines: [
      'Use honcho_upload to ingest document content into Honcho memory for future recall.',
      'Do not upload files containing secrets or credentials.',
    ],
    parameters: Type.Object({
      path: Type.String({ description: 'Path to the file to upload' }),
      contentType: Type.Optional(
        Type.String({ description: 'MIME type (default: auto-detected from extension)' }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const handles = ensureConnected();
      try {
        const fs = await import('node:fs/promises');
        const pathModule = await import('node:path');

        const resolved = pathModule.resolve(params.path);
        const content = await fs.readFile(resolved);
        const filename = pathModule.basename(resolved);

        const ext = pathModule.extname(resolved).toLowerCase();
        const mimeMap: Record<string, string> = {
          '.txt': 'text/plain',
          '.md': 'text/markdown',
          '.json': 'application/json',
          '.csv': 'text/csv',
          '.pdf': 'application/pdf',
          '.html': 'text/html',
          '.xml': 'application/xml',
          '.yaml': 'text/yaml',
          '.yml': 'text/yaml',
        };
        const contentType = params.contentType ?? mimeMap[ext] ?? 'application/octet-stream';

        const messages = await handles.session.uploadFile(
          { filename, content, content_type: contentType },
          handles.userPeer,
        );

        return {
          content: [
            {
              type: 'text' as const,
              text: `Uploaded ${filename} (${contentType}) — ${messages.length} message(s) created.`,
            },
          ],
          details: { messageCount: messages.length, filename, contentType },
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        return {
          content: [{ type: 'text' as const, text: `Upload failed: ${message}` }],
          details: {},
        };
      }
    },
  });
};
