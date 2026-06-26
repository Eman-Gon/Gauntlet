import { useState, useRef, useCallback } from "react";
import { GlassCard } from "./GlassCard";

/*
  ShopperPanel -- buyer agent embedded in Gauntlet's dashboard.
  Search -> discover vetted agents -> show products -> buy with Stripe test.
  Design contract: glass surfaces, monochrome-cream text, indigo-cyan accent.
*/

interface Product {
  name: string;
  price: string;
  pros: string[];
  cons: string[];
  source_url: string | null;
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

const API_BASE = (
  (import.meta as unknown as { env?: { VITE_API_URL?: string } }).env
    ?.VITE_API_URL || ""
).replace(/\/+$/, "");

function scoreColor(score: number | null) {
  if (score === null) return "var(--muted)";
  if (score >= 0.8) return "var(--verdict-good)";
  if (score >= 0.6) return "var(--verdict-warn)";
  return "var(--verdict-bad)";
}

function scoreLabel(score: number | null) {
  if (score === null) return "?";
  return Math.round(score * 100) + "%";
}

export function ShopperPanel() {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [purchaseResult, setPurchaseResult] = useState<PurchaseResult | null>(
    null,
  );
  const [purchasingProduct, setPurchasingProduct] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setPhase("loading");
    setError(null);
    setResult(null);
    setPurchaseResult(null);
    try {
      const resp = await fetch(API_BASE + "/buyer/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      if (!resp.ok) {
        const err = await resp
          .json()
          .catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || "Search failed");
      }
      const data: SearchResult = await resp.json();
      setResult(data);
      setPhase("results");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
      setPhase("idle");
    }
  }, [query]);

  const handleBuy = useCallback(async (product: Product) => {
    setPurchasingProduct(product.name);
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
          amount_cents: cents,
          currency: "usd",
          description: product.name + " via Gauntlet buyer panel",
        }),
      });
      if (!resp.ok) {
        const err = await resp
          .json()
          .catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || "Purchase failed");
      }
      const data: PurchaseResult = await resp.json();
      setPurchaseResult(data);
      setPhase("purchased");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Purchase failed");
      setPhase("results");
    } finally {
      setPurchasingProduct(null);
    }
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  const searchBar = (
    <div style={{ display: "flex", gap: 10, width: "100%", maxWidth: 480 }}>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="wireless mouse under $30..."
        style={{
          flex: 1,
          padding: "12px 16px",
          borderRadius: 12,
          border: "1px solid var(--border)",
          background: "rgba(255,255,255,0.04)",
          color: "var(--text)",
          fontSize: 14,
          fontFamily: "var(--font-sans)",
          outline: "none",
        }}
      />
      <button
        onClick={handleSearch}
        disabled={!query.trim()}
        style={{
          padding: "12px 24px",
          borderRadius: 12,
          border: "none",
          background: query.trim()
            ? "var(--accent-grad)"
            : "rgba(255,255,255,0.06)",
          color: query.trim() ? "#fff" : "var(--muted)",
          fontSize: 14,
          fontWeight: 600,
          cursor: query.trim() ? "pointer" : "default",
          transition: "all 0.2s ease",
        }}
      >
        Search
      </button>
    </div>
  );

  const errorBanner = error ? (
    <div
      style={{
        fontSize: 12,
        color: "var(--verdict-bad)",
        padding: "8px 14px",
        borderRadius: 8,
        background: "var(--verdict-bad-soft)",
        maxWidth: 480,
        width: "100%",
        textAlign: "center" as const,
      }}
    >
      {error}
    </div>
  ) : null;

  /* IDLE */
  if (phase === "idle") {
    return (
      <GlassCard padding="24px 28px" radius={18}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 18,
            alignItems: "center",
          }}
        >
          <div
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: "var(--text-2)",
              letterSpacing: "0.02em",
            }}
          >
            WHAT DO YOU WANT TO BUY?
          </div>
          {searchBar}
          {errorBanner}
        </div>
      </GlassCard>
    );
  }

  /* LOADING */
  if (phase === "loading") {
    return (
      <GlassCard padding="24px 28px" radius={18}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div style={{ fontSize: 14, color: "var(--text)" }}>
            Searching for <strong>&ldquo;{query}&rdquo;</strong>
          </div>
          <div style={{ fontSize: 12, color: "var(--muted)" }}>
            Discovering vetted shopping agents via Gauntlet directory...
          </div>
          <div
            style={{
              width: 120,
              height: 3,
              borderRadius: 2,
              background: "rgba(255,255,255,0.06)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: "60%",
                height: "100%",
                background: "var(--accent-grad)",
                borderRadius: 2,
                animation: "shopperPulse 1.2s ease-in-out infinite",
              }}
            />
          </div>
          <style>{`
            @keyframes shopperPulse {
              0%, 100% { transform: translateX(-50%); opacity: 0.6; }
              50% { transform: translateX(150%); opacity: 1; }
            }
          `}</style>
        </div>
      </GlassCard>
    );
  }

  /* RESULTS */
  if (phase === "results" || phase === "purchasing") {
    return (
      <GlassCard padding="24px 28px" radius={18}>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Header */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            <div>
              <div
                style={{ fontSize: 12, color: "var(--muted)", marginBottom: 2 }}
              >
                SEARCH
              </div>
              <div
                style={{ fontSize: 15, fontWeight: 600, color: "var(--text)" }}
              >
                &ldquo;{result?.query}&rdquo;
              </div>
            </div>
            {result?.agent_name && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 14px",
                  borderRadius: 20,
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid var(--border)",
                }}
              >
                <div
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: scoreColor(result.reliability_score),
                    boxShadow:
                      "0 0 6px " + scoreColor(result.reliability_score),
                  }}
                />
                <span style={{ fontSize: 12, color: "var(--text-2)" }}>
                  {result.agent_name}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    color: scoreColor(result.reliability_score),
                  }}
                >
                  {scoreLabel(result.reliability_score)}
                </span>
              </div>
            )}
          </div>

          <div style={{ height: 1, background: "var(--border)" }} />

          {/* Product cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {result?.products.map((product, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 16,
                  flexWrap: "wrap",
                  padding: "16px 18px",
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.025)",
                  border: "1px solid var(--border)",
                  transition: "border-color 0.2s ease",
                }}
              >
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: "var(--text)",
                      marginBottom: 6,
                    }}
                  >
                    {product.name}
                  </div>
                  {product.pros.map((pro, j) => (
                    <div
                      key={"pro-" + j}
                      style={{
                        fontSize: 12,
                        color: "var(--verdict-good)",
                        lineHeight: 1.7,
                      }}
                    >
                      <span style={{ marginRight: 6 }}>&#10003;</span>
                      {pro}
                    </div>
                  ))}
                  {product.cons.map((con, j) => (
                    <div
                      key={"con-" + j}
                      style={{
                        fontSize: 12,
                        color: "var(--muted)",
                        lineHeight: 1.7,
                      }}
                    >
                      <span
                        style={{ marginRight: 6, color: "var(--verdict-bad)" }}
                      >
                        &#10007;
                      </span>
                      {con}
                    </div>
                  ))}
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    gap: 10,
                    minWidth: 100,
                  }}
                >
                  <div
                    style={{
                      fontSize: 20,
                      fontWeight: 800,
                      fontFamily: "var(--font-mono)",
                      fontVariantNumeric: "tabular-nums",
                      color: "var(--text)",
                    }}
                  >
                    {product.price}
                  </div>
                  <button
                    onClick={() => handleBuy(product)}
                    disabled={purchasingProduct === product.name}
                    style={{
                      padding: "10px 22px",
                      borderRadius: 10,
                      border: "none",
                      background: "var(--accent-grad)",
                      color: "#fff",
                      fontSize: 13,
                      fontWeight: 600,
                      cursor:
                        purchasingProduct === product.name ? "wait" : "pointer",
                      opacity: purchasingProduct === product.name ? 0.6 : 1,
                      transition: "all 0.2s ease",
                    }}
                  >
                    {purchasingProduct === product.name
                      ? "Buying..."
                      : "Buy " + product.price}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {errorBanner}

          {/* Search again row */}
          <div
            style={{
              display: "flex",
              gap: 10,
              borderTop: "1px solid var(--border)",
              paddingTop: 16,
            }}
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search again..."
              style={{
                flex: 1,
                padding: "10px 14px",
                borderRadius: 10,
                border: "1px solid var(--border)",
                background: "rgba(255,255,255,0.04)",
                color: "var(--text)",
                fontSize: 13,
                fontFamily: "var(--font-sans)",
                outline: "none",
              }}
            />
            <button
              onClick={handleSearch}
              disabled={!query.trim()}
              style={{
                padding: "10px 20px",
                borderRadius: 10,
                border: "none",
                background: "rgba(255,255,255,0.06)",
                color: "var(--text-2)",
                fontSize: 13,
                fontWeight: 500,
                cursor: query.trim() ? "pointer" : "default",
              }}
            >
              New search
            </button>
          </div>
        </div>
      </GlassCard>
    );
  }

  /* PURCHASED */
  if (phase === "purchased") {
    return (
      <GlassCard padding="24px 28px" radius={18}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
          }}
        >
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: "50%",
              background: "var(--verdict-good-soft)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 28,
            }}
          >
            &#10003;
          </div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 700,
              color: "var(--verdict-good)",
            }}
          >
            Payment confirmed
          </div>
          <div
            style={{ fontSize: 14, color: "var(--text)", textAlign: "center" }}
          >
            {purchasingProduct}
            <br />
            <span
              style={{
                fontFamily: "var(--font-mono)",
                color: "var(--text-2)",
                fontSize: 18,
                fontWeight: 600,
              }}
            >
              ${((purchaseResult?.amount_received ?? 0) / 100).toFixed(2)}
            </span>{" "}
            <span style={{ color: "var(--muted)" }}>
              {(purchaseResult?.currency ?? "usd").toUpperCase()}
            </span>
          </div>
          {purchaseResult?.id && (
            <div
              style={{
                fontSize: 11,
                color: "var(--muted)",
                fontFamily: "var(--font-mono)",
                padding: "6px 12px",
                borderRadius: 6,
                background: "rgba(255,255,255,0.04)",
              }}
            >
              {purchaseResult.id}
            </div>
          )}
          {purchaseResult?.receipt_url && (
            <a
              href={purchaseResult.receipt_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 12,
                color: "var(--accent)",
                textDecoration: "none",
              }}
            >
              View receipt &rarr;
            </a>
          )}
          <div
            style={{
              fontSize: 11,
              color: "var(--muted)",
              padding: "6px 14px",
              borderRadius: 8,
              background: "rgba(255,255,255,0.03)",
            }}
          >
            Test transaction -- no real money moved
          </div>
          <button
            onClick={() => {
              setPhase("results");
              setPurchaseResult(null);
            }}
            style={{
              padding: "10px 24px",
              borderRadius: 10,
              border: "1px solid var(--border)",
              background: "transparent",
              color: "var(--text-2)",
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              marginTop: 4,
            }}
          >
            Buy something else
          </button>
        </div>
      </GlassCard>
    );
  }

  return null;
}
