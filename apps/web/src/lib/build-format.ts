/** Format seconds as mm:ss (or h:mm:ss past an hour) for clip timecodes. */
export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Human label for a recognizer model id. */
export function recognizerLabel(model: string): string {
  if (model === "tsm-r50-kinetics400") return "TSM R50 · Kinetics-400";
  return "TSN R50 · Kinetics-400";
}

/** Human label for a segmentation strategy. */
export function strategyLabel(strategy: string): string {
  return strategy === "scene-detect" ? "Scene detect" : "Fixed stride";
}
