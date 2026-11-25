import { keyFor, sendSignature } from "./sendKey";

const base = { account: "u-1", track: "registered-nurse", questionId: "q1", answer: "I checked.", storyId: null, revisesAnswerId: null };
let n = 0;
const make = () => `key-${++n}`;

describe("Send keys", () => {
  it("reuses the key only for the same send", () => {
    const first = keyFor(null, sendSignature(base), make);
    expect(keyFor(first, sendSignature(base), make)).toBe(first); // resent after no reply
    for (const change of [{ answer: "I checked again." }, { questionId: "q2" }, { account: "u-2" }, { storyId: "s1" }, { revisesAnswerId: "a1" }]) {
      expect(keyFor(first, sendSignature({ ...base, ...change }), make).key).not.toBe(first.key);
    }
  });

  it("makes keys the server accepts (8–64 of A–Z, a–z, 0–9, _ and -)", () => {
    const { key } = keyFor(null, sendSignature(base));
    expect(key).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(keyFor(null, sendSignature(base)).key).not.toBe(key);
  });
});
