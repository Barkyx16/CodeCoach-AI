/** Where an in-progress round answer is kept in this browser until it is submitted. */
export const roundDraftKey = (id: string, index: number) => `codecoach.round.${id}.${index}`;
