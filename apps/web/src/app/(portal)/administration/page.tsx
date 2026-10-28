"use client";

import Link from "next/link";
import { ArrowRight, Cable, LockKeyhole, ScrollText, ShieldCheck, Workflow } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/context/auth-context";
import { TeamAdministration } from "@/features/administration/components/TeamAdministration";
import { BranchSettingsCard } from "@/features/branches/components/BranchSettingsCard";

const ADMIN_ROLES = new Set(["owner", "admin"]);
const CONTROL_AREAS = [
  { href: "/governance", label: "Governance", detail: "Audit evidence, sessions, retention, and consent", icon: ShieldCheck },
  { href: "/integrations", label: "Integrations", detail: "Connection health, credentials, mappings, and sync", icon: Cable },
  { href: "/workflows", label: "Workflows", detail: "Definitions, approvals, executions, and failures", icon: Workflow },
];

export default function AdministrationPage() {
  const { user } = useAuth();
  const canAdminister = ADMIN_ROLES.has(user?.role ?? "");

  return (
    <div className="flex h-full flex-col">
      <Header title="Administration" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-7xl space-y-8">
          {!canAdminister ? (
            <section className="mx-auto max-w-xl border-l-2 border-amber-600 bg-amber-50 p-6 text-amber-950">
              <LockKeyhole className="h-6 w-6" />
              <h2 className="mt-4 text-lg font-semibold">Administrator access required</h2>
              <p className="mt-2 text-sm">Only organization owners and administrators can manage tenant access and operating controls.</p>
            </section>
          ) : (
            <>
              <section className="grid gap-6 border-b pb-7 lg:grid-cols-[1fr_auto] lg:items-end">
                <div>
                  <p className="text-xs font-medium uppercase text-muted-foreground">Organization control center</p>
                  <h2 className="mt-2 text-2xl font-semibold">People, structure, and operating controls</h2>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Manage organization access here. Domain-specific configuration remains in its canonical workspace so permissions, validation, and audit behavior stay consistent.</p>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground"><ScrollText className="h-4 w-4" /> Organization {user?.organization_id}</div>
              </section>

              <section className="grid gap-px overflow-hidden border bg-border md:grid-cols-3">
                {CONTROL_AREAS.map(({ href, label, detail, icon: Icon }) => (
                  <div key={href} className="flex min-h-40 flex-col bg-background p-5">
                    <Icon className="h-5 w-5 text-blue-700" />
                    <h3 className="mt-5 text-sm font-semibold">{label}</h3>
                    <p className="mt-1 flex-1 text-xs leading-5 text-muted-foreground">{detail}</p>
                    <Button variant="ghost" size="sm" className="mt-4 w-fit px-0" asChild><Link href={href}>Open <ArrowRight className="h-4 w-4" /></Link></Button>
                  </div>
                ))}
              </section>

              <section><TeamAdministration /></section>
              <section><BranchSettingsCard /></section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}