import api from '@/lib/api';

/**
 * Turn a case's platforms + targets into collectable sources.
 *
 * Creating a case only creates the container. Nothing is fetched until a
 * collection run is requested, so every entry point (new-case wizard, overview
 * page) must build sources through this helper or an analyst is left staring at
 * an empty case.
 *
 * Platform ids come from the wizard: twitter | youtube | telegram | matrix | web.
 * The authenticated collectors use their own names: x | facebook | instagram.
 */
export interface CollectSource {
  [key: string]: unknown;
}

export interface BuildSourcesInput {
  platforms?: string[];
  /** Free-text targets the analyst typed in the wizard. */
  targets?: string[];
  keywords?: string[];
  caseId: string;
  /** Skip the authenticated browser run (it needs a headed window + minutes). */
  includeAuthenticated?: boolean;
}

const AUTH_PLATFORM: Record<string, { platform: string; envPrefix: string; cookiesEnv?: string; loginUrl?: string; verifyUrl: string }> = {
  x: { platform: 'x', envPrefix: 'X', cookiesEnv: 'X_COOKIES_JSON', verifyUrl: 'https://x.com/home' },
  twitter: { platform: 'x', envPrefix: 'X', cookiesEnv: 'X_COOKIES_JSON', verifyUrl: 'https://x.com/home' },
  facebook: { platform: 'facebook', envPrefix: 'FB', cookiesEnv: 'FB_COOKIES_JSON', loginUrl: 'https://www.facebook.com/login', verifyUrl: 'https://www.facebook.com/feed' },
  instagram: { platform: 'instagram', envPrefix: 'IG', cookiesEnv: 'IG_COOKIES_JSON', loginUrl: 'https://www.instagram.com/accounts/login/', verifyUrl: 'https://www.instagram.com/' },
};

function isUrl(v: string): boolean {
  return /^https?:\/\//i.test(v.trim());
}

export function buildCollectSources(input: BuildSourcesInput): CollectSource[] {
  const {
    platforms = [],
    targets = [],
    keywords = [],
    includeAuthenticated = true,
  } = input;
  const sources: CollectSource[] = [];
  const kws = keywords.map((k) => String(k || '').trim()).filter(Boolean);
  const urls = targets.map((t) => String(t || '').trim()).filter(isUrl);

  // Plain web pages: always safe, no credentials, no browser needed.
  for (const u of urls) {
    sources.push({ type: 'web', url: u });
  }

  // Keyword searches on the authenticated platforms. Uses the investigator's own
  // session; the case title/keywords act as the query.
  if (includeAuthenticated) {
    const query = kws.join(' ').trim();
    for (const p of platforms) {
      const auth = AUTH_PLATFORM[String(p).toLowerCase()];
      if (!auth) continue;
      if (auth.platform === 'x') {
        if (!query) continue;
        sources.push({
          type: 'auth_browser',
          driver: 'playwright',
          platform: 'x',
          env_prefix: 'X',
          session: 'ui-x',
          cookies_env: 'X_COOKIES_JSON',
          verify_url: 'https://x.com/home',
          mode: 'search',
          search_query: query,
          search_url: `https://x.com/search?q=${encodeURIComponent(query)}&f=live`,
          max_items: 15,
        });
      } else {
        // Facebook / Instagram need an explicit public permalink; a keyword alone
        // is not enough and guessing a search URL would collect the wrong thing.
        continue;
      }
    }
  }

  return sources;
}

export interface CollectResponse {
  job_id?: string;
  status?: string;
  received?: number;
  stored?: number;
  deduped?: number;
  reposts?: number;
  claims?: number;
  errors?: string[];
}

export async function runCollection(
  caseId: string,
  sources: CollectSource[],
  maxItems = 20
): Promise<CollectResponse> {
  const res = await api.post<CollectResponse>(
    `/cases/${caseId}/collect`,
    { sources, max_items: maxItems },
    { timeout: 15 * 60 * 1000 }
  );
  return res.data;
}
