import React, { useState, useEffect } from "react";
import { useAuth } from "@/context/AuthContext";
import { fmtError } from "@/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { User as UserIcon, Image as ImageIcon, FileText, Save } from "lucide-react";

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

export default function Settings() {
  const { user, updateProfile } = useAuth();
  const [name, setName] = useState("");
  const [avatar, setAvatar] = useState("");
  const [bio, setBio] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setName(user.name || "");
      setAvatar(user.avatar || "");
      setBio(user.bio || "");
    }
  }, [user]);

  const save = async () => {
    if (!name.trim()) return toast.error("الاسم مطلوب");
    setSaving(true);
    try {
      await updateProfile({ name: name.trim(), avatar: avatar.trim(), bio: bio.trim() });
      toast.success("تم حفظ الإعدادات بنجاح");
    } catch (e) {
      toast.error(fmtError(e.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6" data-testid="settings-page">
      <div>
        <h1 className="font-display text-3xl font-black">الإعدادات</h1>
        <p className="text-muted-foreground mt-1">عدّل ملفك الشخصي وصورتك ومعلوماتك.</p>
      </div>

      <Card className="bg-[#0F111A] border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display">
            <ImageIcon className="w-5 h-5 text-primary" /> صورة الحساب
          </CardTitle>
          <CardDescription>اختر صورة جاهزة أو ألصق رابط صورة مخصّصة</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <Avatar className="w-24 h-24 ring-2 ring-primary/40">
              <AvatarImage src={avatar} />
              <AvatarFallback className="bg-primary text-white text-3xl">
                {name?.[0]?.toUpperCase() || "?"}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1">
              <Label htmlFor="avatar-url" className="flex items-center gap-1">
                <ImageIcon className="w-3.5 h-3.5" /> رابط الصورة
              </Label>
              <Input
                id="avatar-url"
                value={avatar}
                onChange={(e) => setAvatar(e.target.value)}
                placeholder="https://..."
                data-testid="settings-avatar-url"
                className="mt-1 bg-secondary"
              />
            </div>
          </div>
          <div>
            <Label className="text-sm">أو اختر من الصور الجاهزة:</Label>
            <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 mt-2">
              {PRESET_AVATARS.map((src) => (
                <button
                  key={src}
                  type="button"
                  onClick={() => setAvatar(src)}
                  className={`aspect-square rounded-lg overflow-hidden border-2 transition ${avatar === src ? "border-primary scale-105" : "border-border hover:border-primary/50"}`}
                  data-testid={`preset-avatar-${src.split("=")[1]}`}
                >
                  <img src={src} alt="" className="w-full h-full object-cover bg-white" />
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-[#0F111A] border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display">
            <UserIcon className="w-5 h-5 text-primary" /> المعلومات الشخصية
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="settings-name">الاسم</Label>
            <Input
              id="settings-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={40}
              data-testid="settings-name"
              className="mt-1 bg-secondary"
            />
          </div>
          <div>
            <Label htmlFor="settings-email">البريد الإلكتروني</Label>
            <Input
              id="settings-email"
              value={user?.email || ""}
              disabled
              className="mt-1 bg-secondary/50 text-muted-foreground"
              data-testid="settings-email"
            />
            <p className="text-xs text-muted-foreground mt-1">لا يمكن تغيير البريد الإلكتروني حالياً.</p>
          </div>
          <div>
            <Label htmlFor="settings-bio" className="flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" /> نبذة عنك
            </Label>
            <Textarea
              id="settings-bio"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="اكتب نبذة قصيرة عنك..."
              data-testid="settings-bio"
              className="mt-1 bg-secondary"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={save}
          disabled={saving}
          className="bg-primary hover:bg-primary/90 font-bold"
          data-testid="settings-save"
        >
          <Save className="w-4 h-4 me-1" />
          {saving ? "جارٍ الحفظ…" : "حفظ التغييرات"}
        </Button>
      </div>
    </div>
  );
}
