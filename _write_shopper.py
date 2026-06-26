import os
code = r"""
import { useState, useRef, useCallback } from "react";
import { GlassCard } from "./GlassCard";

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

const API_BASE = (((import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL) || "").replace(/\/+$/, "");
"""
with open("frontend/src/components/ShopperPanel_basic.tsx", "w", encoding="utf-8") as f:
    f.write(code)
print("OK")
