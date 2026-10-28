"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Cross,
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
import { cn } from "@/lib/utils";
import { useAuth } from "@/features/auth/context/auth-context";

const NAV_ITEMS = [
  { href: "/dashboard",     label: "Command Center",      icon: LayoutDashboard },
  { href: "/executive",     label: "Executive View",      icon: Building2 },
  { href: "/tasks",         label: "Today's Work",        icon: ListChecks },
  { href: "/patients",      label: "Patients",            icon: Users },
  { href: "/claims",        label: "Claims",              icon: FileText },
  { href: "/documents",     label: "Documents",           icon: FolderOpen },
  { href: "/recovery",      label: "Recovery Workspace",  icon: TrendingUp },
  { href: "/appeals",       label: "Appeals",             icon: MessageSquare },
  { href: "/payments",      label: "Payments",            icon: CreditCard },
  { href: "/analytics",     label: "Analytics",           icon: BarChart3 },
  { href: "/copilot",       label: "Atlas Copilot",       icon: Compass },
  { href: "/integrations",  label: "Integrations",        icon: Plug },
  { href: "/payers",        label: "Payers",               icon: Landmark },
  { href: "/workflows",     label: "Workflow Engine",     icon: Workflow },
  { href: "/settings",      label: "Settings",            icon: Settings },
];

const ADMIN_ITEM = { href: "/administration", label: "Administration", icon: Shield };

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const items = user && ["owner", "admin"].includes(user.role)
    ? [...NAV_ITEMS.slice(0, -1), ADMIN_ITEM, NAV_ITEMS[NAV_ITEMS.length - 1]]
    : NAV_ITEMS;

  return (
    <aside className="flex h-screen w-14 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:w-60">
      <div className="flex h-14 items-center justify-center gap-2.5 border-b border-sidebar-border md:justify-start md:px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Cross className="h-4 w-4" />
        </div>
        <div className="hidden md:block">
          <p className="text-sm font-semibold">Atlas</p>
          <p className="text-[9px] uppercase text-sidebar-foreground/40">Revenue recovery</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-0.5">
          {items.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <li key={href}>
                <Link
                  href={href}
                  title={label}
                  className={cn(
                    "flex items-center justify-center gap-2.5 rounded-md px-2 py-2 text-sm transition-colors md:justify-start md:px-3",
                    active
                      ? "bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                      : "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground text-sidebar-foreground/70 font-normal",
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="hidden md:inline">{label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="space-y-1 border-t border-sidebar-border p-2 md:p-3">
        <div className="flex items-center justify-center gap-2.5 py-2 md:justify-start md:px-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
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
