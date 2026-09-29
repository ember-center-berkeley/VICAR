/** Small extension to Viser 1.1.1 offline playback: select precomputed arm poses.
 * Geometry, camera, playback time, pause and speed remain owned by Viser.
 */
import { Message } from "./WebsocketMessages";

interface Grid {
  frames: number;
  fps: number;
  defaultIndex: number;
  quaternions: string;
  quaternionShape: number[];
  nodes: string[];
  owner: string;
  targetNode: string;
  displayLift: number;
  shifts: number[][];
  targets: number[][];
  axes: Record<string, { min: number; max: number; step: number; default: number }>;
}

export class AugmentationPlayback {
  index: number;
  constructor(public grid: Grid, private rotations: Float32Array) {
    this.index = grid.defaultIndex;
  }

  select(shift: unknown): boolean {
    if (!Array.isArray(shift) || shift.length !== 3 || !shift.every(Number.isFinite)) return false;
    if (["x", "y", "z"].some((axis, i) => shift[i] < this.grid.axes[axis].min - 1e-6 || shift[i] > this.grid.axes[axis].max + 1e-6)) return false;
    let bestDistance = Infinity;
    this.grid.shifts.forEach((candidate, index) => {
      const distance = candidate.reduce((sum, value, i) => sum + (value - shift[i]) ** 2, 0);
      if (distance < bestDistance) { bestDistance = distance; this.index = index; }
    });
    document.documentElement.dataset.augmentationIndex = String(this.index);
    return true;
  }

  apply(time: number, batch: Message[]) {
    const frame = Math.min(this.grid.frames - 1, Math.max(0, Math.floor((time + 1e-7) * this.grid.fps)));
    const start = (this.index * this.grid.frames + frame) * this.grid.nodes.length * 4;
    this.grid.nodes.forEach((name, j) => {
      const offset = start + j * 4;
      batch.push({ type: "SetOrientationMessage", name, owner: this.grid.owner,
        wxyz: Array.from(this.rotations.subarray(offset, offset + 4)) as [number, number, number, number] });
    });
    const target = this.grid.targets[this.index];
    batch.push({ type: "SetPositionMessage", name: this.grid.targetNode, owner: this.grid.owner,
      position: [target[0], target[1], target[2] + this.grid.displayLift] });
  }
}

/** Attach only for an augmentationPath URL. Return cleanup for React's effect. */
export function attachAugmentation(
  setPlayback: (playback: AugmentationPlayback | null) => void,
  refresh: () => void,
): () => void {
  const params = new URLSearchParams(window.location.search);
  const path = params.get("augmentationPath");
  if (!path) return () => {};
  let disposed = false;
  const abort = new AbortController();
  let removeListener = () => {};
  let panel: HTMLElement | null = null;
  const notify = (data: object) => window.parent.postMessage(data, window.location.origin);
  async function load() {
    const url = new URL(path!, window.location.href);
    if (url.origin !== window.location.origin) throw new Error("Augmentation data must be on the same origin.");
    const response = await fetch(url, { signal: abort.signal });
    if (!response.ok) throw new Error("The augmentation grid could not be loaded.");
    const grid: Grid = await response.json();
    const rotationsURL = new URL(grid.quaternions, url);
    if (rotationsURL.origin !== url.origin) throw new Error("Invalid augmentation data location.");
    const compressed = await fetch(rotationsURL, { signal: abort.signal });
    if (!compressed.ok || !compressed.body) throw new Error("The motion data could not be loaded.");
    const bytes = await new Response(compressed.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
    const expected = grid.shifts.length * grid.frames * grid.nodes.length * 4;
    if (grid.frames < 2 || grid.fps <= 0 || grid.nodes.length !== 7 || grid.shifts.length !== 729 || bytes.byteLength !== expected * 4) throw new Error("Invalid augmentation data dimensions.");
    if (disposed) return;
    const playback = new AugmentationPlayback(grid, new Float32Array(bytes));
    const publish = (requestId?: unknown) => notify({ type: "vicar:shift-applied", index: playback.index,
      shift: grid.shifts[playback.index], requestId });
    const select = (shift: unknown, requestId?: unknown) => {
      if (!playback.select(shift)) return;
      refresh();
      publish(requestId);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== window.parent) return;
      if (event.data?.type === "vicar:set-shift") select(event.data.shift, event.data.requestId);
    };
    window.addEventListener("message", onMessage);
    removeListener = () => window.removeEventListener("message", onMessage);
    playback.select(grid.shifts[playback.index]);
    setPlayback(playback);
    if (params.get("controls") !== "external") {
      panel = document.createElement("aside");
      panel.setAttribute("aria-label", "Contact shift controls");
      panel.style.cssText = "position:fixed;right:14px;top:14px;width:200px;padding:16px;background:#ffffffed;border:1px solid #dce3ee;border-radius:10px;z-index:5;font:12px system-ui;color:#25344a;box-shadow:0 3px 16px #22335515";
      const heading = document.createElement("strong"); heading.textContent = "Contact shift (m)"; panel.append(heading);
      const values = grid.shifts[playback.index].slice();
      ["x", "y", "z"].forEach((axis, i) => {
        const label = document.createElement("label"); label.style.cssText = "display:block;margin-top:14px";
        const output = document.createElement("span"); output.style.cssText = "float:right;font-variant-numeric:tabular-nums";
        output.textContent = values[i].toFixed(2);
        const input = document.createElement("input"); input.type = "range";
        input.min = String(grid.axes[axis].min); input.max = String(grid.axes[axis].max); input.step = String(grid.axes[axis].step);
        input.value = String(values[i]); input.setAttribute("aria-label", `${axis.toUpperCase()} contact shift`);
        input.style.cssText = "display:block;width:100%;margin-top:8px;accent-color:#356fe2";
        input.addEventListener("input", () => { values[i] = Number(input.value); output.textContent = values[i].toFixed(2); select(values); });
        label.append(axis.toUpperCase(), output, input); panel!.append(label);
      });
      document.body.append(panel);
    }
    notify({ type: "vicar:augmentation-ready" });
    publish();
  }
  load().catch(error => {
    if (disposed) return;
    notify({ type: "vicar:augmentation-error", message: String(error.message || error) });
    panel = document.createElement("div"); panel.setAttribute("role", "alert");
    panel.textContent = "The augmentation data could not be loaded. Reload the viewer to try again.";
    panel.style.cssText = "position:fixed;top:12px;left:12px;right:12px;padding:16px;background:#fff3e8;color:#713f12;z-index:6;font:13px system-ui";
    document.body.append(panel);
  });
  return () => { disposed = true; abort.abort(); removeListener(); panel?.remove(); setPlayback(null); };
}
