"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { authService } from "@/services/auth-service";
import { getErrorMessage } from "@/lib/api-client";
import { AtlasMark } from "@/components/brand/atlas-mark";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";

type Status = "verifying" | "success" | "error";

export function VerifyEmailView() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<Status>("verifying");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Missing verification token.");
      return;
    }
    authService
      .verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((error) => {
        setStatus("error");
        setMessage(getErrorMessage(error, "This verification link is invalid or has expired."));
      });
  }, [token]);

  return (
    <div className="flex w-full items-center justify-center px-4 py-10 sm:px-6 lg:px-12">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-2 text-center">
          <div className="flex items-center gap-2">
            <AtlasMark className="h-8 w-8 text-primary" />
            <span className="text-3xl font-bold">Atlas</span>
          </div>
        </div>

        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            {status === "verifying" && (
              <>
                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                <CardTitle>Verifying your email…</CardTitle>
              </>
            )}
            {status === "success" && (
              <>
                <CheckCircle2 className="h-10 w-10 text-primary" />
                <CardTitle>Email verified</CardTitle>
                <CardDescription>Your organization is now active. You can sign in.</CardDescription>
                <Button asChild className="mt-2">
                  <Link href="/login">Go to sign in</Link>
                </Button>
              </>
            )}
            {status === "error" && (
              <>
                <XCircle className="h-10 w-10 text-destructive" />
                <CardTitle>Verification failed</CardTitle>
                <CardDescription>{message}</CardDescription>
                <Button asChild variant="outline" className="mt-2">
                  <Link href="/login">Back to sign in</Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
