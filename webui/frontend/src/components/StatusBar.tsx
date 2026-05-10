import { useEffect, useState } from "react";
import { HealthStatus, fetchHealth } from "../api";
import { useDebugMode } from "../hooks/useDebugMode";

type Dot = "green" | "yellow" | "red" | "loading";

function Semaphore({ color, label, title }: { color: Dot; label: string; title: string }) {
  const dot: Record<Dot, string> = {
    green:   "bg-green-500",
    yellow:  "bg-yellow-400",
    red:     "bg-red-500",
    loading: "bg-zinc-600 animate-pulse",
  };
  return (
    <span className="flex items-center gap-1.5" title={title}>
      <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${dot[color]}`} />
      <span className="text-zinc-400">{label}</span>
    </span>
  );
}

function DebugToggle() {
  const [debug, setDebug] = useDebugMode();
  return (
    <label
      className="flex items-center gap-1.5 cursor-pointer text-zinc-500 hover:text-zinc-300 select-none"
      title="When on, expands the live log panel during parse/conversion so you can see all stdout."
    >
      <input
        type="checkbox"
        checked={debug}
        onChange={(e) => setDebug(e.target.checked)}
        className="h-3 w-3 accent-zinc-300 cursor-pointer"
      />
      <span>debug</span>
    </label>
  );
}

export default function StatusBar() {
  const [status, setStatus] = useState<HealthStatus | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchHealth()
      .then(setStatus)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <span className="flex items-center gap-4 text-xs">
        <Semaphore color="red" label="backend unreachable" title="Could not reach /api/health" />
        <DebugToggle />
      </span>
    );
  }

  if (!status) {
    return (
      <span className="flex items-center gap-4 text-xs">
        {["torch", "cuda", "whisper"].map((k) => (
          <Semaphore key={k} color="loading" label={k} title="checking…" />
        ))}
        <DebugToggle />
      </span>
    );
  }

  const torchColor: Dot = status.torch ? "green" : "red";
  const cudaColor: Dot = !status.torch ? "red" : status.cuda ? "green" : "yellow";
  const whisperColor: Dot = status.faster_whisper ? "green" : "red";

  const vramLabel = status.cuda
    ? `${status.vram_free_gb} / ${status.vram_total_gb} GB free`
    : "no GPU";

  return (
    <span className="flex items-center gap-4 text-xs">
      <Semaphore
        color={torchColor}
        label="torch"
        title={status.torch ? "PyTorch installed" : "PyTorch not found"}
      />
      <Semaphore
        color={cudaColor}
        label={status.cuda ? `cuda · ${vramLabel}` : "cpu only"}
        title={status.cuda ? `CUDA available — ${vramLabel}` : "CUDA not available — running on CPU"}
      />
      <Semaphore
        color={whisperColor}
        label="whisper"
        title={status.faster_whisper ? "faster-whisper installed" : "faster-whisper not installed — auto-transcription unavailable"}
      />
      <span className="text-zinc-600">{status.engine_mode}</span>
      <DebugToggle />
    </span>
  );
}
