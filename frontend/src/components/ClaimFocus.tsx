import { ClaimRestatement } from "@/lib/types";

const KIND_LABEL: Record<ClaimRestatement["kind"], string> = {
  fact: "A fact",
  attributed: "Reported speech",
  opinion: "An opinion",
};

/**
 * What a claim is checked *as*, shown before its search: the sentence cut
 * from its article often does not say who is speaking or what exactly is
 * asserted ("Samuda argued Jamaica was different because..."), and a
 * verdict means nothing until that is clear. With restating on
 * (CLAIM_RESTATEMENT=standalone), the backend turns the sentence into one
 * checkable statement - for reported speech, the fact inside the quote -
 * and that is what was searched and judged. Without it, this says the
 * sentence was checked as written.
 */
export function ClaimFocus({ restatement }: { restatement: ClaimRestatement | null | undefined }) {
  if (!restatement) {
    return (
      <div className="trace-block claim-focus is-plain">
        <h4 className="trace-label">What is checked</h4>
        <p className="trace-muted">
          The sentence as the article wrote it, read beside the article&apos;s headline and opening. Restating
          it as a standalone statement first is off (<code>CLAIM_RESTATEMENT=standalone</code> in{" "}
          <code>backend/.env</code>).
        </p>
      </div>
    );
  }

  const { kind, speaker, standalone, checkable, questions, used, note } = restatement;

  return (
    <div className={used ? "trace-block claim-focus" : "trace-block claim-focus is-plain"}>
      <h4 className="trace-label">What is checked</h4>

      <p className="claim-focus-kind">
        <span className={`claim-focus-chip is-${kind}`}>{KIND_LABEL[kind]}</span>
        {speaker && kind !== "fact" && <span className="trace-muted">said by {speaker}</span>}
      </p>

      {used ? (
        <>
          <p className="claim-focus-checkable">{checkable}</p>
          {kind === "attributed" && (
            <p className="trace-muted">
              What is verified is the fact inside the quote, not whether it was said.
            </p>
          )}
          {standalone && standalone !== checkable && (
            <p className="claim-focus-standalone">
              <span className="trace-muted">In full: </span>
              {standalone}
            </p>
          )}
        </>
      ) : (
        <p className="trace-muted">{note ?? "Checked as written."}</p>
      )}

      {questions.length > 0 && (
        <div className="claim-focus-questions">
          <span className="trace-muted">To settle it:</span>
          <ul>
            {questions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
