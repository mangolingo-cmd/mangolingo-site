import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { proxyImg } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { RotateCcw } from "lucide-react";

/**
 * Horizontal "Continue Reading" rail.
 * - Logged-in: pulls from /reading/continue
 * - Guest: reads localStorage entries (`reading:<title_id>`) and resolves titles from /titles bulk
 */
export default function ContinueReading() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (user) {
        try {
          const { data } = await api.get("/reading/continue");
          if (!cancelled) setItems(data || []);
        } catch (e) {
          if (!cancelled) setItems([]);
        }
        return;
      }
      // Guest: scan localStorage
      const local = [];
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (!k || !k.startsWith("reading:")) continue;
        try {
          const v = JSON.parse(localStorage.getItem(k));
          if (v && v.title_id && v.episode_id) local.push(v);
        } catch (e) { /* skip */ }
      }
      local.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
      const top = local.slice(0, 12);
      const enriched = await Promise.all(
        top.map(async (p) => {
          try {
            const { data } = await api.get(`/titles/${p.title_id}`);
            return { ...p, title: data };
          } catch (e) {
            return null;
          }
        })
      );
      if (!cancelled) setItems(enriched.filter(Boolean));
    })();
    return () => { cancelled = true; };
  }, [user?.id]);

  if (items.length === 0) return null;

  return (
    <section className="space-y-3" data-testid="continue-reading-rail">
      <div className="flex items-center gap-2">
        <RotateCcw className="w-5 h-5 text-accent" />
        <h2 className="font-display text-lg font-black">تابع القراءة</h2>
      </div>
      <div className="flex gap-3 sm:gap-4 overflow-x-auto pb-2 -mx-1 px-1">
        {items.map((it) => {
          const t = it.title;
          if (!t) return null;
          return (
            <Link
              key={it.title_id}
              to={`/title/${it.title_id}/episode/${it.episode_id}`}
              className="shrink-0 w-32 sm:w-36 group"
              data-testid={`continue-card-${it.title_id}`}
            >
              <div className="aspect-[2/3] rounded-lg overflow-hidden bg-[#0F111A] border border-border group-hover:border-accent transition">
                {t.cover_url && (
                  <img src={proxyImg(t.cover_url)} alt={t.title_ar || t.title} className="w-full h-full object-cover" />
                )}
              </div>
              <div className="mt-2 space-y-0.5">
                <div className="text-sm font-bold truncate">{t.title_ar || t.title}</div>
                <div className="text-xs text-accent font-semibold">
                  {t.type === "anime" ? "الحلقة" : "الفصل"} {it.episode_number ?? "-"}
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
