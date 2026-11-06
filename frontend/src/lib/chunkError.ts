/** Browsers word a failed dynamic import differently; any of these means a page's code didn't load. */
const CHUNK_FAILED = /dynamically imported module|Importing a module script failed|error loading dynamically imported module|Failed to fetch/i;

export function isChunkLoadError(error: unknown): boolean {
  return error instanceof Error && CHUNK_FAILED.test(error.message);
}
