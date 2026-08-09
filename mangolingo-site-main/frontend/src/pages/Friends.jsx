import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { fmtError } from "@/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { UserPlus, Check, X, MessageSquare, Search, UserMinus } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function Friends() {
  const [data, setData] = useState({ friends: [], incoming: [], outgoing: [] });
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);

  const load = async () => {
    const { data } = await api.get("/friends");
    setData(data);
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!q.trim()) { setResults([]); return; }
    const id = setTimeout(async () => {
      try {
        const { data } = await api.get("/users/search", { params: { q } });
        setResults(data);
      } catch (e) { console.error("user search failed", e); }
    }, 300);
    return () => clearTimeout(id);
  }, [q]);

  const sendRequest = async (uid) => {
    try {
      await api.post(`/friends/request/${uid}`);
      toast.success("تم إرسال طلب الصداقة");
      load();
    } catch (e) {
      toast.error(fmtError(e.response?.data?.detail));
    }
  };

  const respond = async (uid, accept) => {
    try {
      await api.post(`/friends/respond/${uid}`, null, { params: { accept } });
      toast.success(accept ? "تم قبول الصداقة" : "تم رفض الطلب");
      load();
    } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
  };

  const removeFriend = async (uid) => {
    try {
      await api.delete(`/friends/${uid}`);
      toast.success("تم الحذف");
      load();
    } catch (e) { toast.error(fmtError(e.response?.data?.detail)); }
  };

  const UserRow = ({ u, actions }) => (
    <div className="flex items-center gap-3 bg-[#0F111A] border border-border rounded-lg p-3" data-testid={`friend-row-${u.id}`}>
      <Avatar className="w-11 h-11">
        <AvatarImage src={u.avatar} />
        <AvatarFallback className="bg-primary text-white">{u.name?.[0]}</AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0">
        <div className="font-bold">{u.name}</div>
        <div className="text-xs text-muted-foreground truncate">{u.bio || "—"}</div>
      </div>
      <div className="flex gap-2">{actions}</div>
    </div>
  );

  return (
    <div className="space-y-6" data-testid="friends-page">
      <h1 className="font-display text-3xl font-black">الأصدقاء</h1>

      <div className="bg-[#0F111A] border border-border rounded-lg p-4 space-y-3">
        <div className="relative">
          <Search className="w-4 h-4 absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="ابحث عن مستخدم بالاسم..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pe-10 bg-secondary"
            data-testid="user-search-input"
          />
        </div>
        {results.length > 0 && (
          <div className="space-y-2">
            {results.map((u) => (
              <UserRow key={u.id} u={u} actions={
                <Button size="sm" onClick={() => sendRequest(u.id)} className="bg-primary hover:bg-primary/90" data-testid={`send-request-${u.id}`}>
                  <UserPlus className="w-4 h-4 me-1" /> إضافة
                </Button>
              } />
            ))}
          </div>
        )}
      </div>

      <Tabs defaultValue="friends">
        <TabsList className="bg-[#0F111A]">
          <TabsTrigger value="friends" data-testid="tab-friends">الأصدقاء ({data.friends.length})</TabsTrigger>
          <TabsTrigger value="incoming" data-testid="tab-incoming">طلبات واردة ({data.incoming.length})</TabsTrigger>
          <TabsTrigger value="outgoing" data-testid="tab-outgoing">طلبات صادرة ({data.outgoing.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="friends" className="space-y-2 mt-4">
          {data.friends.length === 0 && <p className="text-muted-foreground text-center py-6">لا أصدقاء بعد. ابحث وأضف!</p>}
          {data.friends.map((u) => (
            <UserRow key={u.id} u={u} actions={
              <>
                <Link to={`/messages/${u.id}`}>
                  <Button size="sm" variant="secondary" data-testid={`message-${u.id}`}><MessageSquare className="w-4 h-4" /></Button>
                </Link>
                <Button size="sm" variant="ghost" onClick={() => removeFriend(u.id)} data-testid={`remove-${u.id}`}><UserMinus className="w-4 h-4" /></Button>
              </>
            } />
          ))}
        </TabsContent>
        <TabsContent value="incoming" className="space-y-2 mt-4">
          {data.incoming.length === 0 && <p className="text-muted-foreground text-center py-6">لا طلبات واردة</p>}
          {data.incoming.map((u) => (
            <UserRow key={u.id} u={u} actions={
              <>
                <Button size="sm" onClick={() => respond(u.id, true)} className="bg-primary hover:bg-primary/90" data-testid={`accept-${u.id}`}><Check className="w-4 h-4" /></Button>
                <Button size="sm" variant="ghost" onClick={() => respond(u.id, false)} data-testid={`reject-${u.id}`}><X className="w-4 h-4" /></Button>
              </>
            } />
          ))}
        </TabsContent>
        <TabsContent value="outgoing" className="space-y-2 mt-4">
          {data.outgoing.length === 0 && <p className="text-muted-foreground text-center py-6">لا طلبات صادرة</p>}
          {data.outgoing.map((u) => (
            <UserRow key={u.id} u={u} actions={
              <Button size="sm" variant="ghost" onClick={() => removeFriend(u.id)} data-testid={`cancel-${u.id}`}>إلغاء</Button>
            } />
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}
