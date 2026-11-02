import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pollRun, streamRun, type AskTick } from "./api";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("pollRun while the engine wakes", () => {
  it("waits past 90 seconds for an answer and says why it is slow", async () => {
    vi.useFakeTimers();
    const answer = { answer: "done" };
    const started = Date.now();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          events: [{ agent: "retriever", kind: "start", msg: "searching" }],
          result: Date.now() - started >= 100_000 ? answer : null,
        }),
      })),
    );
    const ticks: AskTick[] = [];
    const pending = pollRun("run-1", (tick) => ticks.push(tick));
    await vi.advanceTimersByTimeAsync(101_000);
    await expect(pending).resolves.toEqual(answer);
    expect(ticks.some((tick) => /Waking the retrieval engine/.test(tick.detail))).toBe(true);
    expect(ticks[0].detail).not.toMatch(/Waking/);
  });

  it("gives up only after four minutes", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ events: [], result: null }) })));
    const pending = pollRun("run-2");
    const settled = vi.fn();
    void pending.then(settled);
    await vi.advanceTimersByTimeAsync(200_000);
    expect(settled).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(45_000);
    await expect(pending).resolves.toBeNull();
  });
});

describe("streamRun", () => {
  beforeEach(() => {
    vi.stubGlobal("window", { setTimeout: globalThis.setTimeout.bind(globalThis), clearTimeout: globalThis.clearTimeout.bind(globalThis) });
  });

  class FakeSource {
    static last: FakeSource;
    listeners: Record<string, ((event: MessageEvent) => void)[]> = {};
    onerror: (() => void) | null = null;
    closed = false;
    constructor(public url: string) {
      FakeSource.last = this;
    }
    addEventListener(name: string, fn: (event: MessageEvent) => void) {
      (this.listeners[name] ||= []).push(fn);
    }
    emit(name: string, data: unknown) {
      this.listeners[name]?.forEach((fn) => fn({ data: JSON.stringify(data) } as MessageEvent));
    }
    close() {
      this.closed = true;
    }
  }

  it("reports each tick and resolves with the result", async () => {
    vi.stubGlobal("EventSource", FakeSource);
    const ticks: AskTick[] = [];
    const pending = streamRun("run-9", (tick) => ticks.push(tick));
    FakeSource.last.emit("tick", { events: [{ agent: "answer", kind: "start", msg: "writing" }], partial: "Short answer" });
    FakeSource.last.emit("done", { events: [], result: { answer: "ok" } });
    await expect(pending).resolves.toEqual({ answer: "ok" });
    expect(FakeSource.last.url).toBe("/api/run/run-9/stream");
    expect(ticks[0].draft).toBe("Short answer");
    expect(FakeSource.last.closed).toBe(true);
  });

  it("hands back to polling when the stream fails", async () => {
    vi.stubGlobal("EventSource", FakeSource);
    const pending = streamRun("run-10");
    FakeSource.last.onerror?.();
    await expect(pending).resolves.toBeUndefined();
  });

  it("hands back to polling when the browser has no EventSource", async () => {
    vi.stubGlobal("EventSource", undefined);
    await expect(streamRun("run-11")).resolves.toBeUndefined();
  });
});
