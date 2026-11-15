import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API_BASE = `http://${window.location.hostname}:8000`;

type Provenance = { source: "stated" | "inferred" | "defaulted"; evidence: string };
type Stage = { name: string; ms: number };
type AgentView = {
  agent_id: string;
  name: string;
  version: number;
  business_context: string;
  agent_goal: string;
  persona: string;
  opening_line: string;
  closing_line: string;
  system_prompt: string;
  language_policy: {
    primary: string;
    allowed: string[];
    switch_rule: string;
    per_language_voice: Record<string, string>;
  };
  voice: { model: string; voice: string; language: string; speed: number };
  stt: { model: string; language_code: string; format: string };
  responsibilities: string[];
  knowledge: { question_variants: string[]; answer: string }[];
  actions: { name: string; description: string }[];
  escalation: string[];
  prohibitions: string[];
  limits: { max_turns: number; max_session_s: number; idle_s: number };
  provenance: Record<string, Provenance>;
  unsupported: { request: string; reason: string; alternative: string }[];
  open_questions: { field: string; question: string; default: string }[];
  lint_issues: string[];
  compile_stages: Stage[];
};
type Turn = { role: "user" | "assistant"; content: string };
type Ledger = { calls: number; successful_calls: number; estimated_inr: number | null; unpriced_calls: number };
type Verdict = {
  scenario_id: string;
  persona: string;
  result: "pass" | "fail";
  reason: string;
  evidence_turn: string;
};
type Report = {
  version_id: string;
  summary: string;
  before_verdicts: Verdict[];
  verdicts: Verdict[];
  repairs: { round: number; reason: string; before: string; after: string; patch: { op: string; path: string; value: string }[] }[];
};
type VoiceEcho = {
  transcript: string;
  detected_language_code?: string;
  stt_latency_seconds?: number;
  total_latency_seconds?: number;
  audio_base64: string;
  audio_chunks?: string[];
  tts_cached?: boolean;
  tts_model?: string;
  ledger: Ledger;
};
type VoiceTurn = VoiceEcho & {
  reply: string;
  llm_latency_seconds?: number;
  handoff: boolean;
};

const EXAMPLE_REQUEST =
  "Mere kapde ki dukaan ke liye ek customer support agent banao. Orders aur return policy handle karo, gusse wale customers ko politely handle karna, aur mushkil cases human ko dena. Demo orders ORD-1001 se ORD-1010 tak hain.";

const KNOWN_STAGES = [
  "Extract requirements",
  "Negotiate capabilities",
  "Write agent copy",
  "Voice-readiness lint",
];

function chunksOf(payload: { audio_chunks?: string[]; audio_base64: string }): string[] {
  return payload.audio_chunks?.length ? payload.audio_chunks : [payload.audio_base64];
}

async function playChunks(chunks: string[]): Promise<void> {
  for (const chunk of chunks) {
    if (!chunk) continue;
    const binary = atob(chunk);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "audio/wav" }));
    await new Promise<void>((resolve) => {
      const audio = new Audio(url);
      const finish = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.onended = finish;
      audio.onerror = finish;
      void audio.play().catch(finish);
    });
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error(
      `Hatch cannot reach the backend at ${API_BASE}. Start it with "python scripts/dev.py", then retry. Your text stays in the box.`,
    );
  }
  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }
  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") throw new Error(detail);
    if (detail && typeof detail === "object" && typeof (detail as { message?: unknown }).message === "string") {
      throw new Error(String((detail as { message: string }).message));
    }
    throw new Error(`The request failed (HTTP ${response.status}). Text input still works.`);
  }
  return payload as T;
}

