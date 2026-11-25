/** The server's password rules, checked live as the user types (the server still enforces them). */
export const PASSWORD_RULES: { id: string; label: string; test(p: string): boolean }[] = [
  { id: "length", label: "At least 10 characters", test: (p) => p.length >= 10 },
  { id: "case", label: "Upper- and lower-case letters", test: (p) => p.toLowerCase() !== p && p.toUpperCase() !== p },
  { id: "digit", label: "At least one number", test: (p) => /\d/.test(p) },
  { id: "spaces", label: "No spaces at the start or end", test: (p) => p.length > 0 && p.trim() === p },
];

export const meetsPasswordRules = (p: string) => PASSWORD_RULES.every((r) => r.test(p));
