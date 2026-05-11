import React, { useEffect, useState } from "react";
import { Outlet, NavLink, Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/api";
import {
  Home as HomeIcon,
  MessageSquare,
  Users,
  User,
  LogOut,
  Bell,
  Shield,
  Send,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

const navItems = [
  { to: "/", label: "الرئيسية", icon: HomeIcon, testid: "nav-home" },
  { to: "/lobby", label: "الردهة العامة", icon: Sparkles, testid: "nav-lobby" },
  { to: "/messages", label: "الرسائل", icon: Send, testid: "nav-messages" },
  { to: "/friends", label: "الأصدقاء", icon: Users, testid: "nav-friends" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [notifs, setNotifs] = useState([]);

  useEffect(() => {
    if (!user) return;
    const tick = async () => {
      try {
        const { data } = await api.get("/notifications/unread_count");
        setUnread(data.count);
      } catch {}
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => clearInterval(id);
  }, [user]);

  const openNotifs = async () => {
    try {
      const { data } = await api.get("/notifications");
      setNotifs(data);
      await api.post("/notifications/read_all");
      setUnread(0);
    } catch {}
  };

  return (
    <div className="min-h-screen bg-[#050505] text-foreground">
      {/* Top nav */}
      <header className="sticky top-0 z-40 glass-strong border-b border-border" data-testid="top-nav">
        <div className="max-w-7xl mx-auto flex items-center gap-6 px-4 sm:px-6 py-3">
          <Link to="/" className="flex items-center gap-2 font-display text-2xl" data-testid="nav-logo">
            <span className="inline-block w-8 h-8 rounded-md bg-primary text-white grid place-items-center font-black">O</span>
            <span className="gradient-text font-black tracking-normal">Otaku Hub</span>
          </Link>
          <nav className="hidden md:flex items-center gap-1 me-auto">
            {navItems.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.to === "/"}
                data-testid={it.testid}
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-semibold transition flex items-center gap-2 ${
                    isActive ? "bg-primary/15 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                  }`
                }
              >
                <it.icon className="w-4 h-4" />
                {it.label}
              </NavLink>
            ))}
            {user?.role === "admin" && (
              <NavLink
                to="/admin"
                data-testid="nav-admin"
                className={({ isActive }) =>
                  `px-3 py-2 rounded-md text-sm font-semibold transition flex items-center gap-2 ${
                    isActive ? "bg-accent/15 text-accent" : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                  }`
                }
              >
                <Shield className="w-4 h-4" />
                لوحة الإدارة
              </NavLink>
            )}
          </nav>

          <div className="flex items-center gap-2 ms-auto md:ms-0">
            <DropdownMenu onOpenChange={(o) => o && openNotifs()}>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="relative" data-testid="notifications-btn">
                  <Bell className="w-5 h-5" />
                  {unread > 0 && (
                    <Badge className="absolute -top-1 -end-1 h-5 min-w-[20px] px-1 bg-primary text-white">
                      {unread}
                    </Badge>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-80 max-h-96 overflow-y-auto" dir="rtl">
                <DropdownMenuLabel>الإشعارات</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {notifs.length === 0 && (
                  <div className="px-3 py-6 text-center text-muted-foreground text-sm">لا توجد إشعارات</div>
                )}
                {notifs.map((n) => (
                  <DropdownMenuItem key={n.id} className="flex flex-col items-start gap-1 py-2">
                    <div className="text-sm font-semibold">
                      {n.type === "friend_request" && `طلب صداقة من ${n.payload?.from_name}`}
                      {n.type === "friend_accepted" && `${n.payload?.from_name} قبل طلب الصداقة`}
                      {n.type === "dm" && `رسالة من ${n.payload?.from_name}`}
                    </div>
                    {n.payload?.preview && (
                      <div className="text-xs text-muted-foreground truncate w-full">{n.payload.preview}</div>
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 rounded-md hover:bg-white/5 p-1" data-testid="user-menu">
                  <Avatar className="w-8 h-8">
                    <AvatarImage src={user?.avatar} />
                    <AvatarFallback className="bg-primary text-white text-xs">
                      {user?.name?.[0]?.toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <span className="hidden sm:block text-sm font-semibold">{user?.name}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" dir="rtl">
                <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/profile")} data-testid="menu-profile">
                  <User className="w-4 h-4 me-2" />
                  ملفي الشخصي
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    logout();
                    navigate("/login");
                  }}
                  data-testid="menu-logout"
                >
                  <LogOut className="w-4 h-4 me-2" />
                  تسجيل الخروج
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* Mobile nav */}
        <nav className="md:hidden flex items-center justify-around border-t border-border" data-testid="mobile-nav">
          {navItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.to === "/"}
              data-testid={`m-${it.testid}`}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center py-2 text-xs gap-1 ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`
              }
            >
              <it.icon className="w-5 h-5" />
              {it.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