function useRecorder(onClip: (clip: Blob) => void, onError: (message: string) => void) {
  const [recording, setRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const frame = useRef<number | null>(null);
  const timer = useRef<number | null>(null);

  function cleanup() {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    if (context.current) void context.current.close();
    context.current = null;
    setLevel(0);
  }

  useEffect(() => () => cleanup(), []);

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      onError("This browser cannot record audio. Type your request instead.");
      return;
    }
    try {
      const activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = activeStream;
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find((candidate) =>
        MediaRecorder.isTypeSupported(candidate),
      );
      const activeRecorder = mimeType ? new MediaRecorder(activeStream, { mimeType }) : new MediaRecorder(activeStream);
      chunks.current = [];
      activeRecorder.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      activeRecorder.onstop = () => {
        const clip = new Blob(chunks.current, { type: activeRecorder.mimeType || "audio/webm" });
        cleanup();
        if (clip.size) onClip(clip);
      };
      recorder.current = activeRecorder;
      activeRecorder.start();
      setSeconds(0);
      setRecording(true);
      timer.current = window.setInterval(() => setSeconds((value) => value + 1), 1000);

      const AudioCtx =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioContext = new AudioCtx();
      context.current = audioContext;
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      audioContext.createMediaStreamSource(activeStream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (const value of data) {
          const centred = (value - 128) / 128;
          sum += centred * centred;
        }
        const rms = Math.sqrt(sum / data.length);
        setLevel(Math.min(100, Math.round(rms * 260)));
        frame.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      cleanup();
      setRecording(false);
      onError("Microphone access was denied or is unavailable. Allow microphone access, or type your request below.");
    }
  }

  function stop() {
    if (recorder.current?.state === "recording") {
      recorder.current.stop();
      setRecording(false);
    }
  }

  return { recording, level, seconds, start, stop };
}

function clock(value: number): string {
  const minutes = Math.floor(value / 60).toString().padStart(2, "0");
  const rest = (value % 60).toString().padStart(2, "0");
  return `${minutes}:${rest}`;
}

function LevelMeter({ level, active }: { level: number; active: boolean }) {
  return (
    <div className={`level ${active ? "active" : ""}`} aria-hidden="true">
      {Array.from({ length: 18 }, (_, index) => {
        const shape = 0.35 + ((index * 7) % 10) / 12;
        const height = active ? Math.max(6, Math.min(100, level * shape)) : 6;
        return <span key={index} style={{ height: `${height}%` }} />;
      })}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="banner error" role="alert">
      <strong>We hit a snag.</strong>
      <span>{message}</span>
      <small>Text input stays available below.</small>
    </div>
  );
}

function ProvenanceBadge({ field, value }: { field: string; value: Provenance }) {
  return (
    <span className={`badge ${value.source}`} title={value.evidence}>
      {field.replaceAll("_", " ")} · {value.source}
    </span>
  );
}

function Stepper({ stages, working }: { stages: Stage[]; working: boolean }) {
  const timing = new Map(stages.map((stage) => [stage.name, stage.ms]));
  return (
    <ol className="stepper" aria-label="Compile stages">
      {KNOWN_STAGES.map((name, index) => {
        const ms = timing.get(name);
        const done = ms !== undefined;
        const active = working && !done && index === stages.length;
        return (
          <li key={name} className={done ? "done" : active ? "active" : "pending"}>
            <span className="dot">{done ? "✓" : index + 1}</span>
            <span>{name}</span>
            <small>{done ? `${Math.round(ms ?? 0)} ms` : active ? "working" : "waiting"}</small>
          </li>
        );
      })}
    </ol>
  );
}

