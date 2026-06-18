import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { fmtError, proxyImg } from "@/api";
import { arGenre } from "@/lib/genres";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Star, MessageSquare, Bookmark, PlayCircle, BookOpen } from "lucide-react";
import ChatRoom from "@/components/ChatRoom";

const TYPE_LABEL = { anime: "أنمي", manhwa: "مانهوا", manga: "مانجا" };

function ChapterLanguageBadge({ ep, lang }) {
  if (ep.language === "ar") {
    return <span className="bg-accent/20 text-accent px-1.5 py-0.5 rounded font-bold">عربي ✓</span>;
  }
  return null;
}

function ChaptersList({ episodes, isAnime, lang, id }) {
  if (episodes.length === 0) return null;
  const hasGap = episodes.length > 1 && episodes[episodes.length - 1].number - episodes[0].number > episodes.length + 5;
  return (
    <>
      {hasGap && (
        <div className="text-xs text-muted-foreground bg-secondary/40 border border-border rounded-md p-3 mb-4" data-testid="gaps-notice">
          ℹ️ <strong>ملاحظة</strong>: قد تلاحظ فجوات في أرقام الفصول. هذا لأن فرق الترجمة المختلفة لم تُترجم كل الفصول.
        </div>
      )}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {episodes.map((ep) => (
          <Link
            key={ep.id}
            to={`/title/${id}/episode/${ep.id}`}
            className="flex items-center gap-3 bg-[#0F111A] border border-border rounded-lg p-3 hover:border-primary/50 transition group"
            data-testid={`episode-item-${ep.id}`}
          onClick={() => { window.open('https://www.effectivecpmnetwork.com/jrrgfky4?key=f973cf80e20aad395373fc3d220ac33c', '_blank'); }}
          >
            <div className="w-12 h-12 rounded-md bg-primary/15 text-primary grid place-items-center font-display font-black shrink-0 group-hover:bg-primary group-hover:text-white transition">
              {ep.number}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-bold truncate">{ep.name || (isAnime ? `الحلقة ${ep.number}` : `الفصل ${ep.number}`)}</div>
              <div className="text-xs text-muted-foreground flex items-center gap-2">
                <ChapterLanguageBadge ep={ep} lang={lang} />
                <span>{isAnime ? "اضغط للمشاهدة" : "اضغط للقراءة"}</span>
              </div>
            </div>
            {isAnime ? <PlayCircle className="w-5 h-5 text-muted-foreground" /> : <BookOpen className="w-5 h-5 text-muted-foreground" />}
          </Link>
        ))}
      </div>
    </>
  );
}

const STATUS_LABEL = {
  watching: "أشاهد",
  completed: "أكملت",
  plan: "أنوي",
  dropped: "تركت",
  favorite: "مفضّل",
};

