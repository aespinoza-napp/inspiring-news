import Link from "next/link";

export type FlowStep = "discover" | "analyze" | "live" | "write" | "reader";

const STEPS: { key: FlowStep; href: string; label: string; hint: string }[] = [
  { key: "discover", href: "/discover", label: "Discover", hint: "Topics → sources → choose up to 20" },
  { key: "analyze", href: "/", label: "Analyze", hint: "Or paste URLs straight in" },
  { key: "live", href: "/live", label: "Follow", hint: "Every run, claim by claim" },
  { key: "write", href: "/drafts", label: "Write", hint: "An article from one that passed" },
  { key: "reader", href: "/reader", label: "Read", hint: "What passed, published" },
];

/**
 * The newsroom's path, drawn the same on each of its pages so they read
 * as one flow rather than five tools: where you are, what comes before
 * and after. Not on the reader itself - that page is for the public,
 * who have no use for the operator's flow.
 *
 * Write comes before Read: an article that passed is already on the
 * reader, and what the newsroom writes from it is published there too
 * (docs/decisions/writing.md).
 */
export function FlowSteps({ current }: { current: FlowStep }) {
  return (
    <ol className="flow-steps" aria-label="Newsroom steps">
      {STEPS.map((step, index) => {
        const active = step.key === current;
        return (
          <li key={step.key} className={active ? "flow-step is-current" : "flow-step"}>
            <Link href={step.href} aria-current={active ? "step" : undefined}>
              <span className="flow-step-number">{index + 1}</span>
              <span className="flow-step-text">
                <span className="flow-step-label">{step.label}</span>
                <span className="flow-step-hint">{step.hint}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
