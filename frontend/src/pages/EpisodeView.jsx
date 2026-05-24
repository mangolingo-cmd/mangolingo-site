import React, { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api from "@/api";
import { Button } from "@/components/ui/button";
import { ChevronRight, ChevronLeft, ArrowRight } from "lucide-react";

export default function EpisodeView() {
  const { id, epId } = useParams();
  const nav = useNavigate();
  const [ep, setEp] = useState(null);
  const [title, setTitle] = useState(null);
  const [episodes, setEpisodes] = useState([]);

  useEffect(() => {
    (async () => {
      const [a, b, c] = await Promise.all([
        api.get(`/titles/${id}/episodes/${epId}`),
        api.get(`/titles/${id}`),
        api.get(`/titles/${id}/episodes`),
      ]);
      setEp(a.data);
      setTitle(b.data);
      setEpisodes(c.data);
    })();
  }, [id, epId]);

  if (!ep || !title) return <div className="text-center py-12 text-muted-foreground">جارٍ التحميل…</div>;

  const idx = episodes.findIndex((e) => e.id === epId);
  const prev = idx > 0 ? episodes[idx - 1] : null;
  const next = idx >= 0 && idx < episodes.length - 1 ? episodes[idx + 1] : null;
  const isAnime = title.type === "anime";

  return (
    <div className="space-y-6" data-testid="episode-page">
      <Link to={`/title/${id}`} className="text-sm text-muted-foreground hover:text-primary inline-flex items-center gap-1">
        <ArrowRight className="w-4 h-4" /> عودة إلى {title.title_ar || title.title}
      </Link>
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
          {(ep.pages || []).length === 0 ? (
            <p className="text-center text-muted-foreground py-12">لا توجد صفحات بعد</p>
          ) : ep.pages.map((p, i) => (
            <img key={i} src={p} alt={`Page ${i + 1}`} className="w-full rounded-lg border border-border" loading="lazy" />
          ))}
        </div>
      )}

      <div className="flex items-center justify-between gap-3" data-testid="episode-nav">
        <Button
          variant="secondary"
          disabled={!prev}
          onClick={() => prev && nav(`/title/${id}/episode/${prev.id}`)}
          data-testid="ep-prev"
        >
          <ChevronRight className="w-4 h-4 me-1" />
          {isAnime ? "السابقة" : "السابق"}
        </Button>
        <Button
          variant="secondary"
          disabled={!next}
          onClick={() => next && nav(`/title/${id}/episode/${next.id}`)}
          data-testid="ep-next"
        >
          {isAnime ? "التالية" : "التالي"}
          <ChevronLeft className="w-4 h-4 ms-1" />
        </Button>
      </div>
    </div>
  );
}
