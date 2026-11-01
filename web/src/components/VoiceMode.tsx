// Hands-free mode: say a question, hear the short answer, say the next one. A full-screen conversation
// with one big control; tap it to interrupt the voice or to finish a question early, and close to leave.

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Mic, Square, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MicDenied, startRecording, type Recording } from "@/lib/mic";
import { transcribe, warmSpeech } from "@/lib/speech";
import { narrate, type Narration } from "@/map/narrator";
import { cn } from "@/lib/utils";

/** What the page hands back for the question just asked: the lines to say aloud. */
export type VoiceReply = { id: string; lines: string[] } | null;

type Phase = "listening" | "hearing" | "thinking" | "speaking";

const WORDS: Record<Phase, string> = {
  listening: "Listening…",
  hearing: "Go on, I'm listening",
  thinking: "Researching…",
  speaking: "Tap to interrupt",
};

type Props = {
  /** The page is working on a question. */
  busy: boolean;
  /** The newest reply; a new id means a new answer to say. */
  reply: VoiceReply;
  serverVoice: boolean;
  onAsk: (question: string) => void;
  onClose: () => void;
  onProblem: (message: string) => void;
};

export default function VoiceMode({ busy, reply, serverVoice, onAsk, onClose, onProblem }: Props) {
  const [phase, setPhase] = useState<Phase>("listening");
  const [level, setLevel] = useState(0);
  const [heard, setHeard] = useState("");
  const recording = useRef<Recording | null>(null);
  const speaking = useRef<Narration | null>(null);
  const spoken = useRef<string | null>(reply?.id ?? null);
  const waiting = useRef(false);
  const closed = useRef(false);
  const abort = useRef<AbortController | null>(null);
  const handlers = useRef({ onAsk, onClose, onProblem });
  handlers.current = { onAsk, onClose, onProblem };

  const listen = useCallback(async () => {
    if (closed.current) return;
    setPhase("listening");
    setHeard("");
    try {
      recording.current = await startRecording({
        auto: true,
        endpoint: { waitMs: 15000 },
        onLevel: setLevel,
        onSpeech: () => setPhase("hearing"),
        onEnd: (wav, why) => {
          recording.current = null;
          setLevel(0);
          if (closed.current) return;
          if (!wav) {
            if (why === "timeout") void listen();
            return;
          }
          setPhase("thinking");
          const controller = new AbortController();
          abort.current = controller;
          transcribe(wav, controller.signal)
            .then((words) => {
              if (closed.current) return;
              if (!words) {
                void listen();
                return;
              }
              setHeard(words);
              waiting.current = true;
              handlers.current.onAsk(words);
            })
            .catch((error: unknown) => {
              if (controller.signal.aborted || closed.current) return;
              handlers.current.onProblem(error instanceof Error ? error.message : "Speech to text is unavailable");
              handlers.current.onClose();
            });
        },
      });
    } catch (error) {
      handlers.current.onProblem(error instanceof MicDenied ? "Allow the microphone to talk hands-free." : "The microphone could not start.");
      handlers.current.onClose();
    }
  }, []);

  const say = useCallback(
    (lines: string[]) => {
      setPhase("speaking");
      const next = (at: number) => {
        if (closed.current) return;
        if (at >= lines.length) {
          speaking.current = null;
          void listen();
          return;
        }
        speaking.current = narrate(lines[at], () => next(at + 1), { server: serverVoice });
      };
      next(0);
    },
    [listen, serverVoice],
  );

  useEffect(() => {
    closed.current = false;
    warmSpeech();
    void listen();
    return () => {
      closed.current = true;
      recording.current?.cancel();
      speaking.current?.stop();
      abort.current?.abort();
    };
  }, [listen]);

  // A new answer arrives after the question was asked: say it.
  useEffect(() => {
    if (!waiting.current || busy || !reply || reply.id === spoken.current) return;
    waiting.current = false;
    spoken.current = reply.id;
    say(reply.lines);
  }, [busy, reply, say]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") handlers.current.onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const tap = () => {
    if (phase === "speaking") {
      speaking.current?.stop();
      speaking.current = null;
      void listen();
    } else if (phase === "hearing" || phase === "listening") {
      recording.current?.stop();
    }
  };

  const pulse = 1 + Math.min(0.35, level * 2.5);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Hands-free voice mode"
      className="fixed inset-0 z-50 flex flex-col items-center justify-between bg-background/95 px-6 pb-[max(2rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))] backdrop-blur"
    >
      <div className="flex w-full max-w-md justify-end">
        <Button variant="ghost" size="icon" className="h-11 w-11 rounded-full" onClick={onClose} aria-label="Leave voice mode">
          <X className="h-5 w-5" />
        </Button>
      </div>

      <div className="flex flex-col items-center gap-6 text-center">
        <button
          type="button"
          onClick={tap}
          disabled={phase === "thinking"}
          aria-label={phase === "speaking" ? "Interrupt and ask" : phase === "thinking" ? "Researching" : "Finish speaking"}
          style={{ transform: `scale(${phase === "listening" || phase === "hearing" ? pulse : 1})` }}
          className={cn(
            "flex h-32 w-32 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-xl transition-transform duration-100 motion-reduce:transition-none",
            phase === "thinking" && "animate-pulse motion-reduce:animate-none",
            phase === "speaking" && "ring-4 ring-primary/30",
          )}
        >
          {phase === "thinking" ? <Loader2 className="h-10 w-10 animate-spin" /> : phase === "speaking" ? <Square className="h-9 w-9" /> : <Mic className="h-10 w-10" />}
        </button>
        <p className="text-lg font-medium" aria-live="polite">
          {WORDS[phase]}
        </p>
        {heard && <p className="max-w-sm text-base text-muted-foreground">“{heard}”</p>}
      </div>

      <p className="max-w-xs text-center text-xs text-muted-foreground">
        Ask a legal question out loud. The short answer is read back; the full memo is waiting in the chat.
      </p>
    </div>
  );
}
