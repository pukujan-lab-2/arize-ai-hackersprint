// The one page: ask a question, read the memo, and turn the answer into a map. The conversation stays
// a conversation — the figures behind an answer, its sources and its retrieval record open in drawers,
// and the map is a mode of the same page rather than a place of its own.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import {
  ArrowUp,
  Clock,
  Menu,
  ShieldAlert,
  ShieldCheck,
  BookOpen,
  CheckCircle2,
  Circle,
  Copy,
  CornerDownRight,
  FlaskConical,
  Gauge,
  Loader2,
  MapPin,
  MessagesSquare,
  PanelRight,
  Plus,
  Sparkles,
  Volume2,
  VolumeX,
  type LucideIcon,
} from "lucide-react";
import type { ShellContext } from "@/components/AppShell";
import AuthorityDetail from "@/components/AuthorityDetail";
import CitationMap, { placesOf, type MapPlace } from "@/components/CitationMap";
import DetailDrawer from "@/components/DetailDrawer";
import EvidenceList from "@/components/EvidenceList";
import Memo from "@/components/Memo";
import CheckPopover from "@/components/CheckPopover";
import ExportMenu from "@/components/ExportMenu";
import PrintReport from "@/components/PrintReport";
import QuestionBank from "@/components/QuestionBank";
import SourcePane from "@/components/SourcePane";
import MapPanel, { type PanelTab } from "@/components/MapPanel";
import TurnDetails from "@/components/TurnDetails";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useNarration } from "@/hooks/use-narration";
import { useTour } from "@/hooks/use-tour";
import { useWide } from "@/hooks/use-wide";
import { pathLine, plainText, tourPlan } from "@/map/tour";
import { AskRefused, STAGE_PLAN, STAGE_WORDS, ask, loadRunResult, warmEngine, type AskTick, type Source, type StageTick } from "@/lib/api";
import { citeType, locate, type Citation, type RunResult } from "@/lib/citations";
import { seconds, toRetrieval } from "@/lib/runs";
import { cn } from "@/lib/utils";
import { showError, showSuccess } from "@/utils/toast";

type AssistantTurn = {
  id: string;
  role: "assistant";
  result: RunResult;
  runId: string;
  source: Source;
};

type Turn = { id: string; role: "user"; text: string } | AssistantTurn | { id: string; role: "error"; text: string };

const EMPTY_STAGES: StageTick[] = STAGE_PLAN.map((name) => ({ name, state: "waiting", message: "" }));

let counter = 0;
const nextId = () => `t${(counter += 1)}`;

function StageRow({ stage }: { stage: StageTick }) {
  const Icon = stage.state === "done" ? CheckCircle2 : stage.state === "running" ? Loader2 : Circle;
  return (
    <li className="flex items-start gap-2">
      <Icon
        className={cn(
          "mt-0.5 h-3.5 w-3.5 shrink-0",
          stage.state === "done" && "text-emerald-500",
          stage.state === "running" && "animate-spin text-foreground motion-reduce:animate-none",
          stage.state === "waiting" && "text-muted-foreground/50",
        )}
      />
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            "block text-xs font-medium",
            stage.state === "waiting" ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {STAGE_WORDS[stage.name]}
        </span>
        {stage.message && <span className="mt-0.5 block text-xs text-muted-foreground">{stage.message}</span>}
      </span>
    </li>
  );
}

/** One thing the reader can do with an answer, in the drawer that now holds them all. */
function ToolRow({
  icon: Icon,
  label,
  hint,
  onClick,
  disabled,
}: {
  icon: LucideIcon;
  label: string;
  hint: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-start gap-2.5 rounded-lg border border-border bg-card px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-50 disabled:hover:bg-card"
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{label}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">{hint}</span>
      </span>
    </button>
  );
}

