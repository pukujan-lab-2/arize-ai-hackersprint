// The pure half of the microphone: turning what the browser captures into what the speech host reads, and
// deciding when a person has finished speaking. No browser APIs here, so it is tested without a microphone.

/** The host's speech models read 16 kHz mono. */
export const TARGET_RATE = 16000;

/** Mix any number of channels down to one. */
export function downmix(channels: Float32Array[]): Float32Array {
  if (channels.length === 0) return new Float32Array(0);
  if (channels.length === 1) return channels[0];
  const out = new Float32Array(channels[0].length);
  for (const channel of channels) for (let i = 0; i < out.length; i++) out[i] += channel[i] / channels.length;
  return out;
}

/** Linear resample. Speech at 16 kHz does not need better, and this runs on a phone. */
export function resample(input: Float32Array, from: number, to: number = TARGET_RATE): Float32Array {
  if (from === to || input.length === 0) return input;
  const length = Math.max(1, Math.round((input.length * to) / from));
  const out = new Float32Array(length);
  const step = (input.length - 1) / Math.max(1, length - 1);
  for (let i = 0; i < length; i++) {
    const at = i * step;
    const low = Math.floor(at);
    const high = Math.min(input.length - 1, low + 1);
    out[i] = input[low] + (input[high] - input[low]) * (at - low);
  }
  return out;
}

/** 16-bit PCM WAV, mono. */
export function encodeWav(samples: Float32Array, rate: number = TARGET_RATE): Uint8Array {
  const bytes = new Uint8Array(44 + samples.length * 2);
  const view = new DataView(bytes.buffer);
  const text = (at: number, value: string) => {
    for (let i = 0; i < value.length; i++) view.setUint8(at + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const clipped = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
  }
  return bytes;
}

/** Root-mean-square level of a block, 0 to 1. */
export function rms(block: Float32Array): number {
  if (block.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < block.length; i++) sum += block[i] * block[i];
  return Math.sqrt(sum / block.length);
}

export type EndpointEvent = "idle" | "speech" | "end" | "timeout";

export type EndpointOptions = {
  /** Level above which a block counts as speech, relative to the room's noise floor. */
  margin?: number;
  /** Lowest absolute level that can be speech, so a silent room is not "speech" at any ratio. */
  floor?: number;
  /** Silence after speech that ends the utterance, in ms. */
  hangMs?: number;
  /** Speech shorter than this is a cough or a tap, not a question, in ms. */
  minSpeechMs?: number;
  /** Give up if nobody speaks at all, in ms. */
  waitMs?: number;
  /** Stop a runaway recording, in ms. */
  maxMs?: number;
};

/**
 * Decides when an utterance starts and ends from block levels. The noise floor is learned from the first
 * blocks, so it works in a quiet room and on a train. Feed it one block at a time with that block's length in ms.
 */
export class Endpointer {
  private readonly o: Required<EndpointOptions>;
  private noise = 0;
  private learned = 0;
  private heardMs = 0;
  private silentMs = 0;
  private elapsed = 0;
  private spoke = false;
  private finished = false;

  constructor(options: EndpointOptions = {}) {
    this.o = { margin: 3, floor: 0.015, hangMs: 900, minSpeechMs: 250, waitMs: 8000, maxMs: 30000, ...options };
  }

  /** True once speech has begun. */
  get speaking(): boolean {
    return this.spoke;
  }

  push(level: number, ms: number): EndpointEvent {
    if (this.finished) return "idle";
    this.elapsed += ms;
    if (this.learned < 300) {
      // The first 300 ms set the floor; people do not start mid-syllable the instant the mic opens.
      this.noise = this.learned === 0 ? level : (this.noise + level) / 2;
      this.learned += ms;
    }
    const loud = level > Math.max(this.o.floor, this.noise * this.o.margin);
    if (loud) {
      this.heardMs += ms;
      this.silentMs = 0;
      if (!this.spoke && this.heardMs >= this.o.minSpeechMs) {
        this.spoke = true;
        return "speech";
      }
    } else if (this.spoke) {
      this.silentMs += ms;
      if (this.silentMs >= this.o.hangMs) {
        this.finished = true;
        return "end";
      }
    } else {
      this.heardMs = 0;
    }
    if (!this.spoke && this.elapsed >= this.o.waitMs) {
      this.finished = true;
      return "timeout";
    }
    if (this.elapsed >= this.o.maxMs) {
      this.finished = true;
      return this.spoke ? "end" : "timeout";
    }
    return "idle";
  }
}
