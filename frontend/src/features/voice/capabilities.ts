/**
 * What this browser can actually do. Nothing here asks for permission: detection only.
 *
 * Speech recognition is the browser's own service (Chrome and Edge send audio to their vendor's
 * speech servers; Safari may process it on the device). CodeCoach never receives audio, only the
 * text the learner chooses to submit.
 */

export interface RecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: { transcript: string };
}

export interface RecognitionEventLike {
  readonly resultIndex: number;
  readonly results: { readonly length: number; [index: number]: RecognitionResultLike };
}

export interface RecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: RecognitionEventLike) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type RecognitionCtor = new () => RecognitionLike;

export function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && typeof window.SpeechSynthesisUtterance === "function";
}

export function canTestMicrophone(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia;
}

export type MicPermission = "granted" | "denied" | "prompt" | "unknown";

/** The microphone permission state where the Permissions API supports it; never prompts. */
export async function microphonePermission(): Promise<MicPermission> {
  try {
    const status = await navigator.permissions?.query({ name: "microphone" as PermissionName });
    return (status?.state as MicPermission | undefined) ?? "unknown";
  } catch {
    return "unknown";
  }
}
