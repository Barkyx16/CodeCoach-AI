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
  /** Deliver results: [text, isFinal] pairs, as one recognition event. */
  emit(...results: [string, boolean][]) {
    const list = results.map(([text, isFinal]) => Object.assign([{ transcript: text }], { isFinal }));
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
let speaking: { onend?: () => void } | null = null;

class FakeUtterance {
  voice: unknown = null;
  rate = 1;
  volume = 1;
  onend?: () => void;
  onerror?: () => void;
  constructor(public text: string) {}
}

const synthesis = {
  getVoices: () => [{ name: "Test Voice", lang: "en-US", voiceURI: "test-voice" }],
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
  speak(u: FakeUtterance) {
    spoken.push(u.text);
    speaking = u;
  },
  cancel() {
    speaking = null;
  },
};

/** Finish the utterance being spoken, as the browser does when playback ends. */
export function finishSpeaking() {
  const u = speaking;
  speaking = null;
  act(() => u?.onend?.());
}

export function installSpeech({ recognition = true, synthesis: withSynthesis = true } = {}) {
  FakeRecognition.instances = [];
  spoken.length = 0;
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
