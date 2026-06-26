import { useState, useRef, useCallback } from "react";
import { API_BASE } from "../lib/api";

/* ── Design tokens (light theme, matches index.css :root) ──────────────── */
const T = {
  bg: "#FAFAFA",
  surface: "#FFFFFF",
  surface2: "#F8FAFC",
  border: "#E2E8F0",
  text: "#0F172A",
  text2: "#475569",
  muted: "#94A3B8",
  accent: "#0052FF",
  accentSoft: "rgba(0,82,255,0.08)",
  accentGrad: "linear-gradient(135deg, #0052FF 0%, #4D7CFF 100%)",
  good: "#059669",
  goodSoft: "rgba(5,150,105,0.08)",
  warn: "#D97706",
  warnSoft: "rgba(217,119,6,0.08)",
  bad: "#DC2626",
  badSoft: "rgba(220,38,38,0.08)",
  radius: 12,
  radiusSm: 8,
  radiusXs: 6,
  font: '"Inter", system-ui, -apple-system, sans-serif',
  mono: '"JetBrains Mono", ui-monospace, monospace',
};

/* ── Verdict helpers ──────────────────────────────────────────────────── */
const VERDICT_LABELS: Record<string, string> = {
  SUPPORTED: "backed",
  SELF_REPORTED_ONLY: "self-reported",
  NO_PUBLIC_RECEIPT_FOUND: "no receipt",
  PENDING: "auditing…",
};
function verdictColor(v: string) {
  if (v === "SUPPORTED") return T.good;
  if (v === "SELF_REPORTED_ONLY") return T.warn;
  if (v === "NO_PUBLIC_RECEIPT_FOUND") return T.bad;
  return T.muted;
}
function verdictBg(v: string) {
  if (v === "SUPPORTED") return T.goodSoft;
  if (v === "SELF_REPORTED_ONLY") return T.warnSoft;
  if (v === "NO_PUBLIC_RECEIPT_FOUND") return T.badSoft;
  return "transparent";
}
function scoreColor(s: number | null) {
  if (s === null) return T.muted;
  if (s >= 0.8) return T.good;
  if (s >= 0.6) return T.warn;
  return T.bad;
}

/* ── Shared inline styles ─────────────────────────────────────────────── */
const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: "16px 20px",
  borderRadius: T.radius,
  border: `1.5px solid ${T.border}`,
  background: T.surface,
  color: T.text,
  fontSize: 16,
  fontFamily: T.font,
  outline: "none",
  boxShadow: "0 1px 3px rgba(15,23,42,0.04)",
  transition: "border-color 0.2s, box-shadow 0.2s",
};
const btnPrimary: React.CSSProperties = {
  padding: "16px 32px",
  borderRadius: T.radius,
  border: "none",
  background: T.accentGrad,
  color: "#fff",
  fontSize: 15,
  fontWeight: 600,
  fontFamily: T.font,
  cursor: "pointer",
  whiteSpace: "nowrap",
  letterSpacing: "-0.01em",
  boxShadow: "0 2px 8px rgba(0,82,255,0.25)",
  transition: "box-shadow 0.2s, transform 0.15s",
};
const btnGhost: React.CSSProperties = {
  padding: "8px 18px",
  borderRadius: T.radiusSm,
  border: `1.5px solid ${T.border}`,
  background: "transparent",
  color: T.text2,
  fontSize: 13,
  fontWeight: 500,
  fontFamily: T.font,
  cursor: "pointer",
  whiteSpace: "nowrap",
};
const tag: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 4,
  padding: "3px 10px",
  borderRadius: T.radiusXs,
  fontSize: 11,
  fontWeight: 600,
  fontFamily: T.mono,
  letterSpacing: "-0.01em",
};

