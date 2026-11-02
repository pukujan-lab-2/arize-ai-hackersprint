import { describe, expect, it } from "vitest";
import { Endpointer, downmix, encodeWav, resample, rms } from "./audio";

const tone = (n: number, amp = 0.3) => Float32Array.from({ length: n }, (_, i) => amp * Math.sin(i / 5));

describe("encodeWav", () => {
  it("writes a 16-bit mono header and the samples", () => {
    const wav = encodeWav(Float32Array.from([0, 0.5, -0.5, 1, -1]), 16000);
    const view = new DataView(wav.buffer);
    expect(String.fromCharCode(...wav.slice(0, 4))).toBe("RIFF");
    expect(String.fromCharCode(...wav.slice(8, 12))).toBe("WAVE");
    expect(view.getUint16(22, true)).toBe(1);
    expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint16(34, true)).toBe(16);
    expect(view.getUint32(40, true)).toBe(10);
    expect(wav.length).toBe(44 + 10);
    expect(view.getInt16(44 + 6, true)).toBe(0x7fff);
    expect(view.getInt16(44 + 8, true)).toBe(-0x8000);
  });

  it("clips out-of-range samples instead of wrapping", () => {
    const view = new DataView(encodeWav(Float32Array.from([3, -3])).buffer);
    expect(view.getInt16(44, true)).toBe(0x7fff);
    expect(view.getInt16(46, true)).toBe(-0x8000);
  });
});

describe("resample and downmix", () => {
  it("brings 48 kHz down to a third of the samples", () => {
    expect(resample(tone(4800), 48000, 16000).length).toBe(1600);
  });
  it("keeps the signal when the rate already matches", () => {
    const input = tone(100);
    expect(resample(input, 16000, 16000)).toBe(input);
  });
  it("keeps a slow tone's level", () => {
    const out = resample(tone(48000), 48000, 16000);
    expect(rms(out)).toBeCloseTo(rms(tone(48000)), 1);
  });
  it("averages channels", () => {
    const mixed = downmix([Float32Array.from([1, 0]), Float32Array.from([0, 1])]);
    expect(Array.from(mixed)).toEqual([0.5, 0.5]);
  });
});

function run(endpointer: Endpointer, levels: number[], ms = 100) {
  const events: string[] = [];
  for (const level of levels) events.push(endpointer.push(level, ms));
  return events.filter((event) => event !== "idle");
}

describe("Endpointer", () => {
  const quiet = (n: number) => Array(n).fill(0.004);
  const loud = (n: number) => Array(n).fill(0.2);

  it("hears a question and ends after the pause", () => {
    expect(run(new Endpointer(), [...quiet(4), ...loud(10), ...quiet(12)])).toEqual(["speech", "end"]);
  });
  it("does not end on a short breath mid-sentence", () => {
    expect(run(new Endpointer(), [...quiet(4), ...loud(6), ...quiet(4), ...loud(6), ...quiet(12)])).toEqual(["speech", "end"]);
  });
  it("ignores a cough shorter than the minimum", () => {
    expect(run(new Endpointer({ waitMs: 3000 }), [...quiet(4), ...loud(1), ...quiet(40)])).toEqual(["timeout"]);
  });
  it("times out when nobody speaks", () => {
    expect(run(new Endpointer(), quiet(100))).toEqual(["timeout"]);
  });
  it("learns a noisy room and does not call it speech", () => {
    expect(run(new Endpointer({ waitMs: 3000 }), Array(40).fill(0.05))).toEqual(["timeout"]);
  });
  it("cuts a runaway recording", () => {
    expect(run(new Endpointer({ maxMs: 2000 }), [...quiet(4), ...loud(60)])).toEqual(["speech", "end"]);
  });
  it("says nothing after it has finished", () => {
    const endpointer = new Endpointer({ waitMs: 500 });
    run(endpointer, quiet(10));
    expect(endpointer.push(0.5, 100)).toBe("idle");
  });
});
