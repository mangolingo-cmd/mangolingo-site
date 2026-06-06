import React, { useState, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import { fmtError, uploadImage } from "@/api";
import { toast } from "sonner";
import { t, dirFor } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { User as UserIcon, Image as ImageIcon, FileText, Save, Languages, Mountain, Upload, Loader2 } from "lucide-react";

const PRESET_AVATARS = [
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Misa",
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Kira",
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Levi",
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Saber",
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Yumeko",
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Tanjiro",
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Asuka",
  "https://api.dicebear.com/7.x/adventurer/svg?seed=Itadori",
];

const PRESET_BACKGROUNDS = [
  "https://images.unsplash.com/photo-1542204165-65bf26472b9b?w=1200",
  "https://images.unsplash.com/photo-1626551093754-bf4ab57f5e22?w=1200",
  "https://images.unsplash.com/photo-1604079628040-94301bb21b91?w=1200",
  "https://images.unsplash.com/photo-1757694010137-08c1ac1f697e?w=1200",
  "https://images.unsplash.com/photo-1748445907524-2721462cc31a?w=1200",
];

export default function Settings() {
  const { user, updateProfile } = useAuth();
  const locale = user?.locale || "ar";
  const tr = (k, v) => t(locale, k, v);
  const [name, setName] = useState(() => user?.name || "");
  const [avatar, setAvatar] = useState(() => user?.avatar || "");
  const [bio, setBio] = useState(() => user?.bio || "");
  const [background, setBackground] = useState(() => user?.background || "");
  const [lang, setLang] = useState(() => user?.locale || "ar");
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [uploadingBg, setUploadingBg] = useState(false);
  const avatarFileRef = useRef(null);
  const bgFileRef = useRef(null);

  const onPickFile = async (file, kind) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error(locale === "en" ? "Image too large (max 5MB)" : "حجم الصورة كبير جداً (الحد 5 ميغابايت)");
      return;
    }
    const setLoading = kind === "avatar" ? setUploadingAvatar : setUploadingBg;
    setLoading(true);
    try {
      const { url } = await uploadImage(file);
      if (kind === "avatar") setAvatar(url); else setBackground(url);
      toast.success(locale === "en" ? "Image uploaded" : "تم رفع الصورة");
    } catch (e) {
      toast.error(fmtError(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    if (!name.trim()) return toast.error(tr("name_label"));
    setSaving(true);
    try {
      const updated = await updateProfile({
        name: name.trim(),
        avatar: avatar.trim(),
        bio: bio.trim(),
        background: background.trim(),
        locale: lang,
      });
      // Apply direction immediately
      document.documentElement.dir = dirFor(updated.locale);
      document.documentElement.lang = updated.locale;
      toast.success(tr("saved"));
    } catch (e) {
      toast.error(fmtError(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6" data-testid="settings-page">
      <div>
        <h1 className="font-display text-3xl font-black">{tr("settings_title")}</h1>
        <p className="text-muted-foreground mt-1">{tr("settings_subtitle")}</p>
      </div>

      {/* Language */}
      <Card className="bg-[#0F111A] border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display">
            <Languages className="w-5 h-5 text-primary" /> {tr("language_section")}
          </CardTitle>
          <CardDescription>{tr("language_hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="inline-flex rounded-md border border-border overflow-hidden">
            <button
              onClick={() => setLang("ar")}
              className={`px-5 py-2.5 text-sm font-bold transition ${lang === "ar" ? "bg-primary text-white" : "bg-secondary text-muted-foreground hover:text-foreground"}`}
              data-testid="lang-ar-toggle"
            >
              🇸🇦 {tr("arabic")}
            </button>
            <button
              onClick={() => setLang("en")}
              className={`px-5 py-2.5 text-sm font-bold transition ${lang === "en" ? "bg-primary text-white" : "bg-secondary text-muted-foreground hover:text-foreground"}`}
              data-testid="lang-en-toggle"
            >
              🇬🇧 {tr("english")}
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Avatar */}
      <Card className="bg-[#0F111A] border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display">
            <ImageIcon className="w-5 h-5 text-primary" /> {tr("avatar_section")}
          </CardTitle>
          <CardDescription>{tr("avatar_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <Avatar className="w-24 h-24 ring-2 ring-primary/40">
              <AvatarImage src={avatar} />
              <AvatarFallback className="bg-primary text-white text-3xl">{name?.[0]?.toUpperCase() || "?"}</AvatarFallback>
            </Avatar>
            <div className="flex-1">
              <Label htmlFor="avatar-url">{tr("image_url")}</Label>
              <Input id="avatar-url" value={avatar} onChange={(e) => setAvatar(e.target.value)} placeholder="https://..." data-testid="settings-avatar-url" className="mt-1 bg-secondary" />
              <input ref={avatarFileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={(e) => onPickFile(e.target.files?.[0], "avatar")} data-testid="settings-avatar-file" />
              <Button type="button" variant="outline" size="sm" onClick={() => avatarFileRef.current?.click()} disabled={uploadingAvatar} className="mt-2" data-testid="upload-avatar-btn">
                {uploadingAvatar ? <Loader2 className="w-4 h-4 me-1 animate-spin" /> : <Upload className="w-4 h-4 me-1" />}
                {uploadingAvatar ? (locale === "en" ? "Uploading…" : "جارٍ الرفع…") : (locale === "en" ? "Upload from device" : "رفع من الجهاز")}
              </Button>
            </div>
          </div>
          <div>
            <Label className="text-sm">{tr("or_pick_preset")}</Label>
            <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 mt-2">
              {PRESET_AVATARS.map((src) => (
                <button key={src} type="button" onClick={() => setAvatar(src)}
                  className={`aspect-square rounded-lg overflow-hidden border-2 transition ${avatar === src ? "border-primary scale-105" : "border-border hover:border-primary/50"}`}
                  data-testid={`preset-avatar-${src.split("=")[1]}`}>
                  <img src={src} alt="" className="w-full h-full object-cover bg-white" />
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Background */}
      <Card className="bg-[#0F111A] border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display">
            <Mountain className="w-5 h-5 text-primary" /> {tr("background_section")}
          </CardTitle>
          <CardDescription>{tr("background_hint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="aspect-[3/1] rounded-lg overflow-hidden bg-secondary border border-border relative">
            {background ? <img src={background} alt="" className="w-full h-full object-cover" /> : <div className="grid place-items-center h-full text-muted-foreground text-sm">لا توجد خلفية</div>}
          </div>
          <Input value={background} onChange={(e) => setBackground(e.target.value)} placeholder="https://..." data-testid="settings-background-url" className="bg-secondary" />
          <input ref={bgFileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={(e) => onPickFile(e.target.files?.[0], "background")} data-testid="settings-bg-file" />
          <Button type="button" variant="outline" size="sm" onClick={() => bgFileRef.current?.click()} disabled={uploadingBg} data-testid="upload-bg-btn">
            {uploadingBg ? <Loader2 className="w-4 h-4 me-1 animate-spin" /> : <Upload className="w-4 h-4 me-1" />}
            {uploadingBg ? (locale === "en" ? "Uploading…" : "جارٍ الرفع…") : (locale === "en" ? "Upload from device" : "رفع من الجهاز")}
          </Button>
          <div>
            <Label className="text-sm">{tr("or_pick_preset")}</Label>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-2">
              {PRESET_BACKGROUNDS.map((src, i) => (
                <button key={src} type="button" onClick={() => setBackground(src)}
                  className={`aspect-[3/2] rounded-md overflow-hidden border-2 transition ${background === src ? "border-primary scale-105" : "border-border hover:border-primary/50"}`}
                  data-testid={`preset-bg-${i}`}>
                  <img src={src} alt="" className="w-full h-full object-cover" />
                </button>
              ))}
              {background && (
                <button type="button" onClick={() => setBackground("")}
                  className="aspect-[3/2] rounded-md border-2 border-border hover:border-destructive text-xs text-muted-foreground"
                  data-testid="clear-bg">إزالة</button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personal info */}
      <Card className="bg-[#0F111A] border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display">
            <UserIcon className="w-5 h-5 text-primary" /> {tr("info_section")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="settings-name">{tr("name_label")}</Label>
            <Input id="settings-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={40} data-testid="settings-name" className="mt-1 bg-secondary" />
          </div>
          <div>
            <Label htmlFor="settings-email">{tr("email_label")}</Label>
            <Input id="settings-email" value={user?.email || ""} disabled className="mt-1 bg-secondary/50 text-muted-foreground" data-testid="settings-email" />
            <p className="text-xs text-muted-foreground mt-1">{tr("email_locked")}</p>
          </div>
          <div>
            <Label htmlFor="settings-bio" className="flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" /> {tr("bio_label")}
            </Label>
            <Textarea id="settings-bio" value={bio} onChange={(e) => setBio(e.target.value)} rows={3} maxLength={500} placeholder={tr("bio_placeholder")} data-testid="settings-bio" className="mt-1 bg-secondary" />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={save} disabled={saving} className="bg-primary hover:bg-primary/90 font-bold" data-testid="settings-save">
          <Save className="w-4 h-4 me-1" />
          {saving ? tr("saving") : tr("save")}
        </Button>
      </div>
    </div>
  );
}
