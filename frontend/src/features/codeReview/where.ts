/** "line 7" or "lines 9–10". */
export const where = (start: number, end: number) => (start === end ? `line ${start}` : `lines ${start}–${end}`);
