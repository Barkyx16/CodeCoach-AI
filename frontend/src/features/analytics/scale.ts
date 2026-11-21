/** A score on its own scale ("0-100" reads 64/100), never converted to another. */
export function scoreOnScale(score: number, scale: string): string {
  const top = /^0-(\d+)$/.exec(scale)?.[1];
  return top ? `${score}/${top}` : `${score} (${scale})`;
}
