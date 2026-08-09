import React from "react";
import ChatRoom from "@/components/ChatRoom";
import { Sparkles } from "lucide-react";

export default function Lobby() {
  return (
    <div className="space-y-4" data-testid="lobby-page">
      <div>
        <h1 className="font-display text-3xl font-black flex items-center gap-2">
          <Sparkles className="w-7 h-7 text-accent" /> الردهة العامة
        </h1>
        <p className="text-muted-foreground mt-1">دردش مع جميع أعضاء المنصة في الزمن الفعلي.</p>
      </div>
      <ChatRoom roomId="lobby" title="الردهة العامة" />
    </div>
  );
}
