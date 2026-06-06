import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { fmtError } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

const STATUS_LABEL = {
  watching: "أشاهد",
  completed: "أكملت",
  plan: "أنوي",
  dropped: "تركت",
  favorite: "مفضّل",
};

export default function Profile() {
  const { id } = useParams();
  const { user, updateProfile } = useAuth();
  const isMe = !id || id === user?.id;
  const [target, setTarget] = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [edit, setEdit] = useState({ name: "", bio: "", avatar: "" });

  const load = async () => {
    const uid = id || user.id;
    const { data } = await api.get(`/users/${uid}`);
    setTarget(data);
    setEdit({ name: data.name, bio: data.bio || "", avatar: data.avatar || "" });
    if (isMe) {
      const wl = await api.get("/watchlist");
      setWatchlist(wl.data.filter((e) => e.title));
    } else {
      setWatchlist([]);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id, user]);

  const save = async () => {
    try {
      await updateProfile(edit);
      toast.success("تم تحديث الملف الشخصي");
      load();
    } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
  };

  if (!target) return <div className="text-center py-12 text-muted-foreground">جارٍ التحميل…</div>;

  const byStatus = (s) => watchlist.filter((e) => e.status === s);

  return (
    <div className="space-y-8" data-testid="profile-page">
      <div className="bg-[#0F111A] border border-border rounded-2xl overflow-hidden">
        {target.background && (
          <div className="aspect-[4/1] w-full bg-cover bg-center" style={{ backgroundImage: `url(${target.background})` }} data-testid="profile-background" />
        )}
        <div className="p-6 flex flex-col md:flex-row gap-6 items-start">
          <Avatar className="w-28 h-28 ring-2 ring-primary/40 -mt-16 md:-mt-20 bg-[#0F111A]">
            <AvatarImage src={target.avatar} />
            <AvatarFallback className="bg-primary text-white text-3xl">{target.name?.[0]}</AvatarFallback>
          </Avatar>
          <div className="flex-1 space-y-2">
            <h1 className="font-display text-3xl font-black">{target.name}</h1>
            <p className="text-muted-foreground">{target.bio || "لا توجد نبذة بعد"}</p>
            {target.role === "admin" && <Badge className="bg-accent text-black">مدير</Badge>}
          </div>
        </div>
      </div>

      {isMe && (
        <div className="bg-[#0F111A] border border-border rounded-xl p-6 space-y-3" data-testid="edit-profile">
          <h2 className="font-display text-xl font-black">تعديل الملف الشخصي</h2>
          <Input placeholder="الاسم" value={edit.name} onChange={(e) => setEdit({...edit, name: e.target.value})} data-testid="edit-name" />
          <Input placeholder="رابط الصورة الرمزية (URL)" value={edit.avatar} onChange={(e) => setEdit({...edit, avatar: e.target.value})} data-testid="edit-avatar" />
          <Textarea placeholder="نبذة عنك" value={edit.bio} onChange={(e) => setEdit({...edit, bio: e.target.value})} rows={3} data-testid="edit-bio" />
          <Button onClick={save} className="bg-primary hover:bg-primary/90" data-testid="save-profile">حفظ</Button>
        </div>
      )}

      {isMe && (
        <div data-testid="watchlist-section">
          <h2 className="font-display text-2xl font-black mb-4">قائمتي</h2>
          <Tabs defaultValue="watching">
            <TabsList className="bg-[#0F111A] flex-wrap h-auto">
              {Object.entries(STATUS_LABEL).map(([k, v]) => (
                <TabsTrigger key={k} value={k} data-testid={`wl-tab-${k}`}>{v} ({byStatus(k).length})</TabsTrigger>
              ))}
            </TabsList>
            {Object.keys(STATUS_LABEL).map((k) => (
              <TabsContent key={k} value={k} className="mt-4">
                {byStatus(k).length === 0 ? (
                  <p className="text-muted-foreground text-center py-8">لا توجد عناصر</p>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
                    {byStatus(k).map((e) => (
                      <Link key={e.title_id} to={`/title/${e.title_id}`} className="block rounded-lg overflow-hidden bg-[#0F111A] card-hover">
                        <div className="aspect-[2/3] bg-secondary">
                          {e.title?.cover_url && <img src={e.title.cover_url} alt="" className="w-full h-full object-cover" />}
                        </div>
                        <div className="p-2"><div className="font-bold text-sm line-clamp-2">{e.title?.title_ar || e.title?.title}</div></div>
                      </Link>
                    ))}
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        </div>
      )}
    </div>
  );
}
