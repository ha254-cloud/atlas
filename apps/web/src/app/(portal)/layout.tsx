"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/context/auth-context";
import { Sidebar } from "@/components/layout/sidebar";
import { PageLoader } from "@/components/common/Loader";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
    if (!loading && user?.is_superuser) router.replace("/atlas-admin");
  }, [user, loading, router]);

  if (loading) return <PageLoader text="Loading Atlas…" />;
  if (!user || user.is_superuser) return null;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