export default function TitleDetail() {
  const { id } = useParams();
  const [t, setT] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [episodes, setEpisodes] = useState([]);
  const [lang, setLang] = useState("en");
  const [loadingEps, setLoadingEps] = useState(false);
  const [rating, setRating] = useState(8);
  const [content, setContent] = useState("");
  const [wlStatus, setWlStatus] = useState("");

  const loadTitle = async () => {
    try {
      const [a, b] = await Promise.all([
        api.get(`/titles/${id}`),
        api.get(`/titles/${id}/reviews`),
      ]);
      setT(a.data);
      setReviews(b.data);
    } catch (e) {
      toast.error("تعذر تحميل العنوان");
    }
  };

  const loadEpisodes = async (l) => {
    setLoadingEps(true);
    try {
      const r = await api.get(`/titles/${id}/episodes`, { params: { lang: l } });
      setEpisodes(r.data);
    } finally {
      setLoadingEps(false);
    }
  };

  const load = async () => {
    await loadTitle();
    await loadEpisodes(lang);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  useEffect(() => {
    if (t) loadEpisodes(lang);
    /* eslint-disable-next-line */
  }, [lang]);

  const submitReview = async () => {
    if (!content.trim()) return toast.error("اكتب مراجعتك أولاً");
    try {
      await api.post(`/titles/${id}/reviews`, { rating, content });
      toast.success("تم نشر المراجعة");
      setContent("");
      load();
    } catch (e) {
      toast.error(fmtError(e.response?.data?.detail));
    }
  };

  const setWatch = async (status) => {
    setWlStatus(status);
    try {
      await api.post("/watchlist", { title_id: id, status });
      toast.success(`أُضيف إلى: ${STATUS_LABEL[status]}`);
    } catch (e) {
      toast.error(fmtError(e.response?.data?.detail));
    }
  };

  if (!t) return <div className="text-center py-20 text-muted-foreground" data-testid="title-loading">جارٍ التحميل…</div>;

  const isAnime = t.type === "anime";

  return (
    <div className="space-y-8" data-testid="title-detail-page">
      <Link to="/" className="text-muted-foreground text-sm hover:text-primary">← العودة</Link>

      <div className="grid md:grid-cols-[260px_1fr] gap-8">
        <div className="aspect-[2/3] rounded-xl overflow-hidden bg-[#0F111A] border border-border">
          {t.cover_url && <img src={proxyImg(t.cover_url)} alt={t.title_ar || t.title} className="w-full h-full object-cover" />}
        </div>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge className="bg-primary text-white border-0">{TYPE_LABEL[t.type] || t.type}</Badge>
            {t.status && <Badge variant="outline" className="border-border text-muted-foreground">{t.status === "ongoing" ? "مستمر" : "مكتمل"}</Badge>}
            {t.year && <Badge variant="outline" className="border-border text-muted-foreground">{t.year}</Badge>}
          </div>
          <h1 className="font-display text-3xl sm:text-5xl font-black">{t.title_ar || t.title}</h1>
          {t.title_ar && t.title && t.title_ar !== t.title && <p className="text-muted-foreground">{t.title}</p>}
          <div className="flex items-center gap-4 flex-wrap">
            {t.rating_avg > 0 && (
              <div className="flex items-center gap-1 text-lg">
                <Star className="w-5 h-5 fill-accent text-accent" />
                <span className="font-bold">{t.rating_avg}</span>
                <span className="text-muted-foreground text-sm">({t.rating_count})</span>
              </div>
            )}
            {t.episodes && <span className="text-sm text-muted-foreground">{t.episodes} حلقة</span>}
            {t.chapters && <span className="text-sm text-muted-foreground">{t.chapters} فصل</span>}
          </div>
          <p className="leading-7 text-foreground/90">{t.synopsis}</p>
          <div className="flex gap-2 flex-wrap">
            {(t.genres || []).map((g) => <Badge key={g} variant="secondary" className="bg-secondary">{arGenre(g)}</Badge>)}
          </div>
          <div className="flex gap-3 pt-2 items-center flex-wrap">
            {episodes.length > 0 && (
              <Link to={`/title/${id}/episode/${episodes[0].id}`}>
                <Button className="bg-primary hover:bg-primary/90 font-bold" data-testid="start-watching-btn" onClick={() => { window.open('https://www.effectivecpmnetwork.com/jrrgfky4?key=f973cf80e20aad395373fc3d220ac33c', '_blank'); }}>
                  {isAnime ? <PlayCircle className="w-4 h-4 me-1" /> : <BookOpen className="w-4 h-4 me-1" />}
                  {isAnime ? "ابدأ المشاهدة" : "ابدأ القراءة"}
                </Button>
              </Link>
            )}
            <Select value={wlStatus} onValueChange={setWatch}>
              <SelectTrigger className="w-48 bg-[#0F111A]" data-testid="watchlist-select">
                <Bookmark className="w-4 h-4 me-2" />
                <SelectValue placeholder="أضف إلى قائمتي" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(STATUS_LABEL).map(([k, v]) => <SelectItem key={k} value={k} data-testid={`wl-opt-${k}`}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <Tabs defaultValue="episodes" className="mt-8">
        <TabsList className="bg-[#0F111A]">
          <TabsTrigger value="episodes" data-testid="tab-episodes">
            {isAnime ? <PlayCircle className="w-4 h-4 me-1" /> : <BookOpen className="w-4 h-4 me-1" />}
            {isAnime ? "الحلقات" : "الفصول"} ({episodes.length})
          </TabsTrigger>
          <TabsTrigger value="discuss" data-testid="tab-discuss"><MessageSquare className="w-4 h-4 me-1" />غرفة النقاش</TabsTrigger>
          <TabsTrigger value="reviews" data-testid="tab-reviews"><Star className="w-4 h-4 me-1" />المراجعات ({reviews.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="episodes" className="mt-4" data-testid="episodes-tab-content">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-3" data-testid="lang-switcher">
            <p className="text-sm text-muted-foreground">اختر لغة الترجمة:</p>
            <div className="inline-flex rounded-md border border-border overflow-hidden">
              <button
                onClick={() => setLang("ar")}
                className={`px-4 py-2 text-sm font-bold transition ${lang === "ar" ? "bg-primary text-white" : "bg-[#0F111A] text-muted-foreground hover:text-foreground"}`}
                data-testid="lang-ar"
              >
                🇸🇦 العربية
              </button>
              <button
                onClick={() => setLang("en")}
                className={`px-4 py-2 text-sm font-bold transition ${lang === "en" ? "bg-primary text-white" : "bg-[#0F111A] text-muted-foreground hover:text-foreground"}`}
                data-testid="lang-en"
              >
                🇬🇧 English
              </button>
            </div>
          </div>
          {loadingEps ? (
            <div className="text-center py-12 text-muted-foreground" data-testid="eps-loading">جارٍ جلب الفصول بالـ {lang === "ar" ? "العربية" : "الإنجليزية"}…</div>
          ) : episodes.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-border rounded-lg space-y-3" data-testid="episodes-empty">
              <p className="text-muted-foreground">
                لا توجد فصول {lang === "ar" ? "عربية" : "إنجليزية"} لهذا العنوان.
              </p>
              <p className="text-xs text-muted-foreground">
                جرّب تبديل اللغة، أو اطلب من المدير إضافة فصول من <Link to="/admin" className="text-primary font-bold hover:underline">لوحة الإدارة</Link>.
              </p>
            </div>
          ) : (
            <ChaptersList episodes={episodes} isAnime={isAnime} lang={lang} id={id} />
          )}
        </TabsContent>

        <TabsContent value="discuss" className="mt-4">
          <ChatRoom roomId={id} title="ناقش هذا العمل" />
        </TabsContent>

        <TabsContent value="reviews" className="mt-4 space-y-4">
          <div className="bg-[#0F111A] border border-border rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-3">
              <span className="text-sm">تقييمك:</span>
              <Select value={String(rating)} onValueChange={(v) => setRating(Number(v))}>
                <SelectTrigger className="w-24" data-testid="review-rating"><SelectValue /></SelectTrigger>
                <SelectContent>{[10,9,8,7,6,5,4,3,2,1].map((n) => <SelectItem key={n} value={String(n)}>{n}/10</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Textarea
              placeholder="شارك رأيك في هذا العمل..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              data-testid="review-content"
              rows={3}
            />
            <Button onClick={submitReview} className="bg-primary hover:bg-primary/90" data-testid="review-submit">نشر المراجعة</Button>
          </div>
          {reviews.map((r) => (
            <div key={r.id} className="bg-[#0F111A] border border-border rounded-lg p-4" data-testid={`review-${r.id}`}>
              <div className="flex items-center gap-3 mb-2">
                <Avatar className="w-9 h-9">
                  <AvatarImage src={r.user_avatar} />
                  <AvatarFallback className="bg-primary text-white text-xs">{r.user_name?.[0]}</AvatarFallback>
                </Avatar>
                <div>
                  <div className="font-bold text-sm">{r.user_name}</div>
                  <div className="text-xs text-muted-foreground flex items-center gap-1">
                    <Star className="w-3 h-3 fill-accent text-accent" />
                    {r.rating}/10
                  </div>
                </div>
              </div>
              <p className="text-sm leading-6 text-foreground/90">{r.content}</p>
            </div>
          ))}
          {reviews.length === 0 && <p className="text-muted-foreground text-center py-6">كن أول من يكتب مراجعة</p>}
        </TabsContent>
      </Tabs>
    </div>
  );
}
