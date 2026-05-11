import React, { useEffect, useState } from "react";
import api, { fmtError } from "@/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Trash2, Plus } from "lucide-react";

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

export default function Admin() {
  const [titles, setTitles] = useState([]);
  const [form, setForm] = useState(EMPTY);

  const load = async () => {
    const { data } = await api.get("/titles");
    setTitles(data);
  };

  useEffect(() => { load(); }, []);

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
                <SelectItem value="anime">أنمي</SelectItem>
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
          <div><Label>الحلقات</Label><Input type="number" value={form.episodes} onChange={(e) => setForm({...form, episodes: e.target.value})} data-testid="admin-episodes" /></div>
          <div><Label>الفصول</Label><Input type="number" value={form.chapters} onChange={(e) => setForm({...form, chapters: e.target.value})} data-testid="admin-chapters" /></div>
          <div><Label>السنة</Label><Input type="number" value={form.year} onChange={(e) => setForm({...form, year: e.target.value})} data-testid="admin-year" /></div>
          <div className="sm:col-span-2"><Label>الملخص</Label><Textarea rows={3} value={form.synopsis} onChange={(e) => setForm({...form, synopsis: e.target.value})} data-testid="admin-synopsis" /></div>
        </div>
        <Button onClick={save} className="bg-primary hover:bg-primary/90" data-testid="admin-save">إضافة</Button>
      </section>

      <section>
        <h2 className="font-display text-xl font-black mb-4">العناوين الحالية ({titles.length})</h2>
        <div className="space-y-2">
          {titles.map((t) => (
            <div key={t.id} className="flex items-center gap-3 bg-[#0F111A] border border-border rounded-lg p-3" data-testid={`admin-row-${t.id}`}>
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
              <Button variant="ghost" size="icon" onClick={() => del(t.id)} data-testid={`admin-del-${t.id}`}>
                <Trash2 className="w-4 h-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
