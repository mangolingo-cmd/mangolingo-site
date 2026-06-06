import React, { useEffect, useState } from "react";
import api from "@/api";
import TitleCard from "@/components/TitleCard";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Search, Flame, X } from "lucide-react";
import { arGenre } from "@/lib/genres";
import { t as tr } from "@/lib/i18n";
import { useAuth } from "@/context/AuthContext";
import Pagination from "@/components/Pagination";

const HERO = "https://images.unsplash.com/photo-1752338384552-1cda3350baba?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Nzh8MHwxfHNlYXJjaHw0fHx0b2t5byUyMG5pZ2h0JTIwYWxsZXl8ZW58MHx8fHwxNzc4NTA5MDMwfDA&ixlib=rb-4.1.0&q=85";

export default function Home() {
  const { user } = useAuth();
  const locale = user?.locale || "ar";
  const t = (k, v) => tr(locale, k, v);
  const [titles, setTitles] = useState([]);
  const [genres, setGenres] = useState([]);
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [arOnly, setArOnly] = useState(false);
  const [genre, setGenre] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Load genres once
  useEffect(() => {
    api.get("/genres").then(({ data }) => setGenres(data)).catch(() => {});
  }, []);

  const load = async () => {
    setLoading(true);
    try {
      const params = { page, limit: 30 };
      if (type !== "all") params.type = type;
      if (q) params.q = q;
      if (arOnly) params.ar_only = true;
      if (genre) params.genre = genre;
      const { data } = await api.get("/titles", { params });
      setTitles(data.items || []);
      setTotalPages(data.total_pages || 1);
      setTotal(data.total || 0);
    } finally {
      setLoading(false);
    }
  };

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); }, [q, type, arOnly, genre]);

  useEffect(() => {
    const id = setTimeout(load, 200);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, type, arOnly, genre, page]);

  return (
    <div className="space-y-8" data-testid="home-page">
      {/* Hero */}
      <section className="relative rounded-2xl overflow-hidden border border-border" data-testid="hero-section">
        <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${HERO})` }} />
        <div className="absolute inset-0 bg-gradient-to-l from-black via-black/70 to-black/30" />
        <div className="relative p-8 sm:p-14 max-w-2xl">
          <div className="inline-flex items-center gap-2 bg-primary/15 text-primary px-3 py-1 rounded-full text-sm font-bold mb-4">
            <Flame className="w-4 h-4" />
            {t("hero_badge")}
          </div>
          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-black leading-tight">
            {t("hero_title_1")} <span className="gradient-text">{t("hero_title_2")}</span> {t("hero_title_3")}
          </h1>
          <p className="text-base sm:text-lg text-muted-foreground mt-4 max-w-xl">
            {t("hero_subtitle")}
          </p>
        </div>
      </section>

      {/* Search + tabs */}
      <section>
        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center mb-4">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t("search_placeholder")}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="pe-10 bg-[#0F111A] border-border"
              data-testid="catalog-search"
            />
          </div>
          <Tabs value={type} onValueChange={setType}>
            <TabsList data-testid="catalog-tabs" className="bg-[#0F111A]">
              <TabsTrigger value="all" data-testid="tab-all">{t("all")}</TabsTrigger>
              <TabsTrigger value="manhwa" data-testid="tab-manhwa">{t("manhwa")}</TabsTrigger>
              <TabsTrigger value="manga" data-testid="tab-manga">{t("manga")}</TabsTrigger>
            </TabsList>
          </Tabs>
          <button
            onClick={() => setArOnly(!arOnly)}
            className={`px-4 py-2 rounded-md text-sm font-bold transition border ${arOnly ? "bg-accent text-black border-accent" : "bg-[#0F111A] text-muted-foreground border-border hover:text-foreground"}`}
            data-testid="ar-only-toggle"
          >
            {t("ar_only")} {arOnly ? "✓" : ""}
          </button>
        </div>

        {/* Genre chips */}
        {genres.length > 0 && (
          <div className="mb-6" data-testid="genres-bar">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-bold text-muted-foreground">{t("genre_label")}</span>
              {genre && (
                <button
                  onClick={() => setGenre("")}
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                  data-testid="clear-genre"
                >
                  <X className="w-3 h-3" /> {t("clear")}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto pb-1">
              {genres.map((g) => (
                <button
                  key={g.name}
                  onClick={() => setGenre(genre === g.name ? "" : g.name)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold transition border ${
                    genre === g.name
                      ? "bg-primary text-white border-primary"
                      : "bg-[#0F111A] text-muted-foreground border-border hover:text-foreground hover:border-primary/50"
                  }`}
                  data-testid={`genre-chip-${g.name}`}
                >
                  {arGenre(g.name)}{" "}
                  <span className={genre === g.name ? "text-white/70" : "text-muted-foreground/60"}>
                    ({g.count})
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {loading ? (
          <div className="text-muted-foreground text-center py-12">{t("loading")}</div>
        ) : titles.length === 0 ? (
          <div className="text-muted-foreground text-center py-12 border border-dashed border-border rounded-lg">
            {t("no_matching_titles")}
          </div>
        ) : (
          <>
            <div className="text-sm text-muted-foreground mb-3" data-testid="catalog-count">
              {t("titles_count", { n: total.toLocaleString(locale === "en" ? "en-US" : "ar-EG") })} • {t("page_of", { page, total: totalPages })}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 sm:gap-6" data-testid="catalog-grid">
              {titles.map((t) => <TitleCard key={t.id} title={t} />)}
            </div>
            {totalPages > 1 && (
              <Pagination page={page} totalPages={totalPages} onChange={setPage} />
            )}
          </>
        )}
      </section>
    </div>
  );
}
