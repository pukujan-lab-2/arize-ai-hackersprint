// The browser's side of the speech host: is there a speech engine, wake it, send it a recording.
// The server decides what answers (the shared open-model host, or a keyed cloud fallback); the page only
// needs to know that dictation is possible and what the words were.

type Health = { speech?: { ok?: boolean } | null; elevenlabs?: boolean };

export type SpeechInfo = { dictation: boolean; localVoice: boolean };

let cached: { at: number; info: Promise<SpeechInfo> } | null = null;

/** Whether the server can transcribe, and whether it has its own voice. Asked at most once a minute. */
export function speechInfo(): Promise<SpeechInfo> {
  if (cached && Date.now() - cached.at < 60_000) return cached.info;
  const info = fetch("/api/health")
    .then((response) => (response.ok ? (response.json() as Promise<Health>) : ({} as Health)))
    .then((health) => ({
      dictation: !!health.speech?.ok || !!health.elevenlabs,
      localVoice: !!health.speech?.ok,
    }))
    .catch(() => ({ dictation: false, localVoice: false }));
  cached = { at: Date.now(), info };
  return info;
}

/** Wake the speech host while the reader is reaching for the microphone. Cheap, repeatable, never throws. */
export function warmSpeech(): void {
  void fetch("/api/speech/warm", { method: "POST", keepalive: true }).catch(() => undefined);
}

export class TranscribeError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/** Send a 16 kHz WAV, get the words. */
export async function transcribe(wav: Uint8Array, signal?: AbortSignal): Promise<string> {
  const form = new FormData();
  form.append("file", new Blob([wav], { type: "audio/wav" }), "question.wav");
  const response = await fetch("/api/stt", { method: "POST", body: form, signal });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string };
    throw new TranscribeError(body.error || "Speech to text is unavailable", response.status);
  }
  const body = (await response.json()) as { text?: string };
  return (body.text || "").trim();
}
