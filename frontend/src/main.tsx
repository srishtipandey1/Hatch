import React from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

function App() {
  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/">hatch<span>●</span></a>
        <span className="runtime">HATCH RUNTIME · PREVIEW</span>
      </header>
      <section className="hero">
        <p className="eyebrow">VOICE AGENT COMPILER</p>
        <h1>Say it. Hatch it.<br /><em>Talk to it.</em></h1>
        <p className="intro">Turn a simple description into a tested, voice-ready agent.</p>
        <div className="notice">Demo uses synthetic data only — don't speak real personal details.</div>
        <textarea aria-label="Describe your agent" placeholder="Describe the voice agent you want to create…" />
        <button type="button" disabled>Create agent <span>↗</span></button>
        <small>Prisma speech recognition · Third-party LLM reasoning · Timbre voice</small>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
