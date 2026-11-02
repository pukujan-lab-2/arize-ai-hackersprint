// Records one utterance from the microphone as a 16 kHz WAV. Nothing is stored: the samples live in memory
// until they are sent, and the microphone is released the moment the recording ends.

import { Endpointer, TARGET_RATE, downmix, encodeWav, resample, rms, type EndpointOptions } from "./audio";

export type MicEnd = "end" | "stopped" | "timeout";

export type MicOptions = {
  /** Stop on its own when the person stops speaking. */
  auto?: boolean;
  endpoint?: EndpointOptions;
  onLevel?: (level: number) => void;
  onSpeech?: () => void;
  onEnd: (wav: Uint8Array | null, why: MicEnd) => void;
};

export type Recording = { stop: () => void; cancel: () => void };

export class MicDenied extends Error {}

export function micSupported(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof AudioContext !== "undefined";
}

export async function startRecording(options: MicOptions): Promise<Recording> {
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
    });
  } catch {
    throw new MicDenied("Microphone access was not allowed");
  }
  const context = new AudioContext();
  await context.resume().catch(() => undefined);
  const source = context.createMediaStreamSource(stream);
  // ScriptProcessor is deprecated but runs everywhere, including every iOS Safari, with no worker file to serve.
  const processor = context.createScriptProcessor(4096, 1, 1);
  const sink = context.createGain();
  sink.gain.value = 0;
  const chunks: Float32Array[] = [];
  const endpointer = options.auto ? new Endpointer(options.endpoint) : null;
  let done = false;
  let spoke = false;

  const finish = (why: MicEnd, keep: boolean) => {
    if (done) return;
    done = true;
    processor.onaudioprocess = null;
    source.disconnect();
    processor.disconnect();
    sink.disconnect();
    stream.getTracks().forEach((track) => track.stop());
    const rate = context.sampleRate;
    void context.close().catch(() => undefined);
    if (!keep || chunks.length === 0) {
      options.onEnd(null, why);
      return;
    }
    const all = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
    let at = 0;
    for (const chunk of chunks) {
      all.set(chunk, at);
      at += chunk.length;
    }
    options.onEnd(encodeWav(resample(all, rate, TARGET_RATE), TARGET_RATE), why);
  };

  processor.onaudioprocess = (event) => {
    if (done) return;
    const block = downmix([event.inputBuffer.getChannelData(0)]).slice();
    chunks.push(block);
    const level = rms(block);
    options.onLevel?.(level);
    if (!endpointer) return;
    const verdict = endpointer.push(level, (block.length / context.sampleRate) * 1000);
    if (verdict === "speech" && !spoke) {
      spoke = true;
      options.onSpeech?.();
    } else if (verdict === "end") finish("end", true);
    else if (verdict === "timeout") finish("timeout", false);
  };

  source.connect(processor);
  processor.connect(sink);
  sink.connect(context.destination);

  return {
    stop: () => finish("stopped", true),
    cancel: () => finish("stopped", false),
  };
}
