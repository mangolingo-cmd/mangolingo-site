import React, { useEffect, useState } from "react";
import api, { fmtError } from "@/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Trash2, Plus, FilmIcon, BookOpen, PlayCircle, RefreshCw, Clock } from "lucide-react";

const EMPTY = {
  type: "anime",
  title: "",
  title_ar: "",
  synopsis: "",
  cover_url: "",
  genres: "",
  status: "ongoing",
  episodes: "",
  chapters: "",
  year: "",
};

function EpisodesManager({ title }) {
  const isAnime = title.type === "anime";
  const [eps, setEps] = useState([]);
  const [number, setNumber] = useState("");
  const [name, setName] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [pagesText, setPagesText] = useState("");

  const load = async () => {
    const { data } = await api.get(`/titles/${title.id}/episodes`);
    setEps(data);
  };

  useEffect(() => {
    api.get(`/titles/${title.id}/episodes`).then(({ data }) => setEps(data)).catch(() => {});
  }, [title.id]);

  const add = async () => {
    if (!number) return toast.error("الرقم مطلوب");
    const pages = pagesText.split("\n").map((s) => s.trim()).filter(Boolean);
    try {
      await api.post(`/titles/${title.id}/episodes`, {
        number: Number(number),
        name,
        video_url: isAnime ? videoUrl : "",
        pages: isAnime ? [] : pages,
      });
      toast.success(`تمت إضافة ${isAnime ? "الحلقة" : "الفصل"}`);
      setNumber(""); setName(""); setVideoUrl(""); setPagesText("");
      load();
    } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
  };

  const del = async (eid) => {
    try {
      await api.delete(`/titles/${title.id}/episodes/${eid}`);
      load();
    } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
  };

  return (
    <div className="space-y-3 mt-3 bg-secondary/40 rounded-lg p-3 border border-border" data-testid={`ep-manager-${title.id}`}>
      <div className="grid sm:grid-cols-2 gap-2">
        <div><Label className="text-xs">الرقم</Label><Input type="number" value={number} onChange={(e) => setNumber(e.target.value)} data-testid={`ep-number-${title.id}`} /></div>
        <div><Label className="text-xs">الاسم (اختياري)</Label><Input value={name} onChange={(e) => setName(e.target.value)} data-testid={`ep-name-${title.id}`} /></div>
        {isAnime ? (
          <div className="sm:col-span-2">
            <Label className="text-xs">رابط الفيديو (YouTube embed أو MP4)</Label>
            <Input value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} placeholder="https://www.youtube.com/embed/..." data-testid={`ep-video-${title.id}`} />
          </div>
        ) : (
          <div className="sm:col-span-2">
            <Label className="text-xs">روابط الصفحات (واحد في كل سطر)</Label>
            <Textarea rows={4} value={pagesText} onChange={(e) => setPagesText(e.target.value)} placeholder="https://...page1.jpg&#10;https://...page2.jpg" data-testid={`ep-pages-${title.id}`} />
          </div>
        )}
      </div>
      <Button size="sm" onClick={add} className="bg-primary hover:bg-primary/90" data-testid={`ep-add-${title.id}`}>
        إضافة {isAnime ? "حلقة" : "فصل"}
      </Button>
      <div className="space-y-1">
        {eps.map((e) => (
          <div key={e.id} className="flex items-center gap-2 text-sm bg-[#0F111A] rounded px-2 py-1.5 border border-border">
            <span className="inline-flex w-7 h-7 items-center justify-center rounded bg-primary/15 text-primary font-bold text-xs">{e.number}</span>
            <span className="flex-1 truncate">{e.name || (isAnime ? `الحلقة ${e.number}` : `الفصل ${e.number}`)}</span>
            <Button size="icon" variant="ghost" onClick={() => del(e.id)} data-testid={`ep-del-${e.id}`}>
              <Trash2 className="w-3.5 h-3.5 text-destructive" />
            </Button>
          </div>
        ))}
        {eps.length === 0 && <p className="text-xs text-muted-foreground py-2">لا توجد {isAnime ? "حلقات" : "فصول"} بعد</p>}
      </div>
    </div>
  );
}

