/** The server's limit on collections per account (backend/app/services/explore.py, MAX_COLLECTIONS),
 * so the page can say it before a copy would pass it. The server still decides: past it, it refuses
 * with `too_many_collections` and the count. */
export const MAX_COLLECTIONS = 50;