function TestReportView({ report }: { report: Report }) {
  const beforePassed = report.before_verdicts.filter((verdict) => verdict.result === "pass").length;
  const afterPassed = report.verdicts.filter((verdict) => verdict.result === "pass").length;
  return (
    <section className="report" aria-labelledby="report-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Text-mode test report · {report.version_id}</p>
          <h3 id="report-title">{report.summary}</h3>
        </div>
        <div className="score">
          <span>{beforePassed}/{report.before_verdicts.length || report.verdicts.length} before</span>
          <strong>{afterPassed}/{report.verdicts.length} after</strong>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Scenario</th><th>Persona</th><th>Result</th><th>Reason and evidence</th></tr>
          </thead>
          <tbody>
            {report.verdicts.map((verdict) => (
              <tr key={verdict.scenario_id} className={verdict.result}>
                <td>{verdict.scenario_id.replaceAll("-", " ")}</td>
                <td>{verdict.persona || "Simulated caller"}</td>
                <td><span className={`verdict-pill ${verdict.result}`}>{verdict.result}</span></td>
                <td>
                  <p>{verdict.reason}</p>
                  <blockquote>{verdict.evidence_turn}</blockquote>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {report.repairs.map((repair) => (
        <details className="repair" key={repair.round}>
          <summary>Repair round {repair.round}: {repair.reason}</summary>
          <div className="diff">
            <div><strong>Before</strong><pre>{repair.before}</pre></div>
            <div><strong>After</strong><pre>{repair.after}</pre></div>
          </div>
        </details>
      ))}
      {report.repairs.length === 0 && <p className="muted">No repair was needed on this run. The loop stays armed for future failures.</p>}
    </section>
  );
}

function SpecView({
  agent,
  onTest,
  testing,
  report,
  onScrollToTalk,
}: {
  agent: AgentView;
  onTest: () => void;
  testing: boolean;
  report: Report | null;
  onScrollToTalk: () => void;
}) {
  const keyFields = [
    "business_context",
    "agent_goal",
    "responsibilities",
    "escalation",
    "prohibitions",
    "languages",
    "voice",
    "stt",
  ];
  return (
    <section className="card spec" aria-labelledby="spec-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Step 3 · Compiled agent spec</p>
          <h2 id="spec-title">{agent.name}</h2>
          <p className="muted">{agent.persona}</p>
        </div>
        <span className="status-chip">Lint {agent.lint_issues.length ? `${agent.lint_issues.length} notes` : "clean"}</span>
      </div>

      <div className="badges">
        {keyFields.map((field) =>
          agent.provenance[field] ? <ProvenanceBadge key={field} field={field} value={agent.provenance[field]} /> : null,
        )}
      </div>

      <div className="spec-grid">
        <div>
          <small>Goal</small>
          <p>{agent.agent_goal || agent.business_context}</p>
        </div>
        <div>
          <small>Languages</small>
          <p>{agent.language_policy.allowed.join(" · ")}</p>
        </div>
        <div>
          <small>Voice</small>
          <p>{agent.voice.voice} · {agent.voice.model} · {agent.voice.language}</p>
        </div>
        <div>
          <small>Speech in</small>
          <p>{agent.stt.model} · {agent.stt.language_code} · {agent.stt.format}</p>
        </div>
        <div>
          <small>Session</small>
          <p>{agent.limits.max_turns} turns · {Math.round(agent.limits.max_session_s / 60)} min</p>
        </div>
        <div>
          <small>Opening</small>
          <p>{agent.opening_line}</p>
        </div>
      </div>

      <div className="spec-columns">
        <div>
          <small>Responsibilities</small>
          {agent.responsibilities.length ? (
            <ul>{agent.responsibilities.map((item) => <li key={item}>{item}</li>)}</ul>
          ) : <p className="muted">None stated. Defaults are visible in the badges.</p>}
          <small>Escalation</small>
          {agent.escalation.length ? (
            <ul>{agent.escalation.map((item) => <li key={item}>{item}</li>)}</ul>
          ) : <p className="muted">Offer a human teammate for unresolved cases.</p>}
        </div>
        <div>
          <small>Policies</small>
          {agent.prohibitions.length ? (
            <ul>{agent.prohibitions.map((item) => <li key={item}>{item}</li>)}</ul>
          ) : <p className="muted">Never invent business facts.</p>}
          {agent.knowledge.length > 0 && (
            <>
              <small>Approved facts</small>
              <ul>{agent.knowledge.map((fact) => <li key={fact.answer}>{fact.answer}</li>)}</ul>
            </>
          )}
        </div>
      </div>

      {agent.open_questions.length > 0 && (
        <div className="questions">
          <p className="eyebrow">Clarifying questions · defaults applied</p>
          {agent.open_questions.map((item) => (
            <div className="question" key={item.field}>
              <span>{item.question}</span>
              <strong>Using: {item.default}</strong>
            </div>
          ))}
          <small>Include an answer in your next description to replace a default.</small>
        </div>
      )}

      {agent.unsupported.length > 0 && (
        <div className="callout">
          <strong>Not supported in this demo</strong>
          {agent.unsupported.map((item) => (
            <p key={item.request}>
              {item.request}: {item.reason} <em>{item.alternative}</em>
            </p>
          ))}
        </div>
      )}

      {agent.lint_issues.length > 0 && (
        <div className="callout soft">
          <strong>Voice-readiness notes</strong>
          <p>{agent.lint_issues.join(" ")}</p>
        </div>
      )}

      <div className="actions">
        <button type="button" className="secondary" onClick={onTest} disabled={testing}>
          {testing ? "Running 7 simulated callers…" : report ? "Re-run simulated callers" : "Run 7 simulated callers"}
        </button>
        <button type="button" onClick={onScrollToTalk}>
          Talk to {agent.name} ↓
        </button>
        <a className="ghost-link" href={`/a/${agent.agent_id}`} target="_blank" rel="noreferrer">
          Direct link (/a/{agent.agent_id.slice(0, 8)}) <span>↗</span>
        </a>
      </div>
      {report && <TestReportView report={report} />}
    </section>
  );
}

function TalkPanel({
  agent,
  ledger,
  onLedgerUpdate,
  onError,
}: {
  agent: AgentView;
  ledger: Ledger | null;
  onLedgerUpdate: (ledger: Ledger) => void;
  onError: (msg: string) => void;
}) {
  const [messages, setMessages] = useState<Turn[]>([
    { role: "assistant", content: agent.opening_line },
  ]);
  const [typed, setTyped] = useState("");
  const [working, setWorking] = useState(false);
  const [handoff, setHandoff] = useState(false);
  const [timing, setTiming] = useState<{ stt?: number; llm?: number; total?: number; cached?: boolean } | null>(null);
  const messagesRef = useRef<Turn[]>(messages);
  messagesRef.current = messages;

  const recorder = useRecorder(
    (clip) => void sendVoice(clip),
    (message) => onError(message),
  );

  async function sendVoice(clip: Blob) {
    setWorking(true);
    onError("");
    try {
      const form = new FormData();
      form.append("audio", clip, "turn.webm");
      form.append("history", JSON.stringify(messagesRef.current));
      const result = await request<VoiceTurn>(`/api/agents/${encodeURIComponent(agent.agent_id)}/voice-turn`, {
        method: "POST",
        body: form,
      });
      setMessages((current) => [
        ...current,
        { role: "user", content: result.transcript },
        { role: "assistant", content: result.reply },
      ]);
      setHandoff(Boolean(result.handoff));
      if (result.ledger) onLedgerUpdate(result.ledger);
      setTiming({
        stt: result.stt_latency_seconds,
        llm: result.llm_latency_seconds,
        total: result.total_latency_seconds,
        cached: result.tts_cached,
      });
      await playChunks(chunksOf(result));
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "The voice turn failed. Type your message instead.");
    } finally {
      setWorking(false);
    }
  }

  async function sendText() {
    const text = typed.trim();
    if (!text) return;
    setTyped("");
    setWorking(true);
    onError("");
    try {
      const result = await request<{ text: string; latency_seconds: number; handoff: boolean }>(
        `/api/agents/${encodeURIComponent(agent.agent_id)}/turn`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, history: messagesRef.current }),
        },
      );
      setMessages((current) => [
        ...current,
        { role: "user", content: text },
        { role: "assistant", content: result.text },
      ]);
      setHandoff(Boolean(result.handoff));
      setTiming({ llm: result.latency_seconds, total: result.latency_seconds });
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "That message failed. Try again.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="card talk" id="talk-section" aria-labelledby="talk-title">
      <div className="section-head">
        <div>
          <p className="eyebrow">Step 4 · Talk</p>
          <h2 id="talk-title">Talk to {agent.name}</h2>
          <p className="muted">Live on Hatch runtime · Powered by Gnani Prisma and Timbre</p>
        </div>
        <span className="status-chip ok">Live at /a/{agent.agent_id.slice(0, 8)}</span>
      </div>

      <div className="notice">
        Synthetic data only. Orders ORD-1001 to ORD-1010 available. Try asking about an order or getting angry to test handoff.
      </div>

      {handoff && (
        <div className="banner handoff" role="status">
          <strong>Human handoff requested</strong>
          <span>A teammate would take over in a connected deployment. The transcript is preserved.</span>
        </div>
      )}

      <div className="call-panel">
        <div className="chat" aria-live="polite">
          {messages.map((turn, index) => (
            <article className={`bubble ${turn.role}`} key={`${index}-${turn.role}`}>
              <span>{turn.role === "user" ? "You" : agent.name}</span>
              <p>{turn.content}</p>
            </article>
          ))}
          {working && <p className="thinking">Hatch is listening and thinking…</p>}
        </div>

        <div className="call-controls">
          <button
            type="button"
            className={`mic ${recorder.recording ? "recording" : ""}`}
            onClick={recorder.recording ? recorder.stop : () => void recorder.start()}
            disabled={working}
            aria-label={recorder.recording ? "Stop recording" : "Push to talk"}
          >
            <span className="mic-icon">{recorder.recording ? "■" : "●"}</span>
            <strong>{recorder.recording ? clock(recorder.seconds) : "Push to talk"}</strong>
            <small>{recorder.recording ? "Tap to send" : "Hindi · Hinglish · English"}</small>
          </button>
          <LevelMeter level={recorder.level} active={recorder.recording} />
        </div>

        <div className="text-turn">
          <label>
            <span className="sr-only">Type a message</span>
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void sendText();
              }}
              placeholder="Or type a message (e.g. Mera order ORD-1004 kahan hai?)…"
            />
          </label>
          <button type="button" className="secondary" disabled={working || !typed.trim()} onClick={() => void sendText()}>
            Send
          </button>
        </div>

        <div className="strip">
          <span className="mono">Latency</span>
          <span>STT {timing?.stt !== undefined ? `${(timing.stt * 1000).toFixed(0)} ms` : "—"}</span>
          <span>LLM {timing?.llm !== undefined ? `${(timing.llm * 1000).toFixed(0)} ms` : "—"}</span>
          <span>Turn {timing?.total !== undefined ? `${timing.total.toFixed(2)} s` : "—"}</span>
          <span>{timing?.cached ? "TTS cached" : "TTS live"}</span>
          <span>₹ {ledger?.estimated_inr !== null && ledger?.estimated_inr !== undefined ? ledger.estimated_inr.toFixed(2) : "—"} est.</span>
        </div>
      </div>
    </section>
  );
}