export default function Admin() {
  const [titles, setTitles] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [expanded, setExpanded] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshLog, setRefreshLog] = useState([]);

  const load = async () => {
    const { data } = await api.get("/titles", { params: { limit: 60 } });
    setTitles(data.items || []);
  };

  const loadRefreshLog = async () => {
    try {
      const { data } = await api.get("/admin/refresh-log");
      setRefreshLog(data);
    } catch (e) { /* ignore */ }
  };

  useEffect(() => {
    api.get("/titles", { params: { limit: 60 } }).then(({ data }) => setTitles(data.items || [])).catch(() => {});
    api.get("/admin/refresh-log").then(({ data }) => setRefreshLog(data)).catch(() => {});
  }, []);

  const triggerRefresh = async () => {
    setRefreshing(true);
    toast.info("جارٍ فحص جميع عناوين manga-spark للفصول الجديدة...");
    try {
      const { data } = await api.post("/admin/refresh-mangaspark", null, { timeout: 600000 });
      toast.success(`اكتمل: فُحص ${data.titles_scanned} عنواناً، أُضيف ${data.new_chapters} فصلاً جديداً`);
      await loadRefreshLog();
    } catch (e) {
      toast.error(fmtError(e.response?.data?.detail));
    }
    setRefreshing(false);
  };

  const save = async () => {
    if (!form.title.trim()) return toast.error("العنوان مطلوب");
    const payload = {
      type: form.type,
      title: form.title,
      title_ar: form.title_ar,
      synopsis: form.synopsis,
      cover_url: form.cover_url,
      genres: form.genres.split(",").map((g) => g.trim()).filter(Boolean),
      status: form.status,
      episodes: form.episodes ? Number(form.episodes) : null,
      chapters: form.chapters ? Number(form.chapters) : null,
      year: form.year ? Number(form.year) : null,
    };
    try {
      await api.post("/titles", payload);
      toast.success("تم إضافة العنوان");
      setForm(EMPTY);
      load();
    } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
  };

  const del = async (id) => {
    if (!window.confirm("حذف هذا العنوان؟")) return;
    try {
      await api.delete(`/titles/${id}`);
      toast.success("تم الحذف");
      load();
    } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
  };

  return (
    <div className="space-y-6" data-testid="admin-page">
      <h1 className="font-display text-3xl font-black">لوحة الإدارة</h1>

      <section className="bg-[#0F111A] border border-border rounded-xl p-6 space-y-3" data-testid="mangadex-import">
        <h2 className="font-display text-xl font-black flex items-center gap-2">
          <FilmIcon className="w-5 h-5 text-accent" /> استيراد من MangaDex
        </h2>
        <p className="text-sm text-muted-foreground">
          استورد مئات العناوين تلقائياً مع الفصول وصفحاتها الحقيقية. الفصول تُحمَّل عند فتح كل عنوان.
        </p>
        <div className="flex gap-2 flex-wrap">
          <Button
            onClick={async () => {
              toast.info("جارٍ استيراد 500 مانجا...");
              try {
                const { data } = await api.post("/admin/import_mangadex?ttype=manga&total=500");
                toast.success(`تم استيراد ${data.inserted} مانجا`);
                load();
              } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
            }}
            className="bg-primary hover:bg-primary/90"
            data-testid="import-manga-btn"
          >
            استيراد 500 مانجا
          </Button>
          <Button
            onClick={async () => {
              toast.info("جارٍ استيراد 500 مانهوا...");
              try {
                const { data } = await api.post("/admin/import_mangadex?ttype=manhwa&total=500");
                toast.success(`تم استيراد ${data.inserted} مانهوا`);
                load();
              } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
            }}
            variant="secondary"
            data-testid="import-manhwa-btn"
          >
            استيراد 500 مانهوا
          </Button>
          <Button
            onClick={async () => {
              toast.info("جارٍ فحص العناوين الفارغة وإخفاؤها...");
              try {
                const { data } = await api.post("/admin/cleanup_empty", null, { timeout: 600000 });
                toast.success(`تم الفحص: ${data.with_chapters} لديها فصول، أُخفي ${data.without_chapters}`);
                load();
              } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
            }}
            variant="ghost"
            data-testid="cleanup-empty-btn"
          >
            تنظيف العناوين بدون فصول
          </Button>
        </div>
      </section>

      <section className="bg-[#0F111A] border border-border rounded-xl p-6 space-y-3" data-testid="mangaspark-refresh">
        <h2 className="font-display text-xl font-black flex items-center gap-2">
          <RefreshCw className="w-5 h-5 text-accent" /> تحديث فصول manga-spark
        </h2>
        <p className="text-sm text-muted-foreground">
          المهمة الدورية تشتغل تلقائياً <strong>كل 6 ساعات</strong> في الخلفية لجلب الفصول الجديدة. يمكنك تشغيلها يدوياً الآن:
        </p>
        <Button onClick={triggerRefresh} disabled={refreshing} className="bg-accent hover:bg-accent/90" data-testid="refresh-mangaspark-btn">
          <RefreshCw className={`w-4 h-4 me-1 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "جارٍ التحديث..." : "تحديث الآن"}
        </Button>
        {refreshLog.length > 0 && (
          <div className="space-y-1.5 mt-3" data-testid="refresh-log">
            <p className="text-xs font-bold text-muted-foreground flex items-center gap-1">
              <Clock className="w-3 h-3" /> آخر عمليات التحديث:
            </p>
            {refreshLog.slice(0, 5).map((log, i) => (
              <div key={i} className="text-xs bg-secondary/40 rounded px-2 py-1.5 border border-border flex items-center gap-2 flex-wrap">
                <Badge variant={log.kind === "mangaspark_refresh_manual" ? "default" : "secondary"} className="text-[10px]">
                  {log.kind === "mangaspark_refresh_manual" ? "يدوي" : "تلقائي"}
                </Badge>
                <span className="text-muted-foreground">{new Date(log.at).toLocaleString("ar-EG")}</span>
                <span className="text-foreground">
                  فُحص {log.titles_scanned} | جديد {log.new_chapters} فصلاً
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="bg-[#0F111A] border border-border rounded-xl p-6 space-y-4">
        <h2 className="font-display text-xl font-black flex items-center gap-2">
          <Plus className="w-5 h-5 text-primary" /> إضافة عنوان جديد
        </h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <Label>النوع</Label>
            <Select value={form.type} onValueChange={(v) => setForm({...form, type: v})}>
              <SelectTrigger data-testid="admin-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="manhwa">مانهوا</SelectItem>
                <SelectItem value="manga">مانجا</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>الحالة</Label>
            <Select value={form.status} onValueChange={(v) => setForm({...form, status: v})}>
              <SelectTrigger data-testid="admin-status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="ongoing">مستمر</SelectItem>
                <SelectItem value="completed">مكتمل</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div><Label>العنوان (إنجليزي)</Label><Input value={form.title} onChange={(e) => setForm({...form, title: e.target.value})} data-testid="admin-title" /></div>
          <div><Label>العنوان (عربي)</Label><Input value={form.title_ar} onChange={(e) => setForm({...form, title_ar: e.target.value})} data-testid="admin-title-ar" /></div>
          <div className="sm:col-span-2"><Label>رابط الغلاف</Label><Input value={form.cover_url} onChange={(e) => setForm({...form, cover_url: e.target.value})} data-testid="admin-cover" /></div>
          <div className="sm:col-span-2"><Label>التصنيفات (مفصولة بفاصلة)</Label><Input value={form.genres} onChange={(e) => setForm({...form, genres: e.target.value})} data-testid="admin-genres" placeholder="أكشن, دراما" /></div>
          <div><Label>عدد الحلقات</Label><Input type="number" value={form.episodes} onChange={(e) => setForm({...form, episodes: e.target.value})} data-testid="admin-episodes" /></div>
          <div><Label>عدد الفصول</Label><Input type="number" value={form.chapters} onChange={(e) => setForm({...form, chapters: e.target.value})} data-testid="admin-chapters" /></div>
          <div><Label>السنة</Label><Input type="number" value={form.year} onChange={(e) => setForm({...form, year: e.target.value})} data-testid="admin-year" /></div>
          <div className="sm:col-span-2"><Label>الملخص</Label><Textarea rows={3} value={form.synopsis} onChange={(e) => setForm({...form, synopsis: e.target.value})} data-testid="admin-synopsis" /></div>
        </div>
        <Button onClick={save} className="bg-primary hover:bg-primary/90" data-testid="admin-save">إضافة العنوان</Button>
      </section>

      <section>
        <h2 className="font-display text-xl font-black mb-4 flex items-center gap-2">
          <FilmIcon className="w-5 h-5" /> العناوين الحالية وإدارة الحلقات/الفصول ({titles.length})
        </h2>
        <div className="space-y-2">
          {titles.map((t) => (
            <div key={t.id} className="bg-[#0F111A] border border-border rounded-lg p-3" data-testid={`admin-row-${t.id}`}>
              <div className="flex items-center gap-3">
                <div className="w-12 h-16 bg-secondary rounded overflow-hidden shrink-0">
                  {t.cover_url && <img src={t.cover_url} alt="" className="w-full h-full object-cover" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-bold">{t.title_ar || t.title}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge>{t.type}</Badge>
                    <span className="text-xs text-muted-foreground">{t.status}</span>
                  </div>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setExpanded(expanded === t.id ? null : t.id)}
                  data-testid={`admin-eps-toggle-${t.id}`}
                >
                  {t.type === "anime" ? <PlayCircle className="w-4 h-4 me-1" /> : <BookOpen className="w-4 h-4 me-1" />}
                  {expanded === t.id ? "إخفاء" : (t.type === "manhwa" ? "الفصول" : "الفصول")}
                </Button>
                <Button variant="ghost" size="icon" onClick={() => del(t.id)} data-testid={`admin-del-${t.id}`}>
                  <Trash2 className="w-4 h-4 text-destructive" />
                </Button>
              </div>
              {expanded === t.id && <EpisodesManager title={t} />}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
