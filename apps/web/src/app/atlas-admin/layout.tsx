"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Building2, LogOut, ShieldCheck } from "lucide-react";
import { PageLoader } from "@/components/common/Loader";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/context/auth-context";

export default function AtlasAdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    if (!loading && user && !user.is_superuser) router.replace("/dashboard");
  }, [loading, router, user]);

  if (loading) return <PageLoader text="Opening Atlas control plane…" />;
  if (!user?.is_superuser) return null;

  return (
    <div className="min-h-screen bg-[#f4f3ef] text-[#181b1a]">
      <header className="sticky top-0 z-50 border-b border-white/10 bg-[#151918] text-white">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center">
          <div className="flex h-8 w-8 items-center justify-center bg-[#d8ff54] text-[#151918]">
            <Building2 className="h-4 w-4" />
          </div>
            <div className="ml-3 border-r border-white/15 pr-3">
              <p className="text-xs font-semibold">ATLAS</p>
              <p className="text-[9px] uppercase text-white/45">Control plane</p>
            </div>
            <div className="ml-3 flex items-center gap-2 text-xs text-white/65">
              <ShieldCheck className="h-4 w-4 text-[#d8ff54]" />
              <span className="hidden sm:inline">Platform administration</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-xs font-medium">{user.first_name} {user.last_name}</p>
              <p className="text-[10px] text-white/40">{user.email}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
              className="h-8 w-8 p-0 text-white/60 hover:bg-white/10 hover:text-white"
            onClick={() => void logout()}
            title="Sign out"
              aria-label="Sign out"
          >
              <LogOut className="h-4 w-4" />
          </Button>
        </div>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}