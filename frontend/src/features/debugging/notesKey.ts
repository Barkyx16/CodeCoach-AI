/** Where a learner's optional investigation notes for a debugging exercise are kept on this device
 * (removed with the account's other drafts at sign-out: auth/localWork.ts). */
export const debugNotesKey = (userId: string, slug: string) => `debug-notes:${userId}:${slug}`;
