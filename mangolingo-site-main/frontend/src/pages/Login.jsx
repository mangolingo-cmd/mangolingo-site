import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { fmtError } from "@/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      toast.success("مرحباً بعودتك!");
      nav("/");
    } catch (err) {
      toast.error(fmtError(err.response?.data?.detail) || "تعذر تسجيل الدخول");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen hero-grad flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <Link to="/" className="block text-center mb-6 font-display text-3xl gradient-text font-black">MangaVerse</Link>
        <Card className="bg-[#0F111A]/90 border-border">
          <CardHeader>
            <CardTitle className="font-display text-3xl">أهلاً بعودتك</CardTitle>
            <CardDescription>سجّل دخولك إلى عالم الأنمي والمانجا</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <Label htmlFor="email">البريد الإلكتروني</Label>
                <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email" className="mt-1" />
              </div>
              <div>
                <Label htmlFor="password">كلمة المرور</Label>
                <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password" className="mt-1" />
              </div>
              <Button type="submit" disabled={loading} className="w-full bg-primary hover:bg-primary/90 font-bold" data-testid="login-submit">
                {loading ? "جارٍ الدخول…" : "دخول"}
              </Button>
            </form>
            <p className="text-sm text-muted-foreground text-center mt-4">
              ليس لديك حساب؟{" "}
              <Link to="/register" className="text-primary font-semibold hover:underline" data-testid="link-register">
                إنشاء حساب
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
