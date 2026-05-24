import React, { useEffect, useState } from "react";
import api from "@/api";
import TitleCard from "@/components/TitleCard";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Search, Flame } from "lucide-react";

const HERO = "https://images.unsplash.com/photo-1752338384552-1cda3350baba?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzh8MHwxfHNlYXJjaHw0fHx0b2t5byUyMG5pZ2h0JTIwYWxsZXl8ZW58MHx8fHwxNzc4NTA5MDMwfDA&ixlib=rb-4.1.0&q=85";

export default function Home() {
  const [titles, setTitles] = useState([]);
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (type !== "all") params.type = type;
      if (q) params.q = q;
      const { data } = await api.get("/titles", { params });
      setTitles(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const id = setTimeout(load, 200);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, type]);

  return (
    <div className="space-y-8" data-testid="home-page">
      {/* Hero */}
      <section className="relative rounded-2xl overflow-hidden border border-border" data-testid="hero-section">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url(${HERO})` }}
        />
        <div className="absolute inset-0 bg-gradient-to-l from-black via-black/70 to-black/30" />
        <div className="relative p-8 sm:p-14 max-w-2xl">
          <div className="inline-flex items-center gap-2 bg-primary/15 text-primary px-3 py-1 rounded-full text-sm font-bold mb-4">
            <Flame className="w-4 h-4" />
            ساحة الأوتاكو العربية
          </div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-black leading-tight">
            عش <span className="gradient-text">شغف الأنمي</span> مع مجتمعك
          </h1>
          <p className="text-base sm:text-lg text-muted-foreground mt-4 max-w-xl">
            تصفح آلاف عناوين الأنمي والمانهوا والمانجا، شارك في غرف النقاش، تواصل مع الأصدقاء، وتابع رحلتك.
          </p>
        </div>
      </section>

      {/* Search + tabs */}
      <section>
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center mb-5">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="ابحث عن أنمي أو مانهوا أو مانجا..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="pe-10 bg-[#0F111A] border-border"
              data-testid="catalog-search"
            />
          </div>
          <Tabs value={type} onValueChange={setType}>
            <TabsList data-testid="catalog-tabs" className="bg-[#0F111A]">
              <TabsTrigger value="all" data-testid="tab-all">الكل</TabsTrigger>
              <TabsTrigger value="manhwa" data-testid="tab-manhwa">مانهوا</TabsTrigger>
              <TabsTrigger value="manga" data-testid="tab-manga">مانجا</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {loading ? (
          <div className="text-muted-foreground text-center py-12">جارٍ التحميل…</div>
        ) : titles.length === 0 ? (
          <div className="text-muted-foreground text-center py-12 border border-dashed border-border rounded-lg">
            لا توجد عناوين مطابقة.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 sm:gap-6" data-testid="catalog-grid">
            {titles.map((t) => <TitleCard key={t.id} title={t} />)}
          </div>
        )}
      </section>
    </div>
  );
}
