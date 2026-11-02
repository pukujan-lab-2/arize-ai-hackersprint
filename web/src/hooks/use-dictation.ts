// Dictation: tap the microphone, say the question, it appears in the box. The recording ends when the
// reader stops speaking or taps again. Nothing is sent until it ends, and nothing is kept after.

import { useCallback, useEffect, useRef, useState } from "react";
import { MicDenied, micSupported, startRecording, type Recording } from "@/lib/mic";
import { speechInfo, transcribe, warmSpeech } from "@/lib/speech";

export type DictationState = "off" | "idle" | "listening" | "hearing" | "transcribing";

export function useDictation(onText: (text: string) => void, onProblem: (message: string) => void) {
  const [available, setAvailable] = useState(false);
  const [state, setState] = useState<DictationState>("idle");
  const [level, setLevel] = useState(0);
  const recording = useRef<Recording | null>(null);
  const abort = useRef<AbortController | null>(null);
  const text = useRef(onText);
  const problem = useRef(onProblem);
  text.current = onText;
  problem.current = onProblem;

  useEffect(() => {
    let live = true;
    if (!micSupported()) return;
    void speechInfo().then((info) => live && setAvailable(info.dictation));
    return () => {
      live = false;
    };
  }, []);

  const cancel = useCallback(() => {
    recording.current?.cancel();
    recording.current = null;
    abort.current?.abort();
    abort.current = null;
    setLevel(0);
    setState("idle");
  }, []);

  useEffect(() => cancel, [cancel]);

  const start = useCallback(async () => {
    warmSpeech();
    setState("listening");
    try {
      recording.current = await startRecording({
        auto: true,
        onLevel: setLevel,
        onSpeech: () => setState("hearing"),
        onEnd: (wav, why) => {
          recording.current = null;
          setLevel(0);
          if (!wav) {
            setState("idle");
            if (why === "timeout") problem.current("I didn't hear anything. Tap the microphone and try again.");
            return;
          }
          setState("transcribing");
          const controller = new AbortController();
          abort.current = controller;
          transcribe(wav, controller.signal)
            .then((words) => {
              if (words) text.current(words);
              else problem.current("I couldn't make that out. Try again a little closer to the microphone.");
            })
            .catch((error: unknown) => {
              if (controller.signal.aborted) return;
              problem.current(error instanceof Error ? error.message : "Speech to text is unavailable");
            })
            .finally(() => {
              abort.current = null;
              setState("idle");
            });
        },
      });
    } catch (error) {
      setState("idle");
      problem.current(error instanceof MicDenied ? "Allow the microphone to dictate a question." : "The microphone could not start.");
    }
  }, []);

  /** Tap: start, or finish early and send what was said. */
  const toggle = useCallback(() => {
    if (state === "transcribing") return;
    if (recording.current) recording.current.stop();
    else void start();
  }, [state, start]);

  return { available, state, level, toggle, cancel, active: state !== "idle" };
}
