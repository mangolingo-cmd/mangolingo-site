import React from "react";
import { Link } from "react-router-dom";
import { Star } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { proxyImg } from "@/api";

const typeLabel = { manhwa: "مانهوا", manga: "مانجا" };

export default function TitleCard({ title }) {
  return (
    <Link
      to={`/title/${title.id}`}
      className="group block rounded-lg overflow-hidden bg-[#0F111A] card-hover"
      data-testid={`title-card-${title.id}`}
    >
      <div className="relative aspect-[2/3] bg-secondary overflow-hidden">
        {title.cover_url ? (
          <img
            src={proxyImg(title.cover_url)}
            alt={title.title_ar || title.title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
        ) : (
          <div className="w-full h-full grid place-items-center text-muted-foreground">لا توجد صورة</div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent" />
        <Badge className="absolute top-2 end-2 bg-primary/90 text-white border-0 font-bold">
          {typeLabel[title.type] || title.type}
        </Badge>
        {title.has_ar && (
          <Badge className="absolute top-9 end-2 bg-accent/95 text-black border-0 font-bold text-[10px]" data-testid={`ar-badge-${title.id}`}>
            عربي ✓
          </Badge>
        )}
        {title.rating_avg > 0 && (
          <div className="absolute top-2 start-2 bg-black/70 backdrop-blur-md rounded px-2 py-0.5 text-xs flex items-center gap-1">
            <Star className="w-3 h-3 fill-accent text-accent" />
            <span className="font-bold">{title.rating_avg}</span>
          </div>
        )}
        <div className="absolute bottom-0 inset-x-0 p-3">
          <h3 className="font-display font-black text-white text-base leading-tight line-clamp-2">
            {title.title_ar || title.title}
          </h3>
          {title.title_ar && title.title && title.title_ar !== title.title && (
            <p className="text-xs text-white/60 mt-0.5 line-clamp-1">{title.title}</p>
          )}
        </div>
      </div>
    </Link>
  );
}
