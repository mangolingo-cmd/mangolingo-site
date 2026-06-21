import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api, { proxyImg } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { ChevronRight, ChevronLeft, ArrowRight, Loader2, X } from "lucide-react";

export default function EpisodeView() {
  const { id, epId } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const [ep, setEp] = useState(null);
  const [title, setTitle] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [pages, setPages] = useState([]);
  const [loadingPages, setLoadingPages] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [a, b] = await Promise.all([
          api.get(`/titles/${id}/episodes/${epId}`),
          api.get(`/titles/${id}`),
        ]);
        setEp(a.data);
        setTitle(b.data);
        // Fetch all episodes in the SAME language as the current one (otherwise
        // prev/next nav stays empty for Arabic-only manhwa).
        const lang = a.data?.language || "en";
        const c = await api.get(`/titles/${id}/episodes`, { params: { lang } });
        setEpisodes(c.data);
        // Fetch live page URLs
        if (b.data.type !== "anime") {
          setLoadingPages(true);
          try {
            const p = await api.get(`/episodes/${epId}/pages`);
            setPages(p.data.pages || []);
          } finally {
            setLoadingPages(false);
          }
        }
        // Save reading progress (server for logged-in, localStorage for guests)
        const payload = {
          title_id: id,
          episode_id: epId,
          episode_number: a.data?.number,
          page: 0,
        };
        try {
          localStorage.setItem(`reading:${id}`, JSON.stringify({
            ...payload,
            updated_at: new Date().toISOString(),
          }));
        } catch (e) { /* ignore */ }
        if (user) {
          api.post("/reading/progress", payload).catch(() => {});
        }
      } catch (e) {
        console.error("episode load failed", e);
      }
    })();
  }, [id, epId, user?.id]);

  if (!ep || !title) return <div className="text-center py-12 text-muted-foreground">جارٍ التحميل…</div>;

  const idx = episodes.findIndex((e) => e.id === epId);
  const prev = idx > 0 ? episodes[idx - 1] : null;
  const next = idx >= 0 && idx < episodes.length - 1 ? episodes[idx + 1] : null;
  const isAnime = title.type === "anime";

  return (
    <div className="space-y-6 pb-24" data-testid="episode-page" style={{ position: "relative", zIndex: 1 }}>
      {/* Top action bar (reader mode, since global nav is hidden) */}
      <div className="sticky top-0 z-50 flex items-center justify-between gap-2 bg-[#050505]/95 backdrop-blur border-b border-border py-2 px-1 -mx-2 sm:-mx-4" data-testid="reader-topbar" style={{ pointerEvents: "auto" }}>
        <Link to={`/title/${id}`} className="text-sm text-muted-foreground hover:text-primary inline-flex items-center gap-1 px-2 py-1" data-testid="back-to-title">
          <ArrowRight className="w-4 h-4" /> عودة إلى {title.title_ar || title.title}
        </Link>
        <Link to="/" className="text-xs text-muted-foreground hover:text-primary inline-flex items-center gap-1 px-2 py-1" data-testid="back-to-home">
          <X className="w-4 h-4" /> خروج
        </Link>
      </div>

      <div>
        <p className="text-sm text-muted-foreground">{title.title_ar || title.title}</p>
        <h1 className="font-display text-2xl sm:text-3xl font-black">
          {isAnime ? "الحلقة" : "الفصل"} {ep.number}{ep.name ? ` — ${ep.name}` : ""}
        </h1>
      </div>

      {isAnime ? (
        <div className="aspect-video bg-black rounded-xl overflow-hidden border border-border" data-testid="episode-player">
          {ep.video_url ? (
            <iframe
              src={ep.video_url}
              title={`Episode ${ep.number}`}
              allow="autoplay; encrypted-media; fullscreen"
              allowFullScreen
              className="w-full h-full"
            />
          ) : (
            <div className="w-full h-full grid place-items-center text-muted-foreground">لا يوجد فيديو بعد</div>
          )}
        </div>
      ) : (
        <div className="space-y-2 max-w-3xl mx-auto" data-testid="chapter-reader">
          {loadingPages ? (
            <div className="flex flex-col items-center gap-3 py-20 text-muted-foreground">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
              <span>جاري تحميل الصفحات...</span>
            </div>
          ) : pages.length === 0 ? (
            <p className="text-center text-muted-foreground py-12">لا توجد صفحات متاحة</p>
          ) : (
            pages.map((p, i) => (
              <img key={`${ep.id}-${i}`} src={proxyImg(p)} alt={`Page ${i + 1}`} referrerPolicy="no-referrer" className="w-full h-auto" />
            ))
          )}
        </div>
      )}

      <div
        className="fixed bottom-0 inset-x-0 z-[9999] border-t border-border bg-[#050505]/95 backdrop-blur"
        data-testid="episode-nav"
        style={{ pointerEvents: "auto" }}
      >
        <div className="max-w-3xl mx-auto flex items-center justify-between gap-3 px-3 py-3 pe-48 sm:pe-3">
          <Button
            variant="secondary"
            disabled={!prev}
            onClick={() => prev && nav(`/title/${id}/episode/${prev.id}`)}
            data-testid="ep-prev"
            className="font-bold"
            style={{ pointerEvents: "auto" }}
          >
            <ChevronRight className="w-4 h-4 me-1" />
            السابق
          </Button>
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {idx >= 0 ? `${idx + 1} / ${episodes.length}` : ""}
          </span>
          <Button
            variant="secondary"
            disabled={!next}
            onClick={() => next && nav(`/title/${id}/episode/${next.id}`)}
            data-testid="ep-next"
            className="font-bold bg-primary text-white hover:bg-primary/90 disabled:bg-secondary disabled:text-muted-foreground"
            style={{ pointerEvents: "auto" }}
          >
            التالي
            <ChevronLeft className="w-4 h-4 ms-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
