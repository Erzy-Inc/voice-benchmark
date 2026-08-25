/**
 * TypeScript SDK — mirrors the Python adapters so JS/TS users can run the same
 * benchmark tracks. Usage:
 *
 *   npx tsx src/ts/run.ts --provider soniox-stt-rt-v5 --dataset core-en-synth-v1
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import WebSocket from "ws";

export interface TranscriptEvent {
  kind: "partial" | "final";
  text: string;
  tMs: number;
}

export abstract class BaseProvider {
  abstract readonly providerId: string;
  abstract readonly displayName: string;
  costPer1kMinUsd?: number;
  requiredEnv: string[] = [];

  abstract connect(): Promise<void>;
  abstract streamAudio(chunk: Buffer): Promise<void>;
  /** Drain events after the utterance; must yield the final transcript. */
  abstract finalize(): AsyncGenerator<TranscriptEvent>;
  abstract close(): Promise<void>;

  isConfigured(): boolean {
    return this.requiredEnv.every((k) => !!process.env[k]);
  }
}

export function normalize(text: string): string {
  const contractions: Record<string, string> = {
    "i'm": "i am", "it's": "it is", "don't": "do not", "can't": "cannot",
    "won't": "will not", "isn't": "is not", "let's": "let us",
  };
  let t = text.normalize("NFKC").toLowerCase();
  for (const [a, b] of Object.entries(contractions)) {
    t = t.replace(new RegExp(`\\b${a}\\b`, "g"), b);
  }
  return t.replace(/[^a-z0-9$%\s]/g, "").replace(/\s+/g, " ").trim();
}

export function wer(ref: string, hyp: string): number | null {
  const r = normalize(ref), h = normalize(hyp);
  if (!r) return null;
  const rw = r.split(" "), hw = h.split(" ");
  const dp: number[][] = Array.from({ length: rw.length + 1 }, () =>
    new Array(hw.length + 1).fill(0),
  );
  for (let i = 0; i <= rw.length; i++) dp[i][0] = i;
  for (let j = 0; j <= hw.length; j++) dp[0][j] = j;
  for (let i = 1; i <= rw.length; i++) {
    for (let j = 1; j <= hw.length; j++) {
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + (rw[i - 1] === hw[j - 1] ? 0 : 1),
      );
    }
  }
  return Math.round((dp[rw.length][hw.length] / rw.length) * 10000) / 10000;
}

const nowMs = () => performance.now();
const CHUNK_MS = 40;

/** Minimal Deepgram Nova-3 adapter — reference implementation. */
export class DeepgramNova3 extends BaseProvider {
  providerId = "deepgram-nova-3";
  displayName = "Deepgram Nova-3";
  costPer1kMinUsd = 4.3;
  requiredEnv = ["DEEPGRAM_API_KEY"];

  private ws!: WebSocket;
  private queue: TranscriptEvent[] = [];
  private waiters: ((e: TranscriptEvent) => void)[] = [];
  private pending: Promise<TranscriptEvent>[] = [];

  async connect(): Promise<void> {
    const url =
      "wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000&channels=1&punctuate=true";
    this.ws = new WebSocket(url, {
      headers: { Authorization: `Token ${process.env.DEEPGRAM_API_KEY}` },
    });
    await new Promise<void>((ok, err) => {
      this.ws.once("open", ok);
      this.ws.once("error", err);
    });
    this.ws.on("message", (raw) => {
      const msg = JSON.parse(String(raw));
      const alt = msg?.channel?.alternatives?.[0]?.transcript ?? "";
      if (!alt) return;
      const kind = msg.speech_final || msg.is_final ? "final" : "partial";
      this.push({ kind, text: alt, tMs: nowMs() });
    });
  }

  private push(e: TranscriptEvent) {
    this.queue.push(e);
    this.waiters.splice(0).forEach((w) => w(e));
  }

  async streamAudio(chunk: Buffer): Promise<void> {
    this.ws.send(chunk);
  }

  async *finalize(): AsyncGenerator<TranscriptEvent> {
    this.ws.send(JSON.stringify({ type: "Finalize" }));
    while (true) {
      if (this.queue.length) yield this.queue.shift()!;
      else {
        const p = new Promise<TranscriptEvent>((r) => this.waiters.push(r));
        this.pending.push(p);
        yield await p;
      }
    }
  }