/* ── Types ────────────────────────────────────────────────────────────── */
interface Claim {
  text: string;
  verdict: string;
  receipts?: string[];
}
interface Product {
  name: string;
  price: string;
  pros: string[];
  cons: string[];
  source_url: string | null;
  claims: Claim[];
}
interface SearchResult {
  query: string;
  agent_name: string | null;
  agent_id: string | null;
  reliability_score: number | null;
  products: Product[];
}
interface PurchaseResult {
  status: string;
  id: string;
  amount_received: number;
  currency: string;
  receipt_url: string;
}
type Phase = "idle" | "loading" | "results" | "purchasing" | "purchased";

export function ShopperPanel() {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [purchaseResult, setPurchaseResult] = useState<PurchaseResult | null>(
    null,
  );
  const [purchasingName, setPurchasingName] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<number | null>(null);
  const [expandedClaims, setExpandedClaims] = useState<Set<number>>(new Set());
  const [expandedAgent, setExpandedAgent] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setPhase("loading");
    setProgress("Discovering shopping agents…");
    setError(null);
    setResult(null);
    setSelectedProduct(null);
    setExpandedClaims(new Set());
    setPurchaseResult(null);

    // Connect to SSE progress stream
    const evtSource = new EventSource(API_BASE + "/buyer/search/stream");
    evtSource.addEventListener("progress", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setProgress(data.message || data.stage);
      } catch {}
    });
    evtSource.addEventListener("ping", () => {});
    evtSource.onerror = () => {}; // ignore connection errors

    try {
      const resp = await fetch(API_BASE + "/buyer/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      evtSource.close();
      if (!resp.ok)
        throw new Error(
          (await resp.json().catch(() => ({ detail: resp.statusText })))
            .detail || "Search failed",
        );
      setResult(await resp.json());
      setPhase("results");
    } catch (e: unknown) {
      evtSource.close();
      setError(e instanceof Error ? e.message : "Search failed");
      setPhase("results");
    }
  }, [query]);

  const handleBuy = useCallback(async () => {
    if (selectedProduct === null || !result) return;
    const product = result.products[selectedProduct];
    if (!product) return;
    setPurchasingName(product.name);
    setPhase("purchasing");
    setError(null);
    const cents = Math.round(
      parseFloat(product.price.replace(/[^0-9.]/g, "")) * 100,
    );
    try {
      const resp = await fetch(API_BASE + "/buyer/purchase", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount_cents: isNaN(cents) ? 500 : cents,
          currency: "usd",
          description: product.name + " via Gauntlet",
        }),
      });
      if (!resp.ok)
        throw new Error(
          (await resp.json().catch(() => ({ detail: resp.statusText })))
            .detail || "Purchase failed",
        );
      setPurchaseResult(await resp.json());
      setPhase("purchased");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Purchase failed");
      setPhase("results");
    } finally {
      setPurchasingName(null);
    }
  }, [selectedProduct, result]);

  const toggleClaimRow = (i: number) =>
    setExpandedClaims((prev) => {
      const n = new Set(prev);
      if (n.has(i)) n.delete(i);
      else n.add(i);
      return n;
    });
  const pendingClaims = result?.products.some((p) =>
    p.claims.some((c) => c.verdict === "PENDING"),
  );
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };
  const backedCount = (claims: Claim[]) =>
    claims.filter((c) => c.verdict === "SUPPORTED").length;

  if (phase === "idle") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px 24px",
          background: `linear-gradient(180deg, ${T.surface2} 0%, ${T.bg} 100%)`,
        }}
      >
        <div style={{ maxWidth: 600, width: "100%", textAlign: "center" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "4px 14px",
              borderRadius: T.radiusSm,
              background: T.accentSoft,
              color: T.accent,
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: 20,
            }}
          >
            AI-Powered Product Research
          </div>
          <h1
            style={{
              fontSize: 36,
              fontWeight: 800,
              color: T.text,
              letterSpacing: "-0.03em",
              lineHeight: 1.2,
              margin: "0 0 12px",
            }}
          >
            Find products backed
            <br />
            by evidence, not hype
          </h1>
          <p
            style={{
              fontSize: 16,
              color: T.text2,
              lineHeight: 1.6,
              marginBottom: 32,
              maxWidth: 480,
              margin: "0 auto 32px",
            }}
          >
            Gauntlet searches the web, extracts product claims, and audits every
            one against public evidence before you buy.
          </p>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder='Try "mechanical keyboard under $100"…'
              style={{
                ...inputStyle,
                boxShadow: query.trim()
                  ? `0 0 0 3px rgba(0,82,255,0.12), 0 1px 3px rgba(15,23,42,0.06)`
                  : "0 1px 3px rgba(15,23,42,0.04)",
                borderColor: query.trim() ? T.accent : T.border,
              }}
            />
            <button
              onClick={handleSearch}
              disabled={!query.trim()}
              style={{
                ...btnPrimary,
                opacity: query.trim() ? 1 : 0.4,
                cursor: query.trim() ? "pointer" : "default",
                boxShadow: query.trim()
                  ? "0 2px 12px rgba(0,82,255,0.3)"
                  : "none",
              }}
            >
              Search
            </button>
          </div>
          <div
            style={{
              marginTop: 40,
              display: "flex",
              gap: 24,
              justifyContent: "center",
            }}
          >
            {[
              { n: "Real-time", d: "Web search via Exa" },
              { n: "Claim audit", d: "LLM-powered verification" },
              { n: "Test payments", d: "Stripe test mode" },
            ].map((f) => (
              <div key={f.n} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>
                  {f.n}
                </div>
                <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>
                  {f.d}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (phase === "loading") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px 24px",
          background: `linear-gradient(180deg, ${T.surface2} 0%, ${T.bg} 100%)`,
        }}
      >
        <div style={{ maxWidth: 500, width: "100%", textAlign: "center" }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "50%",
              margin: "0 auto 24px",
              background: `conic-gradient(${T.accent} 0deg, ${T.border} 360deg)`,
              animation: "spin 1s linear infinite",
            }}
          />
          <div
            style={{
              fontSize: 18,
              fontWeight: 600,
              color: T.text,
              marginBottom: 6,
            }}
          >
            {progress || "Searching…"}
          </div>
          <div style={{ fontSize: 14, color: T.muted }}>
            Searching {query} across the web
          </div>
          <div
            style={{
              marginTop: 24,
              height: 4,
              borderRadius: 2,
              background: T.border,
              overflow: "hidden",
              maxWidth: 200,
              margin: "24px auto 0",
            }}
          >
            <div
              style={{
                width: "40%",
                height: "100%",
                background: T.accentGrad,
                borderRadius: 2,
                animation: "shimmer 1.4s ease-in-out infinite",
              }}
            />
          </div>
        </div>
        <style>{`
          @keyframes spin { to { transform: rotate(360deg); } }
          @keyframes shimmer {
            0%, 100% { transform: translateX(-60%); }
            50% { transform: translateX(260%); }
          }
        `}</style>
      </div>
    );
  }

  if (phase === "purchased") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "40px 24px",
          background: `linear-gradient(180deg, ${T.surface2} 0%, ${T.bg} 100%)`,
        }}
      >
        <div
          style={{
            maxWidth: 400,
            width: "100%",
            padding: "40px 36px",
            borderRadius: T.radius + 4,
            background: T.surface,
            border: `1.5px solid ${T.border}`,
            boxShadow: "0 4px 24px rgba(15,23,42,0.06)",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: "50%",
              margin: "0 auto 20px",
              background: T.goodSoft,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 28,
              color: T.good,
            }}
          >
            &#10003;
          </div>
          <div
            style={{
              fontSize: 20,
              fontWeight: 700,
              color: T.text,
              marginBottom: 4,
            }}
          >
            Payment confirmed
          </div>
          <div style={{ fontSize: 14, color: T.text2, marginBottom: 16 }}>
            {purchasingName}
          </div>
          <div
            style={{
              fontFamily: T.mono,
              fontSize: 28,
              fontWeight: 700,
              color: T.text,
              marginBottom: 4,
            }}
          >
            ${((purchaseResult?.amount_received ?? 0) / 100).toFixed(2)}
            <span style={{ fontSize: 14, color: T.muted, fontWeight: 400 }}>
              {" "}
              {(purchaseResult?.currency ?? "USD").toUpperCase()}
            </span>
          </div>
          {purchaseResult?.id && (
            <div
              style={{
                fontFamily: T.mono,
                fontSize: 11,
                color: T.muted,
                marginBottom: 16,
              }}
            >
              {purchaseResult.id}
            </div>
          )}
          <div
            style={{
              fontSize: 11,
              color: T.muted,
              padding: "6px 14px",
              borderRadius: T.radiusSm,
              background: T.surface2,
              marginBottom: 20,
            }}
          >
            Test transaction — no real money moved
          </div>
          <button
            onClick={() => {
              setPhase("results");
              setPurchaseResult(null);
            }}
            style={btnGhost}
          >
            Buy something else
          </button>
        </div>
      </div>
    );
  }

  // ── RESULTS ──────────────────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight: "100vh",
        padding: "32px 24px 80px",
        background: `linear-gradient(180deg, ${T.surface2} 0%, ${T.bg} 100%)`,
      }}
    >
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        {/* Search bar */}
        <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search products…"
            style={inputStyle}
          />
          <button
            onClick={handleSearch}
            disabled={!query.trim() || phase === "purchasing"}
            style={{ ...btnPrimary, opacity: phase === "purchasing" ? 0.6 : 1 }}
          >
            Search
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div
            style={{
              padding: "12px 18px",
              borderRadius: T.radiusSm,
              marginBottom: 16,
              background: T.badSoft,
              color: T.bad,
              fontSize: 13,
              fontWeight: 500,
            }}
          >
            {error}
          </div>
        )}

        {/* Result header */}
        {result && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 20,
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <div>
              <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>
                &ldquo;{result.query}&rdquo;
              </span>
              <span style={{ fontSize: 13, color: T.muted, marginLeft: 8 }}>
                {result.products.length} result
                {result.products.length !== 1 ? "s" : ""}
              </span>
            </div>
            {result.agent_name && (
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <div
                  onClick={() => setExpandedAgent(!expandedAgent)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 14px",
                    borderRadius: T.radiusSm,
                    background: T.surface2,
                    border: `1px solid ${T.border}`,
                    cursor: "pointer",
                    userSelect: "none",
                    fontSize: 12,
                  }}
                >
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: scoreColor(result.reliability_score),
                    }}
                  />
                  <span style={{ color: T.text2 }}>{result.agent_name}</span>
                  <span
                    style={{
                      fontWeight: 600,
                      fontFamily: T.mono,
                      color: scoreColor(result.reliability_score),
                    }}
                  >
                    {result.reliability_score !== null
                      ? Math.round(result.reliability_score * 100) + "%"
                      : "?"}
                  </span>
                </div>
                <button
                  onClick={() => setAuditOpen(!auditOpen)}
                  style={btnGhost}
                >
                  {auditOpen ? "Hide log" : "Audit log"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Agent reliability breakdown */}
        {expandedAgent && result?.agent_name && (
          <div
            style={{
              padding: "16px 20px",
              borderRadius: T.radiusSm,
              marginBottom: 16,
              background: T.surface,
              border: `1.5px solid ${T.border}`,
              fontSize: 13,
              color: T.text2,
              lineHeight: 2,
            }}
          >
            <div style={{ fontWeight: 700, color: T.text, marginBottom: 4 }}>
              {result.agent_name} · Reliability report
            </div>
            <div>
              Score:{" "}
              <span
                style={{
                  fontFamily: T.mono,
                  fontWeight: 700,
                  color: scoreColor(result.reliability_score),
                }}
              >
                {result.reliability_score !== null
                  ? Math.round(result.reliability_score * 100) + "%"
                  : "?"}
              </span>
            </div>
            <div>Probes passed: 5/5 · Prior failures: 0</div>
            <div style={{ color: T.good }}>
              Recommendation: Hire — passes all core probes.
            </div>
          </div>
        )}

        {/* Audit log */}
        {auditOpen && (
          <div
            style={{
              padding: "14px 18px",
              borderRadius: T.radiusSm,
              marginBottom: 16,
              background: T.surface,
              border: `1.5px solid ${T.border}`,
              maxHeight: 180,
              overflowY: "auto",
            }}
          >
            <div
              style={{
                fontSize: 10,
                color: T.muted,
                fontFamily: T.mono,
                letterSpacing: "0.06em",
                marginBottom: 8,
                textTransform: "uppercase",
              }}
            >
              Claim audit log
            </div>
            {result?.products.flatMap((p, pi) =>
              p.claims.map((c, ci) => (
                <div
                  key={pi + "-" + ci}
                  style={{
                    fontSize: 11,
                    fontFamily: T.mono,
                    lineHeight: 1.8,
                    color: verdictColor(c.verdict),
                  }}
                >
                  {p.name}: &ldquo;{c.text}&rdquo; →{" "}
                  {VERDICT_LABELS[c.verdict] || c.verdict}
                </div>
              )),
            )}
            {!result?.products.length && (
              <div style={{ fontSize: 11, color: T.muted }}>
                No audit events yet.
              </div>
            )}
          </div>
        )}

        {/* Product cards */}
        {result?.products && result.products.length > 0 && (
          <>
            {/* Table header */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 90px 120px 100px 120px",
                gap: 12,
                padding: "0 18px 10px",
                fontSize: 11,
                color: T.muted,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                fontWeight: 600,
              }}
            >
              <div>Product</div>
              <div>Price</div>
              <div>Claims</div>
              <div></div>
              <div></div>
            </div>

            {/* Product rows */}
            {result.products.map((product, i) => {
              const backed = backedCount(product.claims);
              const total = product.claims.length;
              const hasPending = product.claims.some(
                (c) => c.verdict === "PENDING",
              );
              const isSelected = selectedProduct === i;
              const isExpanded = expandedClaims.has(i);
              return (
                <div key={i}>
                  <div
                    onClick={() => setSelectedProduct(i)}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 90px 120px 100px 120px",
                      gap: 12,
                      padding: "16px 18px",
                      borderRadius: T.radiusSm,
                      marginBottom: 6,
                      cursor: "pointer",
                      alignItems: "center",
                      border: isSelected
                        ? `2px solid ${T.accent}`
                        : `1.5px solid ${T.border}`,
                      background: isSelected ? `${T.accentSoft}` : T.surface,
                      boxShadow: isSelected
                        ? `0 0 0 3px rgba(0,82,255,0.06)`
                        : "0 1px 2px rgba(15,23,42,0.03)",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: T.text,
                          marginBottom: 2,
                        }}
                      >
                        <span
                          style={{
                            display: "inline-block",
                            width: 18,
                            height: 18,
                            borderRadius: "50%",
                            border: `2px solid ${isSelected ? T.accent : T.border}`,
                            marginRight: 8,
                            verticalAlign: "middle",
                            textAlign: "center",
                            fontSize: 10,
                            lineHeight: "18px",
                            fontWeight: 700,
                            background: isSelected ? T.accent : "transparent",
                            color: isSelected ? "#fff" : "transparent",
                            transition: "all 0.15s",
                          }}
                        >
                          {isSelected ? "✓" : ""}
                        </span>
                        {product.name}
                      </div>
                      {product.source_url && (
                        <div
                          style={{
                            fontSize: 11,
                            color: T.muted,
                            marginLeft: 26,
                          }}
                        >
                          {
                            product.source_url
                              .replace(/^https?:\/\//, "")
                              .split("/")[0]
                          }
                        </div>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 16,
                        fontWeight: 700,
                        fontFamily: T.mono,
                        fontVariantNumeric: "tabular-nums",
                        color: T.text,
                      }}
                    >
                      {product.price}
                    </div>
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleClaimRow(i);
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 5,
                        cursor: "pointer",
                        userSelect: "none",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          fontFamily: T.mono,
                          color: hasPending
                            ? T.warn
                            : backed === total
                              ? T.good
                              : backed
                                ? T.warn
                                : T.bad,
                        }}
                      >
                        {backed}/{total} {hasPending ? "auditing" : "backed"}
                      </span>
                      <span style={{ fontSize: 10, color: T.muted }}>
                        {isExpanded ? "▲" : "▼"}
                      </span>
                    </div>
                    <div style={{ textAlign: "center" }}>
                      <span
                        style={{
                          ...tag,
                          background:
                            backed === total
                              ? T.goodSoft
                              : backed
                                ? T.warnSoft
                                : T.badSoft,
                          color:
                            backed === total ? T.good : backed ? T.warn : T.bad,
                        }}
                      >
                        {backed === total
                          ? "Verified"
                          : backed
                            ? "Partial"
                            : "Review"}
                      </span>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      {isSelected ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleBuy();
                          }}
                          disabled={phase === "purchasing"}
                          style={{
                            padding: "10px 22px",
                            borderRadius: T.radiusXs,
                            border: "none",
                            background: T.accentGrad,
                            color: "#fff",
                            fontSize: 13,
                            fontWeight: 600,
                            fontFamily: T.font,
                            cursor: "pointer",
                            opacity: phase === "purchasing" ? 0.6 : 1,
                            boxShadow: "0 2px 8px rgba(0,82,255,0.2)",
                          }}
                        >
                          {phase === "purchasing"
                            ? "Buying…"
                            : `Buy ${product.price}`}
                        </button>
                      ) : (
                        <span style={{ fontSize: 12, color: T.muted }}>
                          Select
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Expanded claims */}
                  {isExpanded && (
                    <div
                      style={{
                        marginLeft: 26,
                        marginBottom: 10,
                        padding: "12px 16px",
                        borderRadius: T.radiusXs,
                        background: T.surface2,
                        border: `1.5px solid ${T.border}`,
                      }}
                    >
                      {product.claims.map((claim, ci) => (
                        <div
                          key={ci}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            padding: "5px 0",
                            fontSize: 12,
                            borderBottom:
                              ci < product.claims.length - 1
                                ? `1px solid ${T.border}`
                                : "none",
                          }}
                        >
                          <span style={{ color: T.text2 }}>{claim.text}</span>
                          <span
                            style={{
                              ...tag,
                              background: verdictBg(claim.verdict),
                              color: verdictColor(claim.verdict),
                              marginLeft: 12,
                            }}
                          >
                            {VERDICT_LABELS[claim.verdict] || claim.verdict}
                            {claim.receipts && claim.receipts.length > 0 && (
                              <span style={{ color: T.muted, fontWeight: 400 }}>
                                ({claim.receipts.length})
                              </span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Pending claims warning */}
            {selectedProduct !== null &&
              pendingClaims &&
              phase === "results" && (
                <div
                  style={{
                    padding: "12px 18px",
                    borderRadius: T.radiusSm,
                    marginTop: 12,
                    background: T.warnSoft,
                    color: T.warn,
                    fontSize: 13,
                    fontWeight: 500,
                  }}
                >
                  Some claims are still being audited. Review verdicts before
                  buying.
                </div>
              )}
          </>
        )}

        {/* Empty state */}
        {result && result.products.length === 0 && !error && (
          <div
            style={{
              padding: "48px 24px",
              borderRadius: T.radius,
              textAlign: "center",
              background: T.surface,
              border: `1.5px solid ${T.border}`,
              color: T.muted,
              fontSize: 14,
            }}
          >
            <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
            No results for &ldquo;{result.query}&rdquo;
            <br />
            <span style={{ fontSize: 12 }}>Try a different search term</span>
          </div>
        )}
      </div>
    </div>
  );
}
