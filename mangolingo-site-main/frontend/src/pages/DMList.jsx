import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Send } from "lucide-react";

export default function DMList() {
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/dm");
        setThreads(data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-4" data-testid="dm-list-page">
      <h1 className="font-display text-3xl font-black flex items-center gap-2">
        <Send className="w-7 h-7 text-primary" /> الرسائل الخاصة
      </h1>
      {loading ? (
        <p className="text-muted-foreground">جارٍ التحميل…</p>
      ) : threads.length === 0 ? (
        <p className="text-muted-foreground text-center py-12 border border-dashed border-border rounded-lg">
          لا توجد محادثات بعد. ابدأ الدردشة من صفحة الأصدقاء.
        </p>
      ) : (
        <div className="space-y-2">
          {threads.map((t) => (
            <Link
              key={t.room_id}
              to={`/messages/${t.user.id}`}
              className="flex items-center gap-3 bg-[#0F111A] border border-border rounded-lg p-3 hover:border-primary/50 transition"
              data-testid={`dm-thread-${t.user.id}`}
            >
              <Avatar className="w-12 h-12">
                <AvatarImage src={t.user.avatar} />
                <AvatarFallback className="bg-primary text-white">{t.user.name?.[0]}</AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <div className="font-bold">{t.user.name}</div>
                <div className="text-sm text-muted-foreground truncate">{t.last_message}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
