import { QualityScores } from "@/lib/types";
import { RadarChart } from "@/components/RadarChart";

const AXES: { key: keyof QualityScores; label: string }[] = [
  { key: "constructiveness", label: "Constructive" },
  { key: "inspirationalScore", label: "Inspiring" },
  { key: "hopefulness", label: "Hopeful" },
  { key: "objectivity", label: "Objective" },
  { key: "societalImpact", label: "Societal" },
  { key: "readability", label: "Readable" },
  { key: "novelty", label: "Novel" },
];

/**
 * The article's seven quality dimensions as one shape instead of seven
 * bars scanned one at a time.
 */
export function QualityRadar({ quality }: { quality: QualityScores }) {
  return (
    <RadarChart
      gradientId="radarFillQuality"
      ariaLabel="Impact and quality scores"
      legendColumns={2}
      axes={AXES.map((axis) => ({
        key: axis.key,
        label: axis.label,
        value: quality[axis.key],
      }))}
    />
  );
}
