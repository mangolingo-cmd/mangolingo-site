import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/api";
import ChatRoom from "@/components/ChatRoom";

export default function DMThread() {
  const { userId } = useParams();
  const [roomId, setRoomId] = useState(null);
  const [other, setOther] = useState(null);

  useEffect(() => {
    (async () => {
      const [a, b] = await Promise.all([
        api.get(`/dm/${userId}/room`),
        api.get(`/users/${userId}`),
      ]);
      setRoomId(a.data.room_id);
      setOther(b.data);
    })();
  }, [userId]);

  if (!roomId || !other) return <div className="text-muted-foreground text-center py-12">جارٍ التحميل…</div>;

  return (
    <div className="space-y-4" data-testid="dm-thread-page">
      <Link to="/messages" className="text-sm text-muted-foreground hover:text-primary">← الرسائل</Link>
      <h1 className="font-display text-2xl font-black">محادثة مع {other.name}</h1>
      <ChatRoom roomId={roomId} title={other.name} />
    </div>
  );
}
