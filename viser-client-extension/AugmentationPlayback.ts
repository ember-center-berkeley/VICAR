/** Small extension to Viser 1.1.1 offline playback: select precomputed task motions.
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
  targetNode?: string;
  displayLift: number;
  shifts: number[][];
  targets?: number[][];
  trajectoryNode?: string;
  trajectories?: number[][][];
  boxNodes?: string[];
  boxLabel?: string;
  curves?: {node: string; points: number[][][]}[];
  layers?: {id: string; label: string; nodes: string[]; default: boolean}[];
  dynamic?: {file: string; frameStride: number; channels: {node: string; property: string; width: number; offset: number}[]};
  axes: Record<string, { min: number; max: number; step: number; default: number; values?: number[] }>;
}

export class AugmentationPlayback {
  index: number;
  showBox = true;
  layers: Record<string, boolean>;
  constructor(public grid: Grid, private rotations: Float32Array, private dynamic?: Float32Array) {
    this.index = grid.defaultIndex;
    this.layers = Object.fromEntries((grid.layers || []).map(layer => [layer.id, layer.default]));
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
    const target = this.grid.targets?.[this.index];
    if (target && this.grid.targetNode) batch.push({ type: "SetPositionMessage", name: this.grid.targetNode, owner: this.grid.owner,
      position: [target[0], target[1], target[2] + this.grid.displayLift] });
    if (this.grid.trajectoryNode && this.grid.trajectories) {
      batch.push({ type: "SceneNodeUpdateMessage", name: this.grid.trajectoryNode, owner: this.grid.owner,
        updates: { points: new Float32Array(this.grid.trajectories[this.index].flat()) } });
    }
    this.grid.boxNodes?.forEach(name => batch.push({ type: "SetSceneNodeVisibilityMessage",
      name, owner: this.grid.owner, visible: this.showBox }));
    this.grid.curves?.forEach(curve => batch.push({type: "SceneNodeUpdateMessage", name: curve.node, owner: this.grid.owner,
      updates: {points: new Float32Array(curve.points[this.index].flat())}}));
    this.grid.layers?.forEach(layer => layer.nodes.forEach(name => batch.push({type: "SetSceneNodeVisibilityMessage",
      name, owner: this.grid.owner, visible: this.layers[layer.id]})));
    if (this.dynamic && this.grid.dynamic) {
      const offset = (this.index * this.grid.frames + frame) * this.grid.dynamic.frameStride;
      this.grid.dynamic.channels.forEach(channel => {
        const values = Array.from(this.dynamic!.subarray(offset + channel.offset, offset + channel.offset + channel.width));
        if (channel.property === "position") batch.push({type: "SetPositionMessage", name: channel.node, owner: this.grid.owner,
          position: values as [number, number, number]});
        else if (channel.property === "wxyz") batch.push({type: "SetOrientationMessage", name: channel.node, owner: this.grid.owner,
          wxyz: values as [number, number, number, number]});
        else batch.push({type: "SceneNodeUpdateMessage", name: channel.node, owner: this.grid.owner,
          updates: {[channel.property]: channel.width === 1 ? values[0] : values}});
      });
    }
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
  const gridUrl = new URL(path, window.location.href).href;
  const notify = (data: object) => window.parent.postMessage({ ...data, gridUrl }, window.location.origin);
  async function load() {
    const url = new URL(path!, window.location.href);
    if (url.origin !== window.location.origin) throw new Error("Augmentation data must be on the same origin.");
    const response = await fetch(url, { signal: abort.signal });
    if (!response.ok) throw new Error("The augmentation grid could not be loaded.");
    const grid: Grid = await response.json();
    async function loadPack(path: string) {
      const packURL = new URL(path, url);
      if (packURL.origin !== url.origin) throw new Error("Invalid augmentation data location.");
      const compressed = await fetch(packURL, { signal: abort.signal });
      if (!compressed.ok || !compressed.body) throw new Error("The motion data could not be loaded.");
      return new Response(compressed.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer();
    }
    const [bytes, dynamicBytes] = await Promise.all([loadPack(grid.quaternions), grid.dynamic ? loadPack(grid.dynamic.file) : undefined]);
    const expected = grid.shifts.length * grid.frames * grid.nodes.length * 4;
    if (grid.frames < 2 || grid.fps <= 0 || grid.nodes.length < 1 || grid.nodes.length > 43 || grid.shifts.length < 1 || bytes.byteLength !== expected * 4) throw new Error("Invalid augmentation data dimensions.");
    if (grid.dynamic && dynamicBytes?.byteLength !== grid.shifts.length * grid.frames * grid.dynamic.frameStride * 4) throw new Error("Invalid object data dimensions.");
    if (disposed) return;
    const playback = new AugmentationPlayback(grid, new Float32Array(bytes), dynamicBytes ? new Float32Array(dynamicBytes) : undefined);
    const publish = (requestId?: unknown) => notify({ type: "vicar:shift-applied", index: playback.index,
      shift: grid.shifts[playback.index], requestId });
    const select = (shift: unknown, requestId?: unknown) => {
      if (!playback.select(shift)) return;
      refresh();
      publish(requestId);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== window.parent) return;
      if (event.data?.type === "vicar:set-shift") {
        if (typeof event.data.showBox === "boolean") playback.showBox = event.data.showBox;
        grid.layers?.forEach(layer => {
          if (typeof event.data.layers?.[layer.id] === "boolean") playback.layers[layer.id] = event.data.layers[layer.id];
        });
        document.documentElement.dataset.hitBoxVisible = String(playback.showBox);
        document.documentElement.dataset.sceneLayers = JSON.stringify(playback.layers);
        select(event.data.shift, event.data.requestId);
      }
    };
    window.addEventListener("message", onMessage);
    removeListener = () => window.removeEventListener("message", onMessage);
    playback.select(grid.shifts[playback.index]);
    setPlayback(playback);
    if (params.get("controls") !== "external") {
      panel = document.createElement("aside");
      panel.setAttribute("aria-label", "Contact shift controls");
      panel.style.cssText = "position:fixed;right:14px;top:14px;width:200px;max-height:calc(100vh - 110px);overflow:auto;padding:16px;background:#ffffffed;border:1px solid #dce3ee;border-radius:10px;z-index:5;font:12px system-ui;color:#25344a;box-shadow:0 3px 16px #22335515";
      const heading = document.createElement("strong"); heading.textContent = grid.shifts.length > 1 ? "Contact shift (m)" : "Scene layers"; panel.append(heading);
      const values = grid.shifts[playback.index].slice();
      const format = (value: number) => value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 5 });
      ["x", "y", "z"].forEach((axis, i) => {
        if (grid.shifts.length === 1) return;
        const label = document.createElement("label"); label.style.cssText = "display:block;margin-top:14px";
        const output = document.createElement("span"); output.style.cssText = "float:right;font-variant-numeric:tabular-nums";
        output.textContent = format(values[i]);
        const input = document.createElement("input"); input.type = "range";
        const settings = grid.axes[axis];
        const samples = settings.values;
        input.min = String(samples ? 0 : settings.min); input.max = String(samples ? samples.length - 1 : settings.max); input.step = String(samples ? 1 : settings.step);
        input.value = String(samples ? samples.indexOf(settings.default) : values[i]); input.setAttribute("aria-label", `${axis.toUpperCase()} contact shift`);
        input.disabled = settings.min === settings.max;
        input.setAttribute("aria-valuetext", `${format(values[i])} metres`);
        input.style.cssText = "display:block;width:100%;margin-top:8px;accent-color:#356fe2";
        input.addEventListener("input", () => {
          values[i] = samples ? samples[Number(input.value)] : Number(input.value);
          output.textContent = format(values[i]); input.setAttribute("aria-valuetext", `${format(values[i])} metres`); select(values);
        });
        label.append(axis.toUpperCase(), output, input); panel!.append(label);
      });
      if (grid.boxNodes?.length) {
        const label = document.createElement("label"); label.style.cssText = "display:block;margin-top:14px";
        const input = document.createElement("input"); input.type = "checkbox"; input.checked = true;
        input.addEventListener("change", () => {
          playback.showBox = input.checked;
          document.documentElement.dataset.hitBoxVisible = String(playback.showBox);
          refresh();
        });
        label.append(input, " " + (grid.boxLabel || "Show hit box")); panel.append(label);
      }
      grid.layers?.forEach(layer => {
        const label = document.createElement("label"); label.style.cssText = "display:block;margin-top:12px";
        const input = document.createElement("input"); input.type = "checkbox"; input.checked = playback.layers[layer.id];
        input.addEventListener("change", () => {
          playback.layers[layer.id] = input.checked;
          document.documentElement.dataset.sceneLayers = JSON.stringify(playback.layers);
          refresh();
        });
        label.append(input, " " + layer.label); panel!.append(label);
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
