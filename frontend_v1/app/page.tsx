"use client";
import { useState } from "react";
const API = process.env.NEXT_PUBLIC_API || "http://localhost:8000";
export default function Page() {
  const [out, setOut] = useState("Ready");
  const [cid, setCid] = useState("");
  async function create() {
    const r = await fetch(`${API}/api/cases`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Misleading claim", objective: "P1 objective", keywords: ["breaking"], platforms: ["rss", "web"] }) });
    const j = await r.json(); setCid(j.id); setOut(JSON.stringify(j, null, 2));
  }
  return (<main style={{ padding: 24, fontFamily: "sans-serif" }}>
    <h1>OSINT Analyst Dashboard (Next.js)</h1>
    <p>Backend: {API} — full functional dashboard is also served at /dashboard by FastAPI.</p>
    <button onClick={create}>Create case</button>
    <p>Case: {cid}</p><pre>{out}</pre></main>);
}