function HatchApp() {
  const initialAgentId = window.location.pathname.match(/^\/a\/([^/]+)/)?.[1] || null;
  const [description, setDescription] = useState("");
  const [transcript, setTranscript] = useState("");
  const [detected, setDetected] = useState("");
  const [agent, setAgent] = useState<AgentView | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [working, setWorking] = useState(false);
  const [testing, setTesting] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(Boolean(initialAgentId));
  const [error, setError] = useState("");
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [lastLatency, setLastLatency] = useState<number | null>(null);
  const [demoText, setDemoText] = useState("");

  const step = agent && report ? 3 : agent ? 2 : transcript ? 1 : 0;
  const [stageStarted, setStageStarted] = useState<number | null>(null);
  const [tick, setTick] = useState(Date.now());

  useEffect(() => {
    if (!working) return;
    const id = window.setInterval(() => setTick(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [working]);

  useEffect(() => {
    if (!initialAgentId) return;
    let cancelled = false;
    async function loadInitial() {
      try {
        const loaded = await request<AgentView>(`/api/agents/${encodeURIComponent(initialAgentId!)}`);
        if (cancelled) return;
        setAgent(loaded);
        setDescription(loaded.business_context || loaded.agent_goal);
        const loadedReport = await request<Report | null>(
          `/api/agents/${encodeURIComponent(initialAgentId!)}/test-report`,
        ).catch(() => null);
        if (!cancelled && loadedReport) setReport(loadedReport);
        const ledgerSummary = await request<Ledger>("/api/ledger").catch(() => null);
        if (!cancelled && ledgerSummary) setLedger(ledgerSummary);
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load agent.");
      } finally {
        if (!cancelled) setLoadingInitial(false);
      }
    }
    void loadInitial();
    return () => {
      cancelled = true;
    };
  }, [initialAgentId]);

  const recorder = useRecorder(
    (clip) => void transcribeAndCompile(clip),
    (message) => setError(message),
  );

  async function transcribeAndCompile(clip: Blob) {
    setWorking(true);
    setError("");
    setTranscript("");
    setStageStarted(Date.now());
    try {
      const form = new FormData();
      form.append("audio", clip, "turn.webm");
      const result = await request<VoiceEcho>("/api/voice/turn", { method: "POST", body: form });
      setTranscript(result.transcript);
      setDetected(result.detected_language_code || "");
      if (result.ledger) setLedger(result.ledger);
      setLastLatency(result.total_latency_seconds ?? null);
      setDescription(result.transcript);
      await playChunks(chunksOf(result));
      await compileText(result.transcript);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Voice capture failed. Type your request instead.");
      setWorking(false);
    }
  }

  async function compileText(prompt = description) {
    if (prompt.trim().length < 8) {
      setError("Describe the agent in a little more detail, then compile again.");
      return;
    }
    setWorking(true);
    setError("");
    setAgent(null);
    setReport(null);
    setStageStarted(Date.now());
    try {
      const result = await request<AgentView>("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: prompt }),
      });
      setAgent(result);
      setDescription(prompt);
      window.history.pushState({}, "", `/a/${result.agent_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Compilation failed. Text input still works.");
    } finally {
      setWorking(false);
      setStageStarted(null);
    }
  }

  async function runTests() {
    if (!agent) return;
    setTesting(true);
    setError("");
    try {
      const result = await request<Report>(`/api/agents/${encodeURIComponent(agent.agent_id)}/test`, { method: "POST" });
      setReport(result);
      const latest = await request<AgentView>(`/api/agents/${encodeURIComponent(agent.agent_id)}`);
      setAgent(latest);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The simulated callers could not finish. Text still works.");
    } finally {
      setTesting(false);
    }
  }

  async function playDemo() {
    if (!demoText.trim()) return;
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: demoText.trim(), language: "hi-IN" }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        const detail = (payload as { detail?: unknown } | null)?.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : (detail as { message?: string } | null)?.message || "Speech synthesis failed.",
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const player = new Audio(url);
      player.onended = () => URL.revokeObjectURL(url);
      await player.play();
      const summary = await request<Ledger>("/api/ledger");
      setLedger(summary);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Voice preview failed. Text remains available.");
    }
  }

  function startFresh() {
    setAgent(null);
    setReport(null);
    setTranscript("");
    setDescription("");
    setError("");
    window.history.pushState({}, "", "/");
  }

  function scrollToTalk() {
    const el = document.getElementById("talk-section");
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }

  const elapsed = stageStarted ? Math.max(1, Math.round((tick - stageStarted) / 1000)) : 0;

  if (loadingInitial) {
    return (
      <main className="app">
        <header className="topbar">
          <a className="brand" href="/">hatch<span>●</span></a>
          <span className="mono">Hatch runtime · Loading…</span>
        </header>
        <p className="muted" style={{ marginTop: "40px" }}>Loading hatched agent…</p>
      </main>
    );
  }

  return (
    <main className="app">
      <header className="topbar">
        <a className="brand" href="/" onClick={(e) => { e.preventDefault(); startFresh(); }}>
          hatch<span>●</span>
        </a>
        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          {agent && (
            <button type="button" className="ghost-link" onClick={startFresh}>
              ← Compile new agent
            </button>
          )}
          <span className="mono">Hatch runtime · Prisma + Timbre</span>
        </div>
      </header>

      <section className="hero">
        <p className="eyebrow">Voice-agent compiler</p>
        <h1>
          Say it. Hatch it.<br />
          <em>Talk to it.</em>
        </h1>
        <p className="lede">
          Describe the voice agent you need. Hatch compiles a provenance-tracked spec, attacks it with simulated callers,
          repairs what breaks, and gives you a live voice agent.
        </p>
        <div className="notice">Demo uses synthetic data only — do not speak real personal details.</div>
      </section>

      <nav className="steps" aria-label="Single-page flow steps">
        {["1 Speak or type", "2 Compile", "3 Test and repair", "4 Talk"].map((label, index) => (
          <span key={label} className={index === step ? "current" : index < step ? "complete" : ""}>
            <b>{index + 1}</b>
            {label.slice(2)}
          </span>
        ))}
      </nav>

      {/* Step 1: Speak or type */}
      <section className="card capture" aria-labelledby="capture-title">
        <div className="section-head">
          <div>
            <p className="eyebrow">Step 1</p>
            <h2 id="capture-title">Tell Hatch what to build</h2>
          </div>
          <span className="status-chip">{working ? "working" : recorder.recording ? "listening" : "ready"}</span>
        </div>

        <div className="mic-stage">
          <button
            type="button"
            className={`mic ${recorder.recording ? "recording" : ""}`}
            onClick={recorder.recording ? recorder.stop : () => void recorder.start()}
            disabled={working}
            aria-label={recorder.recording ? "Stop recording" : "Start recording"}
          >
            <span className="mic-icon">{recorder.recording ? "■" : "●"}</span>
            <strong>{recorder.recording ? clock(recorder.seconds) : "Tap to speak"}</strong>
            <small>{recorder.recording ? "Tap to stop" : "Hindi · Hinglish · English"}</small>
          </button>
          <div className="meter-wrap">
            <LevelMeter level={recorder.level} active={recorder.recording} />
            <p className="muted">
              {recorder.recording ? "Listening — speak naturally, then tap stop." : "Or use the seeded demo request below."}
            </p>
          </div>
        </div>

        <label className="field">
          <span>Typed request</span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Mere kapde ki dukaan ke liye ek customer support agent banao…"
            rows={4}
          />
        </label>
        <div className="actions">
          <button type="button" onClick={() => void compileText()} disabled={working || description.trim().length < 8}>
            {working ? `Compiling · ${elapsed}s` : "Compile from text"} <span>↗</span>
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setDescription(EXAMPLE_REQUEST);
            }}
            disabled={working}
          >
            Use demo request (Hinglish clothing store)
          </button>
        </div>

        {transcript && (
          <div className="transcript">
            <div className="transcript-head">
              <span className="eyebrow">Prisma transcript</span>
              {detected && <span className="chip">{detected}</span>}
            </div>
            <p>{transcript}</p>
          </div>
        )}
        {lastLatency !== null && <p className="metric">Voice round trip {lastLatency.toFixed(2)}s · Prisma + Timbre</p>}
      </section>

      {/* Step 2: Compile */}
      {(working || agent) && (
        <section className="card compile" aria-labelledby="compile-title">
          <div className="section-head">
            <div>
              <p className="eyebrow">Step 2</p>
              <h2 id="compile-title">{agent ? "Compiled with visible provenance" : "Compiling your agent"}</h2>
            </div>
            {agent && <span className="status-chip ok">spec v{agent.version}</span>}
          </div>
          <Stepper stages={agent?.compile_stages ?? []} working={working} />
          {!agent && (
            <p className="muted">
              Extracting requirements, negotiating Gnani capabilities, writing the spec, and linting voice copy.
            </p>
          )}
        </section>
      )}

      {/* Step 3: Test and repair */}
      {agent && (
        <SpecView
          agent={agent}
          onTest={() => void runTests()}
          testing={testing}
          report={report}
          onScrollToTalk={scrollToTalk}
        />
      )}

      {/* Step 4: Talk */}
      {agent && (
        <TalkPanel
          agent={agent}
          ledger={ledger}
          onLedgerUpdate={(l) => setLedger(l)}
          onError={(m) => setError(m)}
        />
      )}

      {/* Collapsed Diagnostics */}
      <details className="diagnostics">
        <summary>Diagnostics & Speech Preview</summary>
        <p className="muted">Direct Timbre preview and local ledger. Uses real Gnani speech calls.</p>
        <label className="field">
          <span>Test Timbre with a typed phrase</span>
          <textarea
            value={demoText}
            onChange={(event) => setDemoText(event.target.value)}
            rows={2}
            placeholder="Namaste, main Hatch hoon."
          />
        </label>
        <div className="actions">
          <button type="button" className="ghost" onClick={() => void playDemo()} disabled={!demoText.trim()}>
            Play preview
          </button>
        </div>
        <div className="ledger">
          <span>{ledger ? `${ledger.calls} Gnani calls` : "Gnani ledger"}</span>
          <span>
            {ledger?.estimated_inr === null || ledger?.estimated_inr === undefined
              ? "cost estimate pending"
              : `₹${ledger.estimated_inr.toFixed(2)} estimated`}
          </span>
        </div>
        <small>
          Models: Gnani Prisma (speech in) and Timbre (speech out); third-party LLM on Groq for reasoning. Agents run on the Hatch
          runtime, not Gnani Agent Builder.
        </small>
      </details>

      <ErrorBanner message={error} />
      <footer className="footer">
        <span>Hatch · Say it. Hatch it. Talk to it.</span>
        <span>Prisma + Timbre · synthetic data only</span>
      </footer>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<HatchApp />);
