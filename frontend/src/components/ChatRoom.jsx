import React, { useEffect, useRef, useState } from "react";
import api, { fmtError } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send } from "lucide-react";
import { toast } from "sonner";

export default function ChatRoom({ roomId, title }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);

  const load = async () => {
    try {
      const { data } = await api.get(`/rooms/${roomId}/messages`);
      setMessages(data);
    } catch (e) {
      console.error("chat load failed", e);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (e) => {
    e?.preventDefault();
    if (!text.trim() || sending) return;
    setSending(true);
    try {
      const { data } = await api.post(`/rooms/${roomId}/messages`, { content: text.trim() });
      setMessages((m) => [...m, data]);
      setText("");
    } catch (err) {
      toast.error(fmtError(err.response?.data?.detail));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-[60vh] bg-[#0F111A] border border-border rounded-xl overflow-hidden" data-testid="chat-room">
      <div className="px-4 py-3 border-b border-border glass-strong">
        <h3 className="font-display font-bold">{title}</h3>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-muted-foreground text-center text-sm py-8">كن أول من يكتب هنا!</p>
        )}
        {messages.map((m) => {
          const mine = m.sender_id === user?.id;
          return (
            <div key={m.id} className={`flex gap-2 msg-bubble ${mine ? "flex-row-reverse" : ""}`} data-testid={`msg-${m.id}`}>
              <Avatar className="w-8 h-8 shrink-0">
                <AvatarImage src={m.sender_avatar} />
                <AvatarFallback className="bg-primary text-white text-xs">{m.sender_name?.[0]}</AvatarFallback>
              </Avatar>
              <div className={`max-w-[75%] px-3 py-2 rounded-2xl ${mine ? "bg-primary/25 border border-primary/40 rounded-tl-sm" : "bg-white/8 border border-white/10 rounded-tr-sm"}`}>
                {!mine && <div className="text-xs font-bold text-primary mb-0.5">{m.sender_name}</div>}
                <div className="text-sm leading-6 whitespace-pre-wrap break-words">{m.content}</div>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>
      <form onSubmit={send} className="p-3 border-t border-border flex gap-2 glass-strong">
        <Input
          placeholder="اكتب رسالة..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          data-testid="chat-input"
          className="bg-secondary"
        />
        <Button type="submit" disabled={sending || !text.trim()} className="bg-primary hover:bg-primary/90" data-testid="chat-send">
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </div>
  );
}
