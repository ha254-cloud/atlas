"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  TrendingUp,
  MessageSquare,
  CreditCard,
  BarChart3,
  Plug,
  Settings,
  LogOut,
  Compass,
  Workflow,
  ListChecks,
  Building2,
  FolderOpen,
  Shield,
  Users,
  Landmark,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AtlasMark } from "@/components/brand/atlas-mark";
import { cn } from "@/lib/utils";
import { useAuth } from "@/features/auth/context/auth-context";

interface NavigationItem {
  href: string;
  label: string;
  icon: LucideIcon;
  adminOnly?: boolean;
}

interface NavigationSection {
  label: string;
  items: NavigationItem[];
}

const NAVIGATION: NavigationSection[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Command Center", icon: LayoutDashboard },
      { href: "/executive", label: "Executive View", icon: Building2 },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/tasks", label: "Today's Work", icon: ListChecks },
      { href: "/patients", label: "Patients", icon: Users },
      { href: "/claims", label: "Claims", icon: FileText },
      { href: "/documents", label: "Documents", icon: FolderOpen },
    ],
  },
  {
    label: "Recovery",
    items: [
      { href: "/recovery", label: "Recovery Workspace", icon: TrendingUp },
      { href: "/appeals", label: "Appeals", icon: MessageSquare },
      { href: "/payments", label: "Payments", icon: CreditCard },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/copilot", label: "Atlas Copilot", icon: Compass },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/integrations", label: "Integrations", icon: Plug },
      { href: "/payers", label: "Payers", icon: Landmark },
      { href: "/workflows", label: "Workflow Engine", icon: Workflow },
      { href: "/administration", label: "Administration", icon: Shield, adminOnly: true },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const canAdminister = user && ["owner", "admin"].includes(user.role);

  return (
    <aside className="flex h-screen w-14 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-[2px_0_12px_rgba(11,30,24,0.06)] md:w-60">
      <div className="flex h-14 items-center justify-center gap-2.5 border-b border-sidebar-border md:justify-start md:px-5">
        <AtlasMark className="h-6 w-6 text-sidebar-primary" />
        <div className="hidden md:block">
          <p className="text-sm font-semibold tracking-wide">Atlas</p>
          <p className="text-[9px] uppercase tracking-[0.14em] text-sidebar-foreground/40">Revenue recovery</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <div className="space-y-4">
          {NAVIGATION.map((section) => {
            const items = section.items.filter((item) => !item.adminOnly || canAdminister);
            return (
              <section key={section.label}>
                <h2 className="mb-1 hidden px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-foreground/35 md:block">
                  {section.label}
                </h2>
                <ul className="space-y-0.5">
                  {items.map(({ href, label, icon: Icon }) => {
                    const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
                    return (
                      <li key={href}>
                        <Link
                          href={href}
                          title={label}
                          className={cn(
                            "relative flex items-center justify-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors md:justify-start md:px-3",
                            active
                              ? "bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                              : "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground text-sidebar-foreground/70 font-normal",
                          )}
                        >
                          <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
                          <span className="hidden md:inline">{label}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
      </nav>

      <div className="space-y-1 border-t border-sidebar-border p-2 md:p-3">
        <div className="flex items-center justify-center gap-2.5 py-2 md:justify-start md:px-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-sidebar-primary/50 bg-sidebar-accent text-xs font-semibold text-sidebar-foreground">
            {user?.first_name?.[0]}{user?.last_name?.[0]}
          </div>
          <div className="hidden min-w-0 md:block">
            <p className="text-xs font-medium truncate">{user?.first_name} {user?.last_name}</p>
            <p className="text-xs text-sidebar-foreground/40 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={logout}
          title="Sign out"
          className="flex w-full items-center justify-center gap-2.5 rounded-md px-2 py-2 text-xs text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground md:justify-start md:px-3"
        >
          <LogOut className="h-3.5 w-3.5" /> <span className="hidden md:inline">Sign out</span>
        </button>
      </div>
    </aside>
  );
}
