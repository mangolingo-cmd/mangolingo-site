import React from "react";
import { ChevronRight, ChevronLeft } from "lucide-react";

function pageItems(page, totalPages) {
  // Build a smart pagination list with ellipsis: [1, ..., p-1, p, p+1, ..., last]
  const items = new Set([1, totalPages, page, page - 1, page + 1]);
  const arr = Array.from(items).filter((n) => n >= 1 && n <= totalPages).sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < arr.length; i++) {
    if (i > 0 && arr[i] - arr[i - 1] > 1) out.push("…");
    out.push(arr[i]);
  }
  return out;
}

export default function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null;
  const items = pageItems(page, totalPages);

  const go = (p) => {
    onChange(p);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <nav className="flex items-center justify-center gap-1 mt-8 flex-wrap" data-testid="pagination">
      <button
        onClick={() => go(Math.max(1, page - 1))}
        disabled={page <= 1}
        className="px-3 py-2 rounded-md bg-[#0F111A] border border-border text-sm font-bold hover:border-primary disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
        data-testid="page-prev"
      >
        <ChevronRight className="w-4 h-4" />
        السابق
      </button>
      {items.map((it, i) =>
        it === "…" ? (
          <span key={`e${i}`} className="px-2 text-muted-foreground">…</span>
        ) : (
          <button
            key={it}
            onClick={() => go(it)}
            className={`min-w-[40px] px-3 py-2 rounded-md text-sm font-bold transition border ${
              it === page
                ? "bg-primary text-white border-primary"
                : "bg-[#0F111A] text-muted-foreground border-border hover:text-foreground hover:border-primary/60"
            }`}
            data-testid={`page-${it}`}
          >
            {it}
          </button>
        )
      )}
      <button
        onClick={() => go(Math.min(totalPages, page + 1))}
        disabled={page >= totalPages}
        className="px-3 py-2 rounded-md bg-[#0F111A] border border-border text-sm font-bold hover:border-primary disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
        data-testid="page-next"
      >
        التالي
        <ChevronLeft className="w-4 h-4" />
      </button>
    </nav>
  );
}
