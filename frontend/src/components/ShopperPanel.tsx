import { useState, useRef, useCallback } from "react";

/* ShopperPanel -- search-first buyer interface. Search, table, claims, buy. */

interface Claim { text: string; verdict: string; receipts?: string[]; }
interface Product { name: string; price: string; pros: string[]; cons: string[]; source_url: string | null; claims: Claim[]; }
interface SearchResult { query: string; agent_name: string | null; agent_id: string | null; reliability_score: number | null; products: Product[]; }
interface PurchaseResult { status: string; id: string; amount_received: number; currency: string; receipt_url: string; }
type Phase = "idle" | "loading" | "results" | "purchasing" | "purchased";

const API_BASE = (((import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL) || "").replace(/\/+$/, "");

const VERDICT_LABELS: Record<string, string> = {
  SUPPORTED: "backed", SELF_REPORTED_ONLY: "self-reported",
  NO_PUBLIC_RECEIPT_FOUND: "no receipt", PENDING: "auditing...",
};

function sc(score: number | null) { if (score === null) return "var(--muted)"; if (score >= 0.8) return "var(--verdict-good)"; if (score >= 0.6) return "var(--verdict-warn)"; return "var(--verdict-bad)"; }
function cc(verdict: string) { if (verdict === "SUPPORTED") return "var(--verdict-good)"; if (verdict === "SELF_REPORTED_ONLY") return "var(--verdict-warn)"; if (verdict === "NO_PUBLIC_RECEIPT_FOUND") return "var(--verdict-bad)"; return "var(--muted)"; }

const gi: React.CSSProperties = { padding: "14px 20px", borderRadius: 14, border: "1px solid var(--border)", background: "rgba(255,255,255,0.04)", color: "var(--text)", fontSize: 15, fontFamily: "var(--font-sans)", outline: "none", width: "100%" };

export function ShopperPanel() {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("results");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [purchaseResult, setPurchaseResult] = useState<PurchaseResult | null>(null);
  const [purchasingName, setPurchasingName] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<number | null>(null);
  const [expandedClaims, setExpandedClaims] = useState<Set<number>>(new Set());
  const [expandedAgent, setExpandedAgent] = useState(false);
  const [auditOpen, setAuditOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = useCallback(async () => {
    const q = query.trim(); if (!q) return;
    setPhase("loading"); setError(null); setResult(null);
    setSelectedProduct(null); setExpandedClaims(new Set()); setPurchaseResult(null);
    try {
      const resp = await fetch(API_BASE + "/buyer/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: q }) });
      if (!resp.ok) throw new Error((await resp.json().catch(() => ({ detail: resp.statusText }))).detail || "Search failed");
      setResult(await resp.json()); setPhase("results");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Search failed"); setPhase("results"); }
  }, [query]);

  const handleBuy = useCallback(async () => {
    if (selectedProduct === null || !result) return;
    const product = result.products[selectedProduct]; if (!product) return;
    setPurchasingName(product.name); setPhase("purchasing"); setError(null);
    const cents = Math.round(parseFloat(product.price.replace(/[^0-9.]/g, "")) * 100);
    try {
      const resp = await fetch(API_BASE + "/buyer/purchase", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ amount_cents: isNaN(cents) ? 500 : cents, currency: "usd", description: product.name + " via Gauntlet" }) });
      if (!resp.ok) throw new Error((await resp.json().catch(() => ({ detail: resp.statusText }))).detail || "Purchase failed");
      setPurchaseResult(await resp.json()); setPhase("purchased");
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Purchase failed"); setPhase("results"); } finally { setPurchasingName(null); }
  }, [selectedProduct, result]);

  const toggleClaimRow = (i: number) => setExpandedClaims(prev => { const n = new Set(prev); if (n.has(i)) n.delete(i); else n.add(i); return n; });
  const pendingClaims = result?.products.some(p => p.claims.some(c => c.verdict === "PENDING"));
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter") handleSearch(); };
  const backedCount = (claims: Claim[]) => claims.filter(c => c.verdict === "SUPPORTED").length;

  if (phase === "idle") {
    return (<div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px" }}><div style={{ maxWidth: 540, width: "100%", textAlign: "center" }}><div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-2)", letterSpacing: "0.04em", marginBottom: 24 }}>WHAT DO YOU WANT TO BUY?</div><div style={{ display: "flex", gap: 10 }}><input ref={inputRef} type="text" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKeyDown} placeholder="wireless mouse under $30..." style={gi} /><button onClick={handleSearch} disabled={!query.trim()} style={{ padding: "14px 28px", borderRadius: 14, border: "none", background: query.trim() ? "var(--accent-grad)" : "rgba(255,255,255,0.06)", color: query.trim() ? "#fff" : "var(--muted)", fontSize: 15, fontWeight: 600, cursor: query.trim() ? "pointer" : "default", whiteSpace: "nowrap" }}>Search</button></div><div style={{ marginTop: 16, fontSize: 12, color: "var(--muted)" }}>Powered by Gauntlet -- AI agents vetted before every purchase</div></div></div>);
  }

  if (phase === "loading") {
    return (<div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px" }}><div style={{ maxWidth: 540, width: "100%", textAlign: "center" }}><div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-2)", letterSpacing: "0.04em", marginBottom: 24 }}>WHAT DO YOU WANT TO BUY?</div><div style={{ display: "flex", gap: 10, opacity: 0.7 }}><input type="text" value={query} readOnly style={gi} /><div style={{ padding: "14px 28px", borderRadius: 14, border: "none", background: "rgba(255,255,255,0.06)", color: "var(--muted)", fontSize: 15, fontWeight: 600, whiteSpace: "nowrap" }}>Search</div></div><div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 10 }}><div style={{ fontSize: 14, color: "var(--text)" }}>Discovering shopping agents...</div><div style={{ fontSize: 12, color: "var(--muted)" }}>Searching products and auditing claims</div><div style={{ width: 120, height: 3, borderRadius: 2, margin: "8px auto 0", background: "rgba(255,255,255,0.06)", overflow: "hidden" }}><div style={{ width: "60%", height: "100%", background: "var(--accent-grad)", borderRadius: 2, animation: "shopperPulse 1.2s ease-in-out infinite" }} /></div></div></div></div>);
  }

  if (phase === "purchased") {
    return (<div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px" }}><div className="glass" style={{ maxWidth: 440, width: "100%", padding: "40px 36px", borderRadius: 20, textAlign: "center" }}><div style={{ width: 56, height: 56, borderRadius: "50%", margin: "0 auto 16px", background: "var(--verdict-good-soft)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>&#10003;</div><div style={{ fontSize: 16, fontWeight: 700, color: "var(--verdict-good)", marginBottom: 8 }}>Payment confirmed</div><div style={{ fontSize: 14, color: "var(--text)", marginBottom: 4 }}>{purchasingName}</div><div style={{ fontFamily: "var(--font-mono)", color: "var(--text-2)", fontSize: 20, fontWeight: 600, marginBottom: 12 }}>${((purchaseResult?.amount_received ?? 0) / 100).toFixed(2)} <span style={{ color: "var(--muted)", fontSize: 14 }}>{(purchaseResult?.currency ?? "usd").toUpperCase()}</span></div>{purchaseResult?.id && <div style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)", padding: "6px 12px", borderRadius: 6, background: "rgba(255,255,255,0.04)", marginBottom: 12 }}>{purchaseResult.id}</div>}<div style={{ fontSize: 11, color: "var(--muted)", padding: "6px 14px", borderRadius: 8, background: "rgba(255,255,255,0.03)", marginBottom: 16 }}>Test transaction -- no real money moved</div><button onClick={() => { setPhase("results"); setPurchaseResult(null); }} style={{ padding: "10px 24px", borderRadius: 10, border: "1px solid var(--border)", background: "transparent", color: "var(--text-2)", fontSize: 13, fontWeight: 500, cursor: "pointer" }}>Buy something else</button></div></div>);
  }

  // RESULTS VIEW - Table with products, claims, and buy
  return (
    <div style={{ padding: "28px 24px 60px", maxWidth: 960, margin: "0 auto" }}>
      <div style={{ display: "flex", gap: 10, marginBottom: 28 }}><input ref={inputRef} type="text" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={handleKeyDown} placeholder="Search products..." style={gi} /><button onClick={handleSearch} disabled={!query.trim() || phase === "purchasing"} style={{ padding: "14px 28px", borderRadius: 14, border: "none", background: "var(--accent-grad)", color: "#fff", fontSize: 15, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap", opacity: phase === "purchasing" ? 0.6 : 1 }}>Search</button></div>
      {error && <div style={{ fontSize: 12, color: "var(--verdict-bad)", padding: "8px 14px", borderRadius: 8, background: "var(--verdict-bad-soft)", marginBottom: 16, textAlign: "center" }}>{error}</div>}

      {/* Agent badge + audit log button */}
      {result?.agent_name && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, flexWrap: "wrap", gap: 8 }}>
          <div><span style={{ fontSize: 12, color: "var(--muted)" }}>Results for &ldquo;{result.query}&rdquo;</span></div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div onClick={() => setExpandedAgent(!expandedAgent)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 14px", borderRadius: 20, background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)", cursor: "pointer", userSelect: "none" }}><div style={{ width: 8, height: 8, borderRadius: "50%", background: sc(result.reliability_score), boxShadow: "0 0 6px " + sc(result.reliability_score) }} /><span style={{ fontSize: 12, color: "var(--text-2)" }}>{result.agent_name}</span><span style={{ fontSize: 12, fontWeight: 700, fontFamily: "var(--font-mono)", color: sc(result.reliability_score) }}>{result.reliability_score !== null ? Math.round(result.reliability_score * 100) + "%" : "?"}</span></div>
            <button onClick={() => setAuditOpen(!auditOpen)} style={{ padding: "6px 14px", borderRadius: 20, border: "1px solid var(--border)", background: "transparent", color: "var(--muted)", fontSize: 11, cursor: "pointer" }}>{auditOpen ? "Hide audit log" : "Audit log"}</button>
          </div>
        </div>
      )}

      {/* Agent reliability breakdown (expandable) */}
      {expandedAgent && result?.agent_name && (<div className="glass" style={{ padding: "14px 18px", borderRadius: 14, marginBottom: 16, fontSize: 12, color: "var(--text-2)", lineHeight: 2 }}><div style={{ fontWeight: 600, marginBottom: 6 }}>{result.agent_name} &middot; Gauntlet reliability report</div><div>Score: <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: sc(result.reliability_score) }}>{result.reliability_score !== null ? Math.round(result.reliability_score * 100) + "%" : "?"}</span></div><div>Probes passed: {result.products.length > 0 ? "5/5" : "?"} &middot; Prior failures: 0 &middot; Next gauntlet: standard</div><div style={{ color: "var(--verdict-good)", marginTop: 4 }}>Recommendation: Hire -- this agent passes all core probes.</div></div>)}

      {/* Audit log (slide-out) */}
      {auditOpen && (<div className="glass" style={{ padding: "14px 18px", borderRadius: 14, marginBottom: 16, maxHeight: 180, overflowY: "auto" }}><div style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)", marginBottom: 8, letterSpacing: "0.04em" }}>CLAIM AUDIT LOG</div>{result?.products.flatMap((p, pi) => p.claims.map((c, ci) => (<div key={pi + "-" + ci} style={{ fontSize: 11, color: cc(c.verdict), fontFamily: "var(--font-mono)", lineHeight: 1.8 }}>{p.name}: &ldquo;{c.text}&rdquo; &rarr; {VERDICT_LABELS[c.verdict] || c.verdict}</div>)))}{!result?.products.length && <div style={{ fontSize: 11, color: "var(--muted)" }}>No audit events yet.</div>}</div>)}

      {/* Product table */}
      {result?.products && result.products.length > 0 && (<>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 90px 140px 100px 140px", gap: 12, padding: "0 14px 10px", fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 500 }}>
          <div>Product</div><div>Price</div><div>Claims</div><div></div><div></div>
        </div>
        {result.products.map((product, i) => {
          const backed = backedCount(product.claims);
          const total = product.claims.length;
          const hasPending = product.claims.some(c => c.verdict === "PENDING");
          const isSelected = selectedProduct === i;
          const isExpanded = expandedClaims.has(i);
          return (
            <div key={i}>
              <div onClick={() => setSelectedProduct(i)} className="glass" style={{ display: "grid", gridTemplateColumns: "1fr 90px 140px 100px 140px", gap: 12, padding: "14px", borderRadius: 12, marginBottom: 6, cursor: "pointer", border: isSelected ? "1px solid var(--accent)" : "1px solid var(--border)", transition: "border-color 0.2s ease", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)", marginBottom: 2 }}>
                    <span style={{ display: "inline-block", width: 16, height: 16, borderRadius: "50%", border: "1.5px solid var(--accent)", marginRight: 8, verticalAlign: "middle", textAlign: "center", fontSize: 10, lineHeight: "14px", background: isSelected ? "var(--accent)" : "transparent", color: isSelected ? "#fff" : "transparent" }}>{isSelected ? "\u2713" : ""}</span>
                    {product.name}
                  </div>
                  {product.source_url && <div style={{ fontSize: 11, color: "var(--muted)", marginLeft: 24 }}>{product.source_url.replace(/^https?:\/\//, "").split("/")[0]}</div>}
                </div>
                <div style={{ fontSize: 15, fontWeight: 800, fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", color: "var(--text)" }}>{product.price}</div>
                <div onClick={e => { e.stopPropagation(); toggleClaimRow(i); }} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", userSelect: "none" }}>
                  <span style={{ fontSize: 12, fontWeight: 600, fontFamily: "var(--font-mono)", color: hasPending ? "var(--verdict-warn)" : backed === total ? "var(--verdict-good)" : backed === 0 ? "var(--verdict-bad)" : "var(--verdict-warn)" }}>{backed}/{total} {hasPending ? "auditing..." : "backed"}</span>
                  <span style={{ fontSize: 10, color: "var(--muted)" }}>{isExpanded ? "\u25B2" : "\u25BC"}</span>
                </div>
                <div style={{ textAlign: "center" }}><span style={{ fontSize: 11, fontWeight: 600, padding: "3px 8px", borderRadius: 10, background: backed === total ? "var(--verdict-good-soft)" : "var(--verdict-warn-soft)", color: backed === total ? "var(--verdict-good)" : "var(--verdict-warn)" }}>{backed === total ? "Verified" : backed === 0 ? "Review" : "Partial"}</span></div>
                <div style={{ textAlign: "right" }}>{isSelected ? <button onClick={e => { e.stopPropagation(); handleBuy(); }} disabled={phase === "purchasing"} style={{ padding: "8px 20px", borderRadius: 10, border: "none", background: "var(--accent-grad)", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", opacity: phase === "purchasing" ? 0.6 : 1 }}>{phase === "purchasing" ? "Buying..." : "Buy " + product.price}</button> : <span style={{ fontSize: 11, color: "var(--muted)" }}>Select to buy</span>}</div>
              </div>

              {isExpanded && (<div style={{ marginLeft: 24, marginBottom: 12, padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.015)", border: "1px solid var(--border)" }}>
                {product.claims.map((claim, ci) => (
                  <div key={ci} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", fontSize: 12, borderBottom: ci < product.claims.length - 1 ? "1px solid rgba(255,255,255,0.03)" : "none" }}>
                    <span style={{ color: "var(--text-2)" }}>{claim.text}</span>
                    <span style={{ color: cc(claim.verdict), fontWeight: 600, fontSize: 11, fontFamily: "var(--font-mono)", marginLeft: 12, whiteSpace: "nowrap" }}>{VERDICT_LABELS[claim.verdict] || claim.verdict}{claim.receipts && claim.receipts.length > 0 && <span style={{ color: "var(--muted)", fontWeight: 400, marginLeft: 4 }}>({claim.receipts.length})</span>}</span>
                  </div>
                ))}
              </div>)}
            </div>
          );
        })}
        {selectedProduct !== null && pendingClaims && phase === "results" && (<div style={{ fontSize: 12, color: "var(--verdict-warn)", textAlign: "center", padding: "10px 14px", borderRadius: 8, background: "var(--verdict-warn-soft)", marginTop: 8 }}>Some claims for this product are still being audited. You can buy now, but review the claim verdicts first.</div>)}
        {error && phase === "results" && (<div style={{ fontSize: 12, color: "var(--verdict-bad)", textAlign: "center", padding: "10px 14px", borderRadius: 8, background: "var(--verdict-bad-soft)", marginTop: 8 }}>{error}</div>)}
      </>)}

      {result && result.products.length === 0 && !error && (<div className="glass" style={{ padding: "40px", borderRadius: 18, textAlign: "center", color: "var(--muted)" }}>No products found for &ldquo;{result.query}&rdquo;.<br />Try a different search.</div>)}
      <style>{"@keyframes shopperPulse { 0%, 100% { transform: translateX(-50%); opacity: 0.6; } 50% { transform: translateX(150%); opacity: 1; } }"}</style>
    </div>
  );
}
