"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useAuth } from "@/features/auth/context/auth-context";
import { Button } from "@/components/ui/button";
import { tasksService } from "@/services/tasks-service";

const TASK_ROLES = new Set([
  "owner",
  "admin",
  "manager",
  "revenue_analyst",
  "appeals_specialist",
  "biller",
]);

interface HeaderProps {
  title: string;
}

export function Header({ title }: HeaderProps) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const canViewTasks = TASK_ROLES.has(user?.role ?? "");
  const notifications = useQuery({
    queryKey: ["task-notifications"],
    queryFn: tasksService.notifications,
    enabled: canViewTasks,
    refetchInterval: 60_000,
  });
  const markRead = useMutation({
    mutationFn: tasksService.markNotificationRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["task-notifications"] }),
  });
  const unread = notifications.data ?? [];

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b bg-card px-4 sm:px-6">
      <h1 className="truncate text-lg font-semibold">{title}</h1>
      <div className="flex items-center gap-3">
        {canViewTasks && (
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              title={`${unread.length} unread task notifications`}
              onClick={() => setNotificationsOpen((open) => !open)}
            >
              <Bell className="h-5 w-5" />
              {unread.length > 0 && (
                <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">
                  {unread.length > 99 ? "99+" : unread.length}
                </span>
              )}
            </Button>
            {notificationsOpen && (
              <div className="absolute right-0 top-11 z-50 w-[min(22rem,calc(100vw-5rem))] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-lg">
                <div className="border-b px-4 py-3">
                  <p className="text-sm font-semibold">Task notifications</p>
                  <p className="text-xs text-muted-foreground">{unread.length} unread</p>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {unread.length === 0 ? (
                    <p className="px-4 py-8 text-center text-xs text-muted-foreground">
                      You are up to date.
                    </p>
                  ) : (
                    unread.slice(0, 8).map((notification) => (
                      <button
                        key={notification.id}
                        className="block w-full border-b px-4 py-3 text-left last:border-b-0 hover:bg-muted/50"
                        onClick={() => markRead.mutate(notification.id)}
                      >
                        <span className="block text-sm font-medium">{notification.title}</span>
                        <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">
                          {notification.message}
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
            {user?.first_name?.[0]}
            {user?.last_name?.[0]}
          </div>
          <span className="text-sm font-medium hidden md:block">
            {user?.first_name} {user?.last_name}
          </span>
        </div>
      </div>
    </header>
  );
}
