import { useEffect, useState } from "react";

import { getHealth } from "./api/client";

type ConnectionState = "checking" | "connected" | "unavailable";

const foundations = [
  {
    label: "Evidence first",
    detail: "Every future conclusion will retain its source and version.",
  },
  {
    label: "Deterministic review",
    detail: "AI proposes candidates; published rules decide outcomes.",
  },
  {
    label: "Compatible growth",
    detail: "M1 through M6 will extend the same domain contracts.",
  },
];

function App() {
  const [connection, setConnection] = useState<ConnectionState>("checking");

  useEffect(() => {
    const controller = new AbortController();

    getHealth(controller.signal)
      .then(() => setConnection("connected"))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setConnection("unavailable");
      });

    return () => controller.abort();
  }, []);

  return (
    <main className="shell">
      <nav className="topbar" aria-label="Primary navigation">
        <a className="brand" href="/" aria-label="Code Compliance home">
          <span className="brand-mark">CC</span>
          <span>Code Compliance</span>
        </a>
        <span className={"connection connection--" + connection}>
          <span className="connection-dot" aria-hidden="true" />
          API {connection}
        </span>
      </nav>

      <section className="hero">
        <p className="eyebrow">M0 · Architecture baseline</p>
        <h1>Review building codes with evidence, not guesswork.</h1>
        <p className="hero-copy">
          A traceable foundation for regulations, project facts, deterministic
          rules, and professional review.
        </p>
        <div className="phase">
          <div>
            <span className="phase-label">Current milestone</span>
            <strong>Foundation complete</strong>
          </div>
          <div>
            <span className="phase-label">Next milestone</span>
            <strong>M1 · Walking skeleton</strong>
          </div>
        </div>
      </section>

      <section className="foundations" aria-labelledby="foundation-heading">
        <div>
          <p className="eyebrow">Stable contracts</p>
          <h2 id="foundation-heading">Built to evolve without restarting</h2>
        </div>
        <div className="foundation-grid">
          {foundations.map((foundation, index) => (
            <article className="foundation-card" key={foundation.label}>
              <span className="card-number">0{index + 1}</span>
              <h3>{foundation.label}</h3>
              <p>{foundation.detail}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

export default App;
