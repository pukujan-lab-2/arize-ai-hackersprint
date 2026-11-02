import { afterEach, describe, expect, it, vi } from "vitest";
import { pollRun, type AskTick } from "./api";

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