export default function Chat() {
  const { refreshRuns, resetToken, openNav, source: corpus } = useOutletContext<ShellContext>();
  const [params, setParams] = useSearchParams();

  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<AskTick | null>(null);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [mode, setMode] = useState<"chat" | "map">("chat");
  const [mapTurnId, setMapTurnId] = useState<string | null>(null);

  const [authority, setAuthority] = useState<Citation | null>(null);
  /** The source open beside the memo: which answer it belongs to and where it sits in that answer's list. */
  const [source, setSource] = useState<{ turnId: string; index: number } | null>(null);
  const wide = useWide();
  const [sources, setSources] = useState<Citation[] | null>(null);
  const [place, setPlace] = useState<MapPlace | null>(null);
  /** The map panel: which tab is open, which opinion in its Sources tab, and how tall the phone sheet is. */
  const [panelTab, setPanelTab] = useState<PanelTab>("tour");
  const [panelSource, setPanelSource] = useState<number | null>(null);
  const [sheetH, setSheetH] = useState(0);
  const [details, setDetails] = useState<AssistantTurn | null>(null);
  const [followUps, setFollowUps] = useState<string[] | null>(null);
  /** The answer whose tools are open in the drawer: sources, follow-ups, the figures, the voice, the map. */
  const [actions, setActions] = useState<AssistantTurn | null>(null);
  /** The answer being printed or saved as a PDF: its report is on the page only while this is set. */
  const [printing, setPrinting] = useState<AssistantTurn | null>(null);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  /** The run this page wrote into the address itself, so opening it does not read it back a second time. */
  const skipRun = useRef<string | null>(null);
  const tokenRef = useRef(resetToken);

  const { status: narrationStatus, speak, stop: stopNarration, active: narrating } = useNarration();

  /** The tour is declared below the answer it walks, so the thread's own controls reach it through a ref. */
  const stopTourRef = useRef<() => void>(() => {});

  const clearThread = useCallback(() => {
    stopTourRef.current();
    stopNarration();
    setTurns([]);
    setDraft("");
    setLastRunId(null);
    setProgress(null);
    setMode("chat");
    setMapTurnId(null);
    setAuthority(null);
    setSource(null);
    setSources(null);
    setPlace(null);
    setDetails(null);
    setFollowUps(null);
    setActions(null);
    setParams(new URLSearchParams(), { replace: true });
    inputRef.current?.focus();
  }, [stopNarration, setParams]);

  const askQuestion = useCallback(
    async (text: string) => {
      const asked = text.trim();
      if (!asked) return;
      setBusy(true);
      setDraft("");
      setProgress({
        stage: STAGE_WORDS.planner,
        detail: "",
        draft: "",
        stages: EMPTY_STAGES.map((stage) => ({ ...stage })),
      });
      setTurns((current) => [...current, { id: nextId(), role: "user", text: asked }]);
      try {
        const { runId, result, source } = await ask(asked, {
          prevRunId: lastRunId,
          onTick: (tick) => setProgress(tick),
        });
        setLastRunId(runId);
        setTurns((current) => [...current, { id: nextId(), role: "assistant", result, runId, source }]);
        skipRun.current = runId;
        setParams(new URLSearchParams({ run: runId }), { replace: true });
        refreshRuns();
      } catch (error) {
        const message =
          error instanceof AskRefused
            ? error.message
            : "That question didn't come back. The agents may still be working — try again in a moment.";
        setTurns((current) => [...current, { id: nextId(), role: "error", text: message }]);
      } finally {
        setBusy(false);
        setProgress(null);
      }
    },
    [lastRunId, refreshRuns, setParams],
  );

  // The retrieval engine sleeps when idle; start it loading while the reader is still reading the page.
  useEffect(() => {
    warmEngine("load");
  }, []);

  // A saved run named in the address opens as its own conversation.
  useEffect(() => {
    const runId = (params.get("run") || "").trim();
    if (!runId) return;
    if (skipRun.current === runId) {
      skipRun.current = null;
      return;
    }
    let cancelled = false;
    void loadRunResult(runId).then(({ result, source }) => {
      if (cancelled || !result) return;
      const id = nextId();
      const question = (result.question || "").trim();
      setLastRunId(runId);
      setTurns(() => [
        ...(question ? [{ id: `${id}-q`, role: "user" as const, text: question }] : []),
        { id, role: "assistant" as const, result, runId, source },
      ]);
      setMode("chat");
      setMapTurnId(null);
    });
    return () => {
      cancelled = true;
    };
  }, [params]);

  // The shell's "New chat" asks for an empty thread by bumping this token.
  useEffect(() => {
    if (tokenRef.current === resetToken) return;
    tokenRef.current = resetToken;
    clearThread();
  }, [resetToken, clearThread]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element || mode !== "chat") return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    element.scrollTo({ top: element.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, [turns.length, progress?.draft, mode]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      stopNarration();
      stopTourRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stopNarration]);

  const assistants = useMemo(
    () => turns.filter((turn): turn is AssistantTurn => turn.role === "assistant"),
    [turns],
  );
  const latest = assistants.length ? assistants[assistants.length - 1] : null;
  const mapTurn = useMemo(
    () => assistants.find((turn) => turn.id === mapTurnId) ?? latest,
    [assistants, mapTurnId, latest],
  );

  // The tour walks the answer that is on the map: the short answer, the path the retriever took, the
  // opinion and the rest of the memo, then every authority at the place the camera moves to. It starts
  // on a click, never on its own.
  const tourSteps = useMemo(() => (mapTurn ? tourPlan(mapTurn.result) : []), [mapTurn]);
  const tour = useTour(tourSteps, stopNarration);
  useEffect(() => {
    stopTourRef.current = tour.stop;
  }, [tour.stop]);

  const mapPath = useMemo(() => {
    if (!mapTurn) return "";
    const links = mapTurn.result.edges?.length ?? 0;
    const drawn = links
      ? `${links} citation ${links === 1 ? "link" : "links"} drawn between them.`
      : "No citation link joins them.";
    return `${pathLine(mapTurn.result)} ${drawn}`;
  }, [mapTurn]);

  // The places the walk has reached, in order, so the map can ink the traversal as it happens.
  const trail = useMemo(() => {
    if (!tour.active) return [];
    const out: string[] = [];
    for (const step of tourSteps.slice(0, tour.index + 1)) {
      if (!step.place || out[out.length - 1] === step.place) continue;
      out.push(step.place);
    }
    return out;
  }, [tour.active, tour.index, tourSteps]);

  // The place the walk is standing on, named the way the pin is, so the strip and the map agree.
  const tourAt = useMemo(() => {
    const key = tour.active ? tour.current?.place ?? null : null;
    if (!key) return null;
    const citation = (mapTurn?.result.citations || []).find((item) => locate(item).key === key);
    return citation ? locate(citation).label : null;
  }, [tour.active, tour.current, mapTurn]);

  // The walk belongs to the map: leaving the map leaves the walk.
  useEffect(() => {
    if (mode !== "map") tour.stop();
  }, [mode, tour.stop]);

  const title = useMemo(() => {
    const first = turns.find((turn) => turn.role === "user");
    return first && first.role === "user" ? first.text : "New conversation";
  }, [turns]);

  const submit = () => {
    if (busy || !draft.trim()) return;
    void askQuestion(draft);
  };

  const openMap = (turn: AssistantTurn) => {
    setMapTurnId(turn.id);
    setPlace(null);
    setMode("map");
  };

  /** Open a cited authority beside its memo; one that is in no answer's list falls back to the drawer. */
  const openSource = useCallback(
    (citation: Citation, turn?: AssistantTurn) => {
      const pool = turn ? [turn] : [...assistants].reverse();
      for (const candidate of pool) {
        const list = candidate.result.citations || [];
        const at = list.findIndex((item) => item === citation || (!!item.id && item.id === citation.id));
        if (at >= 0) {
          setSource({ turnId: candidate.id, index: at });
          return;
        }
      }
      setAuthority(citation);
    },
    [assistants],
  );

  const sourceTurn = source ? assistants.find((turn) => turn.id === source.turnId) ?? null : null;
  const sourcePane = sourceTurn && source && (
    <SourcePane
      citations={sourceTurn.result.citations || []}
      index={source.index}
      answer={sourceTurn.result.answer || ""}
      safeguard={sourceTurn.result.safeguard}
      onSelect={(index) => setSource({ turnId: sourceTurn.id, index })}
      onClose={wide ? () => setSource(null) : undefined}
      onAsk={(question) => {
        setSource(null);
        void askQuestion(question);
      }}
      className="h-full"
    />
  );

  const selectPlace = useCallback((next: MapPlace) => {
    setPlace(next);
    setPanelTab("places");
  }, []);

  const mapPlaces = useMemo(() => placesOf(mapTurn?.result.citations || []), [mapTurn]);

  // The one panel that holds the tour, the places, the sources and the key: a sidebar beside the map on a
  // wide screen, a sheet that pulls up from the bottom of it on a phone.
  const mapPanel = (variant: "side" | "sheet") =>
    mapTurn ? (
      <MapPanel
        variant={variant}
        onHeight={variant === "sheet" ? setSheetH : undefined}
        tour={{
          steps: tourSteps,
          index: tour.index,
          status: tour.status,
          heard: tour.heard,
          at: tourAt,
          path: mapPath,
          start: () => {
            setPanelTab("tour");
            tour.start();
          },
          stop: tour.stop,
          prev: tour.prev,
          next: tour.next,
          canPrev: tour.canPrev,
          canNext: tour.canNext,
        }}
        places={mapPlaces}
        place={place}
        onPlace={setPlace}
        citations={mapTurn.result.citations || []}
        answer={mapTurn.result.answer || ""}
        safeguard={mapTurn.result.safeguard}
        tab={panelTab}
        onTab={setPanelTab}
        sourceIndex={panelSource}
        onSourceIndex={setPanelSource}
        onAsk={(question) => {
          setMode("chat");
          void askQuestion(question);
        }}
      />
    ) : null;

  // The report is mounted first, then the print dialog opens over it; closing the dialog unmounts it.
  useEffect(() => {
    if (!printing) return;
    const done = () => setPrinting(null);
    window.addEventListener("afterprint", done);
    const timer = window.setTimeout(() => window.print(), 80);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("afterprint", done);
    };
  }, [printing]);

  const copyAnswer = async (answer: string) => {
    try {
      await navigator.clipboard.writeText(answer);
      showSuccess("Memo copied");
    } catch {
      showError("The browser would not copy that");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-border px-2 sm:h-12 sm:px-3">
        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-11 shrink-0 sm:h-9 sm:w-9 lg:hidden"
          aria-label="Open conversations"
          onClick={openNav}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <h1 className="min-w-0 flex-1 truncate px-1 text-sm font-semibold tracking-tight">
          {mode === "map" ? mapTurn?.result.question || title : title}
        </h1>

        <ToggleGroup
          type="single"
          size="sm"
          value={mode}
          onValueChange={(value) => value && setMode(value as "chat" | "map")}
          className="rounded-full border border-border p-0.5"
          aria-label="Show the conversation or the map"
        >
          <ToggleGroupItem value="chat" className="h-11 w-11 rounded-full p-0 sm:h-8 sm:w-8" aria-label="Chat" title="Chat">
            <MessagesSquare className="h-4 w-4" />
          </ToggleGroupItem>
          <ToggleGroupItem value="map" className="h-11 w-11 rounded-full p-0 sm:h-8 sm:w-8" aria-label="Map" title="Map">
            <MapPin className="h-4 w-4" />
          </ToggleGroupItem>
        </ToggleGroup>

        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-11 shrink-0 sm:h-9 sm:w-9"
          onClick={clearThread}
          disabled={!turns.length && !busy}
          aria-label="New chat"
          title="New chat"
        >
          <Plus className="h-5 w-5" />
        </Button>
      </header>

      {mode === "map" ? (
        <div className="relative flex min-h-0 flex-1">
          {mapTurn && wide && (
            <aside className="w-[24rem] shrink-0 border-r border-border bg-background xl:w-[26rem]">{mapPanel("side")}</aside>
          )}
          <div className="relative min-h-0 min-w-0 flex-1">
            {mapTurn ? (
              <>
                <CitationMap
                  citations={mapTurn.result.citations}
                  edges={mapTurn.result.edges}
                  focus={tour.active ? tour.current?.place ?? null : place?.key ?? null}
                  walking={tour.active}
                  inset={wide ? 0 : sheetH}
                  trail={trail}
                  onSelect={selectPlace}
                  className="h-full rounded-none border-0"
                />
                {!wide && mapPanel("sheet")}
              </>
            ) : (
              <div className="grid h-full place-items-center bg-card p-6 text-center">
                <div className="max-w-sm space-y-3">
                  <MapPin className="mx-auto h-6 w-6 text-muted-foreground" />
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    Ask a question first: the map places every authority the answer cites at the court that decided it.
                  </p>
                  <Button variant="outline" size="sm" onClick={() => setMode("chat")}>
                    Back to the chat
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-smooth motion-reduce:scroll-auto">
            <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
              {!turns.length && !busy && (
                <div className="flex min-h-[calc(100dvh-16rem)] flex-col justify-center py-6">
                  <img
                    src="/logo.svg"
                    alt=""
                    className="h-12 w-12 animate-in fade-in zoom-in-95 duration-500 motion-reduce:animate-none"
                  />
                  <h2 className="mt-5 text-3xl font-semibold tracking-tight animate-in fade-in slide-in-from-bottom-2 duration-500 motion-reduce:animate-none sm:text-4xl">
                    What would you like to research?
                  </h2>
                  <p className="mt-2 max-w-[56ch] text-base leading-relaxed text-muted-foreground animate-in fade-in slide-in-from-bottom-2 duration-500 motion-reduce:animate-none">
                    Four agents split the work and every citation comes from a case they retrieved. You get a short
                    memo, its sources, and a map of where the law sits.
                  </p>
                  <div className="mt-8">
                    <QuestionBank onAsk={(question) => void askQuestion(question)} />
                  </div>
                </div>
              )}

              <div className="space-y-8">
                {turns.map((turn) => {
                  if (turn.role === "user") {
                    return (
                      <div key={turn.id} className="flex justify-end animate-in fade-in slide-in-from-bottom-2 duration-300 motion-reduce:animate-none">
                        <p className="max-w-[85%] whitespace-pre-wrap rounded-3xl bg-secondary px-4 py-2.5 text-base leading-relaxed text-secondary-foreground">
                          {turn.text}
                        </p>
                      </div>
                    );
                  }

                  if (turn.role === "error") {
                    return (
                      <div
                        key={turn.id}
                        role="alert"
                        className="rounded-lg border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-sm"
                      >
                        {turn.text}
                      </div>
                    );
                  }

                  const answer = turn.result.answer || "";
                  const citations = turn.result.citations || [];
                  const pass = turn.result.safeguard?.pass ?? null;
                  const elapsed = typeof turn.result.elapsed_s === "number" ? turn.result.elapsed_s : null;
                  const waking = toRetrieval(turn.result.retrieval)?.engineWaking === true;

                  return (
                    <article
                      key={turn.id}
                      className="min-w-0 animate-in fade-in slide-in-from-bottom-2 duration-500 motion-reduce:animate-none"
                    >
                      <div className="min-w-0">
                      {answer ? (
                        <div className="mt-3">
                          <Memo answer={answer} citations={citations} onCite={(citation) => openSource(citation, turn)} />
                        </div>
                      ) : (
                        <p className="mt-2 text-sm text-muted-foreground">The run recorded no answer.</p>
                      )}
                      {waking && (
                        <p role="status" className="mt-2 text-sm text-muted-foreground">
                          The full search engine was asleep and is waking up, which takes about 1–2 minutes. This
                          answer used the quicker backup search; ask again shortly for the full search.
                        </p>
                      )}

                      <div className="mt-3 flex flex-wrap items-center gap-0.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-11 w-11 text-muted-foreground hover:text-foreground sm:h-9 sm:w-9"
                          onClick={() => void copyAnswer(turn.result.answer || "")}
                          aria-label="Copy the memo"
                          title="Copy the memo"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-11 w-11 text-muted-foreground hover:text-foreground sm:h-9 sm:w-9"
                          onClick={() => {
                            if (narrating) {
                              stopNarration();
                              return;
                            }
                            tour.stop();
                            speak(plainText(turn.result.answer || ""));
                          }}
                          aria-label={narrating ? "Stop reading" : "Read aloud"}
                          title={narrating ? "Stop reading" : "Read aloud"}
                        >
                          {narrating ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-11 w-11 text-muted-foreground hover:text-foreground sm:h-9 sm:w-9"
                          onClick={() => openMap(turn)}
                          aria-label="Show on the map"
                          title="Show on the map"
                        >
                          <MapPin className="h-4 w-4" />
                        </Button>
                        <ExportMenu result={turn.result} runId={turn.runId} onPrint={() => setPrinting(turn)} />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-11 w-11 text-muted-foreground hover:text-foreground sm:h-9 sm:w-9"
                          onClick={() => setActions(turn)}
                          aria-label="Answer tools"
                          title="Answer tools"
                        >
                          <PanelRight className="h-4 w-4" />
                        </Button>
                        <span className="ml-auto flex items-center gap-2 pl-2 text-xs text-muted-foreground">
                        <CheckPopover safeguard={turn.result.safeguard} citations={citations.length} />
                        {elapsed !== null && (
                          <span className="inline-flex items-center gap-1 tabular-nums" title="Time to answer">
                            <Clock className="h-3.5 w-3.5" />
                            {seconds(elapsed)}
                          </span>
                        )}
                      </span>
                      </div>
                      </div>
                    </article>
                  );
                })}

                {busy && progress && (
                  <section aria-label="Run progress" className="rounded-xl border border-border bg-card p-3.5">
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground motion-reduce:animate-none" />
                      <p role="status" className="text-sm font-medium">
                        {progress.stage}
                      </p>
                      {progress.detail && (
                        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{progress.detail}</span>
                      )}
                    </div>
                    <ol className="mt-3 grid gap-2 sm:grid-cols-2">
                      {progress.stages.map((stage) => (
                        <StageRow key={stage.name} stage={stage} />
                      ))}
                    </ol>
                    {progress.draft && (
                      <div className="mt-3 border-t border-border pt-2.5">
                        <p className="text-xs text-muted-foreground">Draft, as it is written</p>
                        <div className="mt-1 max-h-64 overflow-hidden">
                          <Memo answer={progress.draft} citations={[]} collapsible={false} />
                        </div>
                      </div>
                    )}
                  </section>
                )}
              </div>
            </div>
          </div>

          <div className="shrink-0 bg-gradient-to-t from-background via-background to-transparent px-4 pb-4 pt-2 sm:px-6">
            <form
              className="mx-auto w-full max-w-3xl"
              onSubmit={(event) => {
                event.preventDefault();
                submit();
              }}
            >
              <div className="flex items-end gap-2 rounded-[28px] border border-border bg-card py-2 pl-5 pr-2 shadow-lg transition-shadow duration-200 focus-within:shadow-xl focus-within:ring-2 focus-within:ring-ring motion-reduce:transition-none">
                <textarea
                  ref={inputRef}
                  aria-label="Ask a question"
                  rows={1}
                  onFocus={() => warmEngine("focus")}
                  value={draft}
                  onChange={(event) => {
                    setDraft(event.target.value);
                    const element = event.currentTarget;
                    element.style.height = "auto";
                    element.style.height = `${Math.min(160, element.scrollHeight)}px`;
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submit();
                    }
                  }}
                  placeholder={turns.length ? "Ask a follow-up question…" : "Ask a legal question…"}
                  className="max-h-40 min-h-[2.25rem] min-w-0 flex-1 resize-none bg-transparent px-2 py-1.5 text-base leading-relaxed text-foreground placeholder:text-muted-foreground focus-visible:outline-none"
                />
                <Button type="submit" size="icon" className="h-11 w-11 shrink-0 rounded-full transition-transform duration-150 active:scale-95 motion-reduce:transition-none" disabled={busy || !draft.trim()} aria-label="Send question">
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
                </Button>
              </div>
              <p className="mt-2 px-1 text-center text-xs text-muted-foreground">
                {corpus === "sample"
                  ? "Offline demo: these answers come from a bundled sample, not live case law."
                  : "AI-generated research summary, not legal advice."}
                {narrationStatus === "unavailable" ? " The voice is unavailable here, so the memo stays in text." : ""}
              </p>
            </form>
          </div>
          </div>
          {wide && sourcePane && (
            <aside className="w-[26rem] shrink-0 border-l border-border xl:w-[30rem]">{sourcePane}</aside>
          )}
        </div>
      )}

      {!wide && (
        <Sheet open={!!sourcePane} onOpenChange={(open) => !open && setSource(null)}>
          <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-lg">
            <SheetTitle className="sr-only">Source</SheetTitle>
            {sourcePane}
          </SheetContent>
        </Sheet>
      )}

      {printing && <PrintReport result={printing.result} runId={printing.runId} />}

      <DetailDrawer
        open={authority !== null}
        onOpenChange={(open) => {
          if (!open) setAuthority(null);
        }}
        title={authority?.title || authority?.citation || "Authority"}
        description={authority ? citeType(authority) : undefined}
      >
        {authority && (
          <AuthorityDetail
            citation={authority}
            onAsk={(question) => {
              setAuthority(null);
              void askQuestion(question);
            }}
          />
        )}
      </DetailDrawer>

      <DetailDrawer
        open={sources !== null}
        onOpenChange={(open) => {
          if (!open) setSources(null);
        }}
        title="Sources"
        description={
          sources?.length ? `${sources.length} authorities behind this answer` : "No authority behind this answer"
        }
      >
        {sources?.length ? (
          <EvidenceList
            citations={sources}
            onOpen={(citation) => {
              setSources(null);
              openSource(citation);
            }}
          />
        ) : (
          <p className="text-sm text-muted-foreground">This answer cited no authority.</p>
        )}
      </DetailDrawer>

      <DetailDrawer
        open={followUps !== null}
        onOpenChange={(open) => {
          if (!open) setFollowUps(null);
        }}
        title="Follow-ups"
        description="Asked with this answer as the previous run, so the agents keep its context"
      >
        <ul className="space-y-1.5">
          {(followUps || []).map((item) => (
            <li key={item}>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setFollowUps(null);
                  void askQuestion(item);
                }}
                className="flex w-full items-start gap-2 rounded-lg border border-border bg-card px-2.5 py-2 text-left text-sm leading-relaxed transition-colors hover:bg-accent/60 disabled:opacity-50"
              >
                <CornerDownRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0">{item}</span>
              </button>
            </li>
          ))}
        </ul>
      </DetailDrawer>

      <DetailDrawer
        open={details !== null}
        onOpenChange={(open) => {
          if (!open) setDetails(null);
        }}
        title="Behind this answer"
        description={details ? `Run ${details.runId}` : undefined}
      >
        {details && (
          <TurnDetails
            result={details.result}
            onShowMap={() => {
              const turn = details;
              setDetails(null);
              openMap(turn);
            }}
          />
        )}
      </DetailDrawer>

      {/* Everything the answer can be turned into, in one drawer: the sources behind it, the questions it
          invites, the run's own figures, its voice, its text, and the map of where it sits. */}
      <DetailDrawer
        open={actions !== null}
        onOpenChange={(open) => {
          if (!open) setActions(null);
        }}
        title="Answer tools"
        description={actions ? `Run ${actions.runId}` : undefined}
      >
        {actions && (
          <div className="space-y-1.5">
            <ToolRow
              icon={BookOpen}
              label={`Sources (${(actions.result.citations || []).length})`}
              hint="Every authority this answer cites, with the passage it rests on"
              disabled={!(actions.result.citations || []).length}
              onClick={() => {
                const turn = actions;
                setActions(null);
                setSources(turn.result.citations || []);
              }}
            />
            <ToolRow
              icon={CornerDownRight}
              label={`Follow-ups (${(actions.result.followups || []).length})`}
              hint="Asked with this answer as the previous run, so the agents keep its context"
              disabled={!(actions.result.followups || []).length}
              onClick={() => {
                const turn = actions;
                setActions(null);
                setFollowUps(turn.result.followups || []);
              }}
            />
            <ToolRow
              icon={Gauge}
              label="Details"
              hint="The run's figures, the places it found and the stages it went through"
              onClick={() => {
                const turn = actions;
                setActions(null);
                setDetails(turn);
              }}
            />
            <ToolRow
              icon={narrating ? VolumeX : Volume2}
              label={narrating ? "Stop reading" : "Read aloud"}
              hint={narrating ? "The voice is running now" : "Speak the memo in the browser's own voice"}
              onClick={() => {
                setActions(null);
                if (narrating) {
                  stopNarration();
                  return;
                }
                tour.stop();
                // Markdown read aloud would be "asterisk asterisk" and "[1]"; say the prose.
                speak(plainText(actions.result.answer || ""));
              }}
            />
            <ToolRow
              icon={Copy}
              label="Copy"
              hint="The memo as markdown, ready to paste"
              onClick={() => {
                setActions(null);
                void copyAnswer(actions.result.answer || "");
              }}
            />
            <ToolRow
              icon={MapPin}
              label="Show on the map"
              hint="Place every authority at the court that decided it, and walk them"
              onClick={() => {
                const turn = actions;
                setActions(null);
                openMap(turn);
              }}
            />
          </div>
        )}
      </DetailDrawer>
    </div>
  );
}
