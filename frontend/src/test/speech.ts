/**
 * Test doubles for the browser's speech APIs. jsdom has neither, which is also how the app sees
 * a browser without voice support; install() adds controllable fakes.
 */
import { act } from "@testing-library/react";

type Handler<T> = ((e: T) => void) | null;

export class FakeRecognition {
  static instances: FakeRecognition[] = [];
  lang = "";
  continuous = false;
  interimResults = false;
  onresult: Handler<unknown> = null;
  onerror: Handler<{ error: string }> = null;
  onend: (() => void) | null = null;
  onstart: (() => void) | null = null;
  started = false;
  stopped = false;
  aborted = false;
  constructor() {
    FakeRecognition.instances.push(this);
  }
  start() {
    this.started = true;
  }
  stop() {
    this.stopped = true;
  }
  abort() {
    this.aborted = true;
  }
  /** Final results so far, as the browser keeps them: earlier results keep their index. */
  finals: string[] = [];
  /**
   * Deliver results: [text, isFinal] pairs, as one recognition event. Like a real browser in
   * continuous mode, they follow the session's earlier final results (resultIndex points at the
   * first new one); interim text sits after them and is replaced by the next event.
   */
  emit(...results: [string, boolean][]) {
    const resultIndex = this.finals.length;
    const list = [...this.finals.map((text) => [text, true] as [string, boolean]), ...results]
      .map(([text, isFinal]) => Object.assign([{ transcript: text }], { isFinal }));
    for (const [text, isFinal] of results) if (isFinal) this.finals.push(text);
    act(() => this.onresult?.({ resultIndex, results: list }));
  }
  /** What some mobile browsers do: send every earlier final result again, from index 0. */
  redeliver(...results: [string, boolean][]) {
    const list = [...this.finals.map((text) => [text, true] as [string, boolean]), ...results]
      .map(([text, isFinal]) => Object.assign([{ transcript: text }], { isFinal }));
    for (const [text, isFinal] of results) if (isFinal) this.finals.push(text);
    act(() => this.onresult?.({ resultIndex: 0, results: list }));
  }
  fail(error: string) {
    act(() => this.onerror?.({ error }));
  }
  end() {
    act(() => this.onend?.());
  }
  static get latest(): FakeRecognition {
    const r = FakeRecognition.instances.at(-1);
    if (!r) throw new Error("speech recognition was never started");
    return r;
  }
}

export const spoken: string[] = [];
let speaking: { onend?: () => void; onerror?: (e: { error: string }) => void } | null = null;
const voiceListeners = new Set<() => void>();

class FakeUtterance {
  voice: unknown = null;
  rate = 1;
  volume = 1;
  onend?: () => void;
  onerror?: (e: { error: string }) => void;
  constructor(public text: string) {}
}

const synthesis = {
  getVoices: () => [{ name: "Test Voice", lang: "en-US", voiceURI: "test-voice" }],
  addEventListener: (type: string, fn: () => void) => { if (type === "voiceschanged") voiceListeners.add(fn); },
  removeEventListener: (type: string, fn: () => void) => { if (type === "voiceschanged") voiceListeners.delete(fn); },
  speak(u: FakeUtterance) {
    spoken.push(u.text);
    speaking = u;
  },
  cancel() {
    speaking = null;
  },
};

/** Playback fails, as the browser reports it (e.g. "synthesis-failed", "not-allowed"). */
export function failSpeaking(error: string) {
  const u = speaking;
  speaking = null;
  act(() => u?.onerror?.({ error }));
}

/** The browser finishes loading its voices (it fires "voiceschanged", often after the page has started). */
export function loadVoices() {
  act(() => { for (const fn of [...voiceListeners]) fn(); });
}

/** Finish the utterance being spoken, as the browser does when playback ends. */
export function finishSpeaking() {
  const u = speaking;
  speaking = null;
  act(() => u?.onend?.());
}

export function installSpeech({ recognition = true, synthesis: withSynthesis = true } = {}) {
  FakeRecognition.instances = [];
  spoken.length = 0;
  speaking = null;
  voiceListeners.clear();
  const w = window as unknown as Record<string, unknown>;
  if (recognition) w.webkitSpeechRecognition = FakeRecognition;
  if (withSynthesis) {
    w.speechSynthesis = synthesis;
    w.SpeechSynthesisUtterance = FakeUtterance;
  }
}

export function uninstallSpeech() {
  const w = window as unknown as Record<string, unknown>;
  delete w.webkitSpeechRecognition;
  delete w.SpeechRecognition;
  delete w.speechSynthesis;
  delete w.SpeechSynthesisUtterance;
}
