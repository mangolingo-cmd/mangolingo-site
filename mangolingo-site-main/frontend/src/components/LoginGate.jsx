import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { LogIn, UserPlus } from "lucide-react";

/**
 * Lightweight "please sign in" gate shown to guests when they hit a
 * social/protected interaction (chat, review, friends, messages...).
 */
export default function LoginGate({ message, testid = "login-gate" }) {
  return (
    <div
      className="bg-[#0F111A] border border-dashed border-border rounded-xl p-6 sm:p-8 text-center space-y-4"
      data-testid={testid}
    >
      <div className="mx-auto w-12 h-12 rounded-full bg-primary/15 grid place-items-center">
        <LogIn className="w-6 h-6 text-primary" />
      </div>
      <p className="text-sm sm:text-base text-foreground/90 max-w-md mx-auto leading-7">
        {message || "سجّل دخولك لتشارك في المناقشات، تكوين صداقات، وحفظ تقدمك في القراءة."}
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Link to="/login">
          <Button className="bg-primary hover:bg-primary/90 font-bold" data-testid={`${testid}-login`}>
            <LogIn className="w-4 h-4 me-1" /> تسجيل الدخول
          </Button>
        </Link>
        <Link to="/register">
          <Button variant="outline" className="font-bold" data-testid={`${testid}-register`}>
            <UserPlus className="w-4 h-4 me-1" /> إنشاء حساب
          </Button>
        </Link>
      </div>
    </div>
  );
}
