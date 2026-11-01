// The memo laid out as a document, for printing and for saving as a PDF: the question, the memo, then
// every authority with the passage the retriever returned and the reference checks that were run on it.
// It is rendered outside the app's own tree, only while a print is under way, and the print styles in
// `globals.css` hide the app and show this, always in black on white whatever the page theme is.

import { createPortal } from "react-dom";
import Memo from "@/components/Memo";
import { citeType, courtName, type RunResult } from "@/lib/citations";
import { sourceReport } from "@/lib/sourcecheck";

const STATE_WORD = { pass: "Passed", fail: "Failed", info: "Note" } as const;

export default function PrintReport({ result, runId }: { result: RunResult; runId: string }) {
  const citations = result.citations || [];
  const date = new Date().toLocaleDateString("en-US", { dateStyle: "long" });

  return createPortal(
    <div className="print-report">
      <header>
        <p className="print-kicker">Precedent · Legal research memo</p>
        <h1>{result.question || "Legal research memo"}</h1>
        <p className="print-meta">
          {date} · Run {runId}
          {result.provider ? ` · Written by ${result.provider}` : ""}
        </p>
      </header>

      <section>
        <h2>Memo</h2>
        <Memo answer={result.answer || ""} citations={citations} collapsible={false} />
      </section>

      {!!citations.length && (
        <section>
          <h2>Authorities ({citations.length})</h2>
          {citations.map((citation, index) => {
            const report = sourceReport(citation, index, result.answer || "", result.safeguard);
            const passage = String(citation.passage || "").trim();
            return (
              <article key={`${citation.id}-${index}`} className="print-authority">
                <h3>
                  {citation.ref || `[${index + 1}]`} {citation.title || citation.citation || "Authority"}
                </h3>
                <p className="print-meta">
                  {[citeType(citation), courtName(citation), citation.citation, citation.date].filter(Boolean).join(" · ")}
                </p>
                {passage ? (
                  <blockquote>{passage}</blockquote>
                ) : (
                  <p className="print-meta">No passage was retrieved; this authority came from the citation graph.</p>
                )}
                <p className="print-checks">
                  {report.checks.map((check) => `${check.label}: ${STATE_WORD[check.state]}`).join(" · ")}
                </p>
              </article>
            );
          })}
        </section>
      )}

      <footer>
        <p>
          {result.safeguard?.disclaimer || "AI-generated research summary, not legal advice."} The checks above test
          references, not legal accuracy or whether the law is current.
        </p>
      </footer>
    </div>,
    document.body,
  );
}
