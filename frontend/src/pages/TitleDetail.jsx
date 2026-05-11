import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { fmtError } from "@/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Star, MessageSquare, Bookmark } from "lucide-react";
import ChatRoom from "@/components/ChatRoom";

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
  const [rating, setRating] = useState(8);
  const [content, setContent] = useState("");
  const [wlStatus, setWlStatus] = useState("");

  const load = async () => {
    const [a, b] = await Promise.all([
      api.get(`/titles/${id}`),
      api.get(`/titles/${id}/reviews`),
    ]);
    setT(a.data);
    setReviews(b.data);
  };

  useEffect(() => { load(); }, [id]);

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

  if (!t) return <div className="text-center py-20 text-muted-foreground">جارٍ التحميل…</div>;

  return (
    <div className="space-y-8" data-testid="title-detail-page">
      <Link to="/" className="text-muted-foreground text-sm hover:text-primary">← العودة</Link>

      <div className="grid md:grid-cols-[260px_1fr] gap-8">
        <div className="aspect-[2/3] rounded-xl overflow-hidden bg-[#0F111A] border border-border">
          {t.cover_url && <img src={t.cover_url} alt={t.title_ar || t.title} className="w-full h-full object-cover" />}
        </div>
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Badge className="bg-primary text-white border-0">{t.type === "anime" ? "أنمي" : t.type === "manhwa" ? "مانهوا" : "مانجا"}</Badge>
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
            {(t.genres || []).map((g) => <Badge key={g} variant="secondary" className="bg-secondary">{g}</Badge>)}
          </div>
          <div className="flex gap-3 pt-2 items-center flex-wrap">
            <Select value={wlStatus} onValueChange={setWatch}>
              <SelectTrigger className="w-48 bg-[#0F111A]" data-testid="watchlist-select">
                <Bookmark className="w-4 h-4 me-2" />
                <SelectValue placeholder="أضف إلى قائمتي" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(STATUS_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <Tabs defaultValue="discuss" className="mt-8">
        <TabsList className="bg-[#0F111A]">
          <TabsTrigger value="discuss" data-testid="tab-discuss"><MessageSquare className="w-4 h-4 me-1" />غرفة النقاش</TabsTrigger>
          <TabsTrigger value="reviews" data-testid="tab-reviews"><Star className="w-4 h-4 me-1" />المراجعات ({reviews.length})</TabsTrigger>
        </TabsList>
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
