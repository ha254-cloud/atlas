"use client";

import Link from "next/link";
import { ArrowRight, SlidersHorizontal } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/context/auth-context";

export default function SettingsPage() {
  const { user } = useAuth();
  const canAdminister = user?.role === "owner" || user?.role === "admin";

  return (
    <div className="flex flex-col h-full">
      <Header title="Settings" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-2xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Account</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Name</dt>
                <dd className="font-medium">{user?.first_name} {user?.last_name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Email</dt>
                <dd className="font-medium">{user?.email}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Role</dt>
                <dd className="font-medium capitalize">{user?.role}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {canAdminister && (
          <div className="flex items-center justify-between gap-4 border p-4">
            <div className="flex items-start gap-3"><SlidersHorizontal className="mt-0.5 h-4 w-4 text-blue-700" /><div><p className="text-sm font-medium">Organization administration</p><p className="mt-1 text-xs text-muted-foreground">Manage team access, branches, and operating controls.</p></div></div>
            <Button variant="outline" size="sm" asChild><Link href="/administration">Open <ArrowRight className="h-4 w-4" /></Link></Button>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