  async close(): Promise<void> {
    this.ws.close();
  }
}

interface TurnManifest { id: string; audio: string; reference: string }
interface DatasetManifest { id: string; turns: TurnManifest[] }

export async function loadDataset(datasetId: string): Promise<
  { turnId: string; pcm: Buffer; reference: string }[]
> {
  const root = join(process.cwd(), "datasets", datasetId);
  const manifest: DatasetManifest = JSON.parse(
    // manifest is YAML in the Python side; TS reads a compiled JSON twin
    readFileSync(join(root, "manifest.json"), "utf8"),
  );
  return manifest.turns.map((t) => ({
    turnId: t.id,
    pcm: readFileSync(join(root, t.audio)).subarray(44), // strip WAV header
    reference: readFileSync(join(root, t.reference), "utf8").trim(),
  }));
}

async function streamAtRealtimePace(pcm: Buffer, provider: BaseProvider): Promise<void> {
  const chunkSize = 16000 * 2 * (CHUNK_MS / 1000);
  for (let pos = 0; pos < pcm.length; pos += chunkSize) {
    await provider.streamAudio(pcm.subarray(pos, pos + chunkSize));
    await new Promise((r) => setTimeout(r, CHUNK_MS));
  }
}

export async function runProvider(
  provider: BaseProvider,
  datasetId: string,
): Promise<object> {
  const turns = await loadDataset(datasetId);
  const results: object[] = [];
  for (const turn of turns) {
    await provider.connect();
    const audioStart = nowMs();
    let firstToken: number | undefined;
    let finalText = "";
    const drain = (async () => {
      for await (const ev of provider.finalize()) {
        if (ev.kind === "final") finalText += (finalText ? " " : "") + ev.text;
        else if (!firstToken && ev.text.trim()) firstToken = ev.tMs;
      }
    })();
    // Note: full interleaved pump parity with the Python runner lands with the
    // E2E milestone; STT track runs are authoritative from Python today.
    void drain;
    await streamAtRealtimePace(turn.pcm, provider);
    const silenceStart = nowMs();
    let finalized: number | undefined;
    for await (const ev of provider.finalize()) {
      if (ev.kind === "final" && finalized === undefined) finalized = ev.tMs;
      if (!firstToken && ev.text.trim()) firstToken ??= ev.tMs;
    }
    await provider.close();
    results.push({
      turn_id: turn.turnId,
      transcript: finalText.trim(),
      wer: wer(turn.reference, finalText),
      ttft_ms: firstToken ? Math.round(firstToken - audioStart) : null,
      finalize_ms: finalized ? Math.round(finalized - silenceStart) : null,
    });
  }
  const out = {
    provider_id: provider.providerId,
    dataset_id: datasetId,
    started_at_utc: new Date().toISOString(),
    harness_version: "ts-0.1.0",
    turns: results,
  };
  const dir = join(process.cwd(), "results");
  mkdirSync(dir, { recursive: true });
  const path = join(dir, `${provider.providerId}--${datasetId}--${Date.now()}.json`);
  writeFileSync(path, JSON.stringify(out, null, 2));
  console.log(`saved ${path}`);
  return out;
}

// ---- CLI ----
if (process.argv[1]?.endsWith("run.ts")) {
  const args = process.argv.slice(2);
  const get = (k: string, d?: string) => {
    const i = args.indexOf(`--${k}`);
    return i >= 0 ? args[i + 1] : d;
  };
  const registry: Record<string, () => BaseProvider> = {
    "deepgram-nova-3": () => new DeepgramNova3(),
  };
  const pid = get("provider") ?? "deepgram-nova-3";
  const make = registry[pid];
  if (!pid || !make) {
    console.error(`unknown provider '${pid}'. Registered: ${Object.keys(registry)}`);
    process.exit(2);
  }
  const p = make();
  if (!p.isConfigured()) {
    console.error(`missing env: ${p.requiredEnv}`);
    process.exit(2);
  }
  const dataset = get("dataset") ?? "core-en-synth-v1";
  runProvider(p, dataset).then(
    (r) => console.log(JSON.stringify(r, null, 2)),
    (e) => {
      console.error(e);
      process.exit(1);
    },
  );
}
