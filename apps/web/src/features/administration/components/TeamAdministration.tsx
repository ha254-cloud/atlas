"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, UserPlus, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getErrorMessage } from "@/lib/api-client";
import { authService } from "@/services/auth-service";
import type { User } from "@/types";

const ROLE_OPTIONS: { value: User["role"]; label: string }[] = [
  { value: "admin", label: "Org Admin" },
  { value: "manager", label: "Manager" },
  { value: "revenue_analyst", label: "Revenue Analyst" },
  { value: "appeals_specialist", label: "Appeals Specialist" },
  { value: "viewer", label: "Viewer" },
];

export function TeamAdministration() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<User["role"]>("viewer");
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const { data: members, isLoading } = useQuery({
    queryKey: ["org-members"],
    queryFn: authService.listMembers,
  });
  const inviteMutation = useMutation({
    mutationFn: () => authService.inviteUser({ email, role }),
    onSuccess: async () => {
      setFeedback({ type: "success", text: `Invitation sent to ${email}` });
      setEmail("");
      await queryClient.invalidateQueries({ queryKey: ["org-members"] });
    },
    onError: (error) => {
      setFeedback({ type: "error", text: getErrorMessage(error, "Failed to send invitation") });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="h-4 w-4" /> Team and access
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setFeedback(null);
            inviteMutation.mutate();
          }}
          className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_auto] sm:items-end"
        >
          <div className="space-y-2">
            <Label htmlFor="invite-email">Email address</Label>
            <Input id="invite-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="invite-role">Role</Label>
            <select
              id="invite-role"
              value={role}
              onChange={(event) => setRole(event.target.value as User["role"])}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              {ROLE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </div>
          <Button type="submit" disabled={inviteMutation.isPending}>
            {inviteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
            Invite
          </Button>
        </form>

        {feedback && (
          <p className={feedback.type === "success" ? "border-l-2 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-950" : "border-l-2 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-950"}>
            {feedback.text}
          </p>
        )}

        <div className="overflow-x-auto border">
          <table className="w-full min-w-[34rem] text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
              <tr><th className="px-4 py-3">Team member</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Status</th></tr>
            </thead>
            <tbody className="divide-y">
              {members?.map((member) => (
                <tr key={member.id}>
                  <td className="px-4 py-3"><p className="font-medium">{member.first_name} {member.last_name}</p><p className="text-xs text-muted-foreground">{member.email}</p></td>
                  <td className="px-4 py-3"><Badge variant="secondary" className="capitalize">{member.role.replaceAll("_", " ")}</Badge></td>
                  <td className="px-4 py-3"><Badge variant={member.is_active ? "success" : "outline"}>{member.is_active ? "Active" : "Inactive"}</Badge></td>
                </tr>
              ))}
              {!isLoading && !members?.length && <tr><td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">No organization members found.</td></tr>}
              {isLoading && <tr><td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">Loading team...</td></tr>}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}