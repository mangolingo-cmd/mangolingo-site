import React, { useEffect, useRef, useState } from "react";
import api, { fmtError } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Pencil, Trash2, Smile, Check, X, Bot } from "lucide-react";
import { toast } from "sonner";
import LoginGate from "@/components/LoginGate";

const REACT_EMOJI = ["👍", "❤️", "😂", "😮", "😢", "🔥"];

export default function ChatRoom({ roomId, title }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState("");
  const [pickerForId, setPickerForId] = useState(null);
  const endRef = useRef(null);

  const load = async () => {
    if (!user) return;
    try {
      const { data } = await api.get(`/rooms/${roomId}/messages`);
      setMessages(data);
    } catch (e) {
      console.error("chat load failed", e);
    }
  };

  useEffect(() => {
    if (!user) return;
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId, user]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (!user) {
    return (
      <LoginGate
        testid="chat-login-gate"
        message="سجّل دخولك للمشاركة في النقاش حول هذا العمل ولقاء عشاق آخرين."
      />
    );
  }

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

  const startEdit = (m) => {
    setEditingId(m.id);
    setEditText(m.content);
  };

  const saveEdit = async (mid) => {
    if (!editText.trim()) return setEditingId(null);
    try {
      const { data } = await api.patch(`/messages/${mid}`, { content: editText.trim() });
      setMessages((arr) => arr.map((m) => (m.id === mid ? data : m)));
      setEditingId(null);
    } catch (err) {
      toast.error(fmtError(err.response?.data?.detail));
    }
  };

  const remove = async (mid) => {
    if (!window.confirm("حذف هذه الرسالة؟")) return;
    try {
      await api.delete(`/messages/${mid}`);
      setMessages((arr) => arr.filter((m) => m.id !== mid));
    } catch (err) {
      toast.error(fmtError(err.response?.data?.detail));
    }
  };

  const react = async (mid, emoji) => {
    setPickerForId(null);
    try {
      const { data } = await api.post(`/messages/${mid}/react`, { emoji });
      setMessages((arr) => arr.map((m) => (m.id === mid ? { ...m, reactions: data.reactions } : m)));
    } catch (err) {
      toast.error(fmtError(err.response?.data?.detail));
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
          const canDelete = mine || user?.role === "admin";
          const isBot = m.is_bot || m.sender_id === "bot";
          return (
            <div key={m.id} className={`flex gap-2 msg-bubble ${mine ? "flex-row-reverse" : ""}`} data-testid={`msg-${m.id}`}>
              <Avatar className="w-8 h-8 shrink-0">
                <AvatarImage src={m.sender_avatar} />
                <AvatarFallback className={`text-white text-xs ${isBot ? "bg-accent" : "bg-primary"}`}>
                  {isBot ? <Bot className="w-4 h-4" /> : (m.sender_name?.[0] || "?")}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col gap-1 max-w-[75%] group">
                <div className={`px-3 py-2 rounded-2xl ${mine ? "bg-primary/25 border border-primary/40 rounded-tl-sm" : isBot ? "bg-accent/15 border border-accent/30" : "bg-white/8 border border-white/10 rounded-tr-sm"}`}>
                  {!mine && (
                    <div className={`text-xs font-bold mb-0.5 ${isBot ? "text-accent" : "text-primary"}`}>
                      {m.sender_name}{isBot && " · bot"}
                    </div>
                  )}
                  {editingId === m.id ? (
                    <div className="flex items-center gap-1">
                      <Input
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && saveEdit(m.id)}
                        className="h-7 text-sm bg-secondary"
                        data-testid={`msg-edit-input-${m.id}`}
                      />
                      <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => saveEdit(m.id)} data-testid={`msg-edit-save-${m.id}`}>
                        <Check className="w-4 h-4 text-accent" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingId(null)}>
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  ) : (
                    <div className="text-sm leading-6 whitespace-pre-wrap break-words">
                      {m.content}
                      {m.edited && <span className="text-[10px] text-muted-foreground ms-1">(عُدّلت)</span>}
                    </div>
                  )}
                </div>

                {/* Reactions row */}
                {m.reactions && Object.keys(m.reactions).length > 0 && (
                  <div className={`flex gap-1 flex-wrap ${mine ? "justify-end" : ""}`} data-testid={`msg-reactions-${m.id}`}>
                    {Object.entries(m.reactions).map(([emo, voters]) => (
                      <button
                        key={emo}
                        onClick={() => react(m.id, emo)}
                        className={`text-xs px-1.5 py-0.5 rounded-full border ${voters.includes(user.id) ? "bg-primary/20 border-primary/50" : "bg-white/5 border-white/10"} hover:bg-white/10`}
                        data-testid={`msg-react-${emo}-${m.id}`}
                      >
                        {emo} {voters.length}
                      </button>
                    ))}
                  </div>
                )}

                {/* Action toolbar (visible on hover) — hide on bot messages */}
                {!isBot && editingId !== m.id && (
                  <div className={`flex gap-1 opacity-0 group-hover:opacity-100 transition ${mine ? "justify-end" : ""}`}>
                    <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => setPickerForId(pickerForId === m.id ? null : m.id)} data-testid={`msg-react-toggle-${m.id}`}>
                      <Smile className="w-3.5 h-3.5" />
                    </Button>
                    {mine && (
                      <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => startEdit(m)} data-testid={`msg-edit-btn-${m.id}`}>
                        <Pencil className="w-3.5 h-3.5" />
                      </Button>
                    )}
                    {canDelete && (
                      <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive" onClick={() => remove(m.id)} data-testid={`msg-delete-btn-${m.id}`}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </div>
                )}

                {/* Emoji picker */}
                {pickerForId === m.id && (
                  <div className={`flex gap-1 bg-[#0F111A] border border-border rounded-full px-2 py-1 shadow-lg ${mine ? "self-end" : ""}`} data-testid={`msg-picker-${m.id}`}>
                    {REACT_EMOJI.map((e) => (
                      <button key={e} onClick={() => react(m.id, e)} className="hover:scale-125 transition text-base">{e}</button>
                    ))}
                  </div>
                )}
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
