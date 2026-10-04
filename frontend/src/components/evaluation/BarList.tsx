export interface BarItem {
  key: string;
  label: string;
  value: number;
  /** Shown after the value, e.g. a share. */
  note?: string;
}

/**
 * One series of magnitudes as horizontal bars: one hue, the value
 * printed beside every bar (few rows, so every one is worth a label),
 * and the row label in text, so nothing is told by colour alone.
 */
export function BarList({
  items,
  label,
  unit,
}: {
  items: BarItem[];
  /** Accessible name for the list. */
  label: string;
  unit: [string, string];
}) {
  const max = Math.max(1, ...items.map((item) => item.value));

  return (
    <ul className="eval-bars" aria-label={label}>
      {items.map((item) => {
        const width = (item.value / max) * 100;
        const noun = item.value === 1 ? unit[0] : unit[1];
        return (
          <li key={item.key} className="eval-bar-row" title={`${item.label}: ${item.value} ${noun}`}>
            <span className="eval-bar-label">{item.label}</span>
            <span className="eval-bar-track" aria-hidden="true">
              {item.value > 0 && (
                <span className="eval-bar-fill" style={{ width: `${width}%` }} />
              )}
            </span>
            <span className="eval-bar-value">
              {item.value}
              {item.note && <span className="eval-bar-note"> {item.note}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
