import { cache } from "react";
import { PublishedStory, STORY_ID } from "@/lib/stories";

// 127.0.0.1, not "localhost" - see app/api/analyze/route.ts for why.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// The one page that reads the backend from the server instead of through
// a route under app/api/: the story page is rendered on the server so
// its text and its <title> are in the HTML a search engine or a reader
// without JavaScript gets, and a withdrawn story answers 404. Same rules
// as the proxies all the same - server-side only, so BACKEND_URL and the
// key never reach the browser; the key sent when this server has one,
// though GET /reader/stories/{id} is open (backend tests/api/
// test_api_key.py::OPEN_ENDPOINTS); no-store, so unpublishing takes the
// page down on the next request.
function headers(json: boolean): HeadersInit {
  const apiKey = process.env.STORAGE_API_KEY;

  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
  };
}

export type StoryLoad =
  | { state: "ready"; story: PublishedStory }
  | { state: "missing" }
  | { state: "error" };

/**
 * One published story. `cache` makes the page and its generateMetadata
 * share one backend request per page view.
 *
 * A failure is logged here, on the server, and the page says only that
 * the story could not be loaded: this page is public, and the backend's
 * address and errors are nobody's business there.
 */
export const loadStory = cache(async (id: string): Promise<StoryLoad> => {
  // Malformed is "no such story" to a reader, as on /reader/[id].
  if (!STORY_ID.test(id)) return { state: "missing" };

  let response: Response;

  try {
    response = await fetch(`${BACKEND_URL}/reader/stories/${id}`, {
      cache: "no-store",
      headers: headers(false),
    });
  } catch (exc) {
    console.error(`Could not reach the backend at ${BACKEND_URL} for story ${id}:`, exc);
    return { state: "error" };
  }

  if (response.status === 404 || response.status === 422) return { state: "missing" };

  let data: unknown;

  try {
    data = await response.json();
  } catch {
    console.error(`The backend answered ${response.status} without JSON for story ${id}.`);
    return { state: "error" };
  }

  if (!response.ok) {
    console.error(`Loading story ${id} failed (${response.status}):`, data);
    return { state: "error" };
  }

  return { state: "ready", story: data as PublishedStory };
});
