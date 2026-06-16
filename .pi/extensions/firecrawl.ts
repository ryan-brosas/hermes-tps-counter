import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';
import { Type } from '@sinclair/typebox';

const FIRECRAWL_URL = process.env.FIRECRAWL_URL || 'http://localhost:3002';
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || '';

const headers: Record<string, string> = {
  'Content-Type': 'application/json',
  ...(FIRECRAWL_API_KEY ? { Authorization: `Bearer ${FIRECRAWL_API_KEY}` } : {}),
};

const firecrawlFetch = async (path: string, body: Record<string, unknown>): Promise<any> => {
  const res = await fetch(`${FIRECRAWL_URL}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`Firecrawl ${path}: ${res.status} ${res.statusText}`);
  }
  return res.json();
};

export default function firecrawl(pi: ExtensionAPI): void {
  // --- web_search ---
  pi.registerTool({
    name: 'web_search',
    label: 'Web Search',
    description: 'Search the web via Firecrawl. Returns titles, URLs, and optionally full markdown content.',
    promptSnippet: 'Search the web for information',
    promptGuidelines: [
      'Use web_search to find current information about libraries, APIs, documentation, and best practices.',
      'Add scrapeOptions to get full page content in one call.',
      'Use categories to filter: "github" for repos, "research" for papers, "pdf" for docs.',
    ],
    parameters: Type.Object({
      query: Type.String({ description: 'Search query' }),
      limit: Type.Optional(Type.Number({ description: 'Max results (default: 5)' })),
      categories: Type.Optional(
        Type.Array(Type.String(), {
          description: 'Filter by category: github, research, pdf',
        }),
      ),
      scrape: Type.Optional(
        Type.Boolean({
          description: 'Scrape full markdown from results (default: false)',
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const body: Record<string, unknown> = {
        query: params.query,
        limit: params.limit || 5,
      };

      if (params.categories?.length) {
        body.categories = params.categories;
      }

      if (params.scrape) {
        body.scrapeOptions = { formats: ['markdown'] };
      }

      try {
        const result = await firecrawlFetch('/v1/search', body);

        if (!result.success) {
          return {
            content: [{ type: 'text' as const, text: `Search failed: ${JSON.stringify(result)}` }],
            details: {},
          };
        }

        // Handle both cloud API format (data.web/data.news) and self-hosted format (flat array)
        const rawData = result.data;
        const web: any[] = Array.isArray(rawData)
          ? rawData
          : rawData?.web || [];
        const news: any[] = Array.isArray(rawData)
          ? []
          : rawData?.news || [];

        if (web.length === 0 && news.length === 0) {
          return {
            content: [{ type: 'text' as const, text: 'No results found.' }],
            details: {},
          };
        }

        const lines: string[] = [];

        if (web.length > 0) {
          lines.push('## Web Results');
          for (const item of web) {
            lines.push(`### ${item.title}`);
            lines.push(`URL: ${item.url}`);
            if (item.description) lines.push(item.description);
            if (item.markdown) {
              lines.push(`\n<content>\n${item.markdown.slice(0, 3000)}\n</content>`);
            }
            lines.push('');
          }
        }

        if (news.length > 0) {
          lines.push('## News Results');
          for (const item of news) {
            lines.push(`### ${item.title}`);
            lines.push(`URL: ${item.url}`);
            if (item.snippet) lines.push(item.snippet);
            if (item.date) lines.push(`Date: ${item.date}`);
            lines.push('');
          }
        }

        return {
          content: [{ type: 'text' as const, text: lines.join('\n') }],
          details: { webCount: web.length, newsCount: news.length },
        };
      } catch (err: any) {
        return {
          content: [{ type: 'text' as const, text: `Search error: ${err.message}` }],
          details: {},
        };
      }
    },
  });

  // --- web_scrape ---
  pi.registerTool({
    name: 'web_scrape',
    label: 'Web Scrape',
    description: 'Scrape a URL and get clean markdown content. Handles JS-rendered pages, PDFs, and more.',
    promptSnippet: 'Scrape a URL to get clean markdown content',
    promptGuidelines: [
      'Use web_scrape to fetch documentation, API references, blog posts, and articles.',
      'Returns clean markdown that can be read directly.',
      'Works with JS-rendered pages, PDFs, and dynamic sites.',
    ],
    parameters: Type.Object({
      url: Type.String({ description: 'URL to scrape' }),
      formats: Type.Optional(
        Type.Array(Type.String(), {
          description: 'Output formats: markdown, html, links, screenshot (default: ["markdown"])',
        }),
      ),
      onlyMainContent: Type.Optional(
        Type.Boolean({
          description: 'Extract only main content, skip nav/footer (default: true)',
        }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const body: Record<string, unknown> = {
        url: params.url,
        formats: params.formats || ['markdown'],
        onlyMainContent: params.onlyMainContent !== false,
      };

      try {
        const result = await firecrawlFetch('/v1/scrape', body);

        if (!result.success) {
          return {
            content: [{ type: 'text' as const, text: `Scrape failed: ${JSON.stringify(result)}` }],
            details: {},
          };
        }

        const data = result.data || {};
        const markdown = data.markdown || '';
        const links = data.links || [];

        const lines: string[] = [];
        lines.push(`# ${data.metadata?.title || params.url}`);
        if (data.metadata?.description) {
          lines.push(`> ${data.metadata.description}`);
        }
        lines.push('');
        lines.push(markdown.slice(0, 15000));

        if (markdown.length > 15000) {
          lines.push(`\n\n[Truncated — ${markdown.length} chars total]`);
        }

        if (links.length > 0) {
          lines.push(`\n\n## Links (${links.length})`);
          for (const link of links.slice(0, 20)) {
            lines.push(`- ${link}`);
          }
        }

        return {
          content: [{ type: 'text' as const, text: lines.join('\n') }],
          details: {
            url: params.url,
            title: data.metadata?.title,
            markdownLength: markdown.length,
            linkCount: links.length,
          },
        };
      } catch (err: any) {
        return {
          content: [{ type: 'text' as const, text: `Scrape error: ${err.message}` }],
          details: {},
        };
      }
    },
  });

  // --- web_extract ---
  pi.registerTool({
    name: 'web_extract',
    label: 'Web Extract',
    description: 'Extract structured data from URLs using a natural language prompt or schema.',
    promptSnippet: 'Extract structured data from web pages',
    promptGuidelines: [
      'Use web_extract to pull specific information from pages (prices, dates, names, etc.).',
      'Provide a clear prompt describing what to extract.',
      'Returns structured JSON data.',
    ],
    parameters: Type.Object({
      urls: Type.Array(Type.String(), { description: 'URLs to extract from (max 5)' }),
      prompt: Type.String({ description: 'What to extract from the pages' }),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      try {
        const result = await firecrawlFetch('/v1/extract', {
          urls: params.urls.slice(0, 5),
          prompt: params.prompt,
        });

        if (!result.success) {
          return {
            content: [{ type: 'text' as const, text: `Extract failed: ${JSON.stringify(result)}` }],
            details: {},
          };
        }

        return {
          content: [
            {
              type: 'text' as const,
              text: JSON.stringify(result.data, null, 2).slice(0, 10000),
            },
          ],
          details: {},
        };
      } catch (err: any) {
        return {
          content: [{ type: 'text' as const, text: `Extract error: ${err.message}` }],
          details: {},
        };
      }
    },
  });

  // --- web_map ---
  pi.registerTool({
    name: 'web_map',
    label: 'Web Map',
    description: 'Discover all URLs on a website. Useful for finding documentation pages, API endpoints, and site structure.',
    promptSnippet: 'Discover URLs on a website',
    promptGuidelines: [
      'Use web_map to find all pages on a site before scraping.',
      'Good for discovering documentation structure, API endpoints, and blog posts.',
    ],
    parameters: Type.Object({
      url: Type.String({ description: 'Website URL to map' }),
      limit: Type.Optional(Type.Number({ description: 'Max URLs to return (default: 50)' })),
      search: Type.Optional(
        Type.String({ description: 'Filter URLs by search term' }),
      ),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, _ctx) {
      const body: Record<string, unknown> = {
        url: params.url,
        limit: params.limit || 50,
      };

      if (params.search) {
        body.search = params.search;
      }

      try {
        const result = await firecrawlFetch('/v1/map', body);

        if (!result.success) {
          return {
            content: [{ type: 'text' as const, text: `Map failed: ${JSON.stringify(result)}` }],
            details: {},
          };
        }

        const links = result.data?.links || [];

        if (links.length === 0) {
          return {
            content: [{ type: 'text' as const, text: 'No URLs found.' }],
            details: {},
          };
        }

        const lines: string[] = [`## URLs on ${params.url} (${links.length})`];
        for (const link of links) {
          if (typeof link === 'string') {
            lines.push(`- ${link}`);
          } else {
            lines.push(`- ${link.url || link}`);
          }
        }

        return {
          content: [{ type: 'text' as const, text: lines.join('\n') }],
          details: { count: links.length },
        };
      } catch (err: any) {
        return {
          content: [{ type: 'text' as const, text: `Map error: ${err.message}` }],
          details: {},
        };
      }
    },
  });
}
