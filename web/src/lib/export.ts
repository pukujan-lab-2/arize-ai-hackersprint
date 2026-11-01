// What leaves the page: the memo as text for sharing, and as a message for the reader's own mail app.
// Nothing here sends anything. Email is a `mailto:` link, so the reader's mail service opens with the
// message already written and the reader presses send; a PDF cannot ride along in a mail link, so the
// message tells the reader to attach the one they saved.

import { citeType, courtName, type Citation, type RunResult } from "@/lib/citations";
import { plainText } from "@/map/tour";

const DISCLAIMER = "AI-generated research summary, not legal advice.";

/** Where this run can be opened again: the address of the page with the run named in it. */
export function runLink(runId: string): string {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  if (runId) url.searchParams.set("run", runId);
  return url.toString();
}

/** The first few sentences of the memo, cut at a sentence so it never ends mid-thought. */
export function summaryOf(result: RunResult, limit = 600): string {
  const prose = plainText(result.answer || "").replace(/^short answer:\s*/i, "");
  if (prose.length <= limit) return prose;
  const cut = prose.slice(0, limit);
  const stop = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("? "));
  return (stop > limit / 2 ? cut.slice(0, stop + 1) : cut.replace(/\s+\S*$/, "") + "…").trim();
}

function authorityLine(citation: Citation, index: number): string {
  const ref = (citation.ref || `[${index + 1}]`).trim();
  const title = citation.title || citation.citation || "Authority";
  const where = [courtName(citation), citation.date].filter(Boolean).join(", ");
  return `${ref} ${title}${where ? ` (${citeType(citation)}, ${where})` : ""}`;
}

/** The memo as plain text: question, short answer, and the authorities behind it. */
export function shareText(result: RunResult, link: string, limit = 1800): string {
  const lines = [`Question: ${result.question || "Legal research question"}`, "", summaryOf(result), ""];
  const citations = result.citations || [];
  if (citations.length) {
    lines.push("Authorities:", ...citations.map(authorityLine), "");
  }
  lines.push(`Open the memo: ${link}`, "", DISCLAIMER);
  const text = lines.join("\n");
  return text.length <= limit ? text : text.slice(0, limit - 1).replace(/\s+\S*$/, "") + "…";
}

/** A `mailto:` link that opens the reader's own mail app with the memo written into it. */
export function mailtoHref(result: RunResult, link: string): string {
  const subject = `Precedent research: ${(result.question || "legal research memo").slice(0, 120)}`;
  const body = `${shareText(result, link, 1500)}\n\n(Attach the PDF saved from Precedent for the full memo and opinions.)`;
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
