"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle2, Loader2 } from "lucide-react";
import { authService } from "@/services/auth-service";
import { getErrorMessage } from "@/lib/api-client";
import { AtlasMark } from "@/components/brand/atlas-mark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const registerSchema = z.object({
  organization_name: z.string().trim().min(2, "Organization name is required"),
  organization_type: z.enum(["hospital", "clinic", "medical_centre", "provider_group"]),
  country: z.string().trim().min(2, "Country is required"),
  first_name: z.string().trim().min(1, "First name is required"),
  last_name: z.string().trim().min(1, "Last name is required"),
  email: z.string().trim().email("Enter a valid work email address"),
  password: z
    .string()
    .min(10, "Password must be at least 10 characters")
    .regex(/[A-Z]/, "Password must include an uppercase letter")
    .regex(/[a-z]/, "Password must include a lowercase letter")
    .regex(/[0-9]/, "Password must include a digit")
    .regex(/[^A-Za-z0-9]/, "Password must include a special character"),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

const journeySteps = [
  ["01", "Create the organization record"],
  ["02", "Verify the administrator email"],
  ["03", "Sign in and configure the workspace"],
];

interface RegisterFormProps {
  registrationEnabled?: boolean;
}

export function RegisterForm({ registrationEnabled = true }: RegisterFormProps) {
  const searchParams = useSearchParams();
  const [serverError, setServerError] = useState<string | null>(null);
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);
  const intent = searchParams.get("intent");
  const isRecoveryPractice = intent === "recovery-practice";
  const title = isRecoveryPractice ? "Build your recovery practice" : "Request Atlas access";
  const submitLabel = isRecoveryPractice ? "Create recovery workspace" : "Request access";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      organization_type: "hospital",
      country: "Kenya",
    },
  });

  async function onSubmit(values: RegisterFormValues) {
    setServerError(null);
    try {
      await authService.register(values);
      setSubmittedEmail(values.email);
    } catch (error) {
      setServerError(
        getErrorMessage(
          error,
          "We could not create your organization. Please try again shortly.",
        ),
      );
    }
  }

  return (
    <div className="flex w-full items-center justify-center px-4 py-10 sm:px-6 lg:px-12">
      <div className="w-full max-w-xl">
        <div className="mb-7 flex flex-col items-center gap-2 text-center lg:hidden">
          <Link href="/" aria-label="Return to Atlas home" className="flex items-center gap-2">
            <AtlasMark className="h-8 w-8 text-primary" />
            <span className="font-editorial text-3xl font-bold">Atlas</span>
          </Link>
          <p className="text-sm text-muted-foreground">Healthcare Revenue Recovery</p>
        </div>

        <Card className="overflow-hidden">
          {!registrationEnabled ? (
            <CardContent
              role="status"
              aria-live="polite"
              className="flex flex-col items-center gap-3 px-6 py-12 text-center"
            >
              <AtlasMark className="h-10 w-10 text-primary" />
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">
                Infrastructure maintenance
              </p>
              <CardTitle className="font-editorial text-3xl">
                {title} is temporarily paused
              </CardTitle>
              <CardDescription className="max-w-md leading-6">
                We are not creating organization records while the hosting provider
                recovers the existing database storage. Contact the onboarding team
                and we will follow up without claiming that an activation email was sent.
              </CardDescription>
              <Button asChild className="mt-3">
                <a href="mailto:onboarding@atlashealth.ke?subject=Atlas%20access%20request">
                  Email the onboarding team
                </a>
              </Button>
              <Link
                href="/"
                className="mt-1 text-xs font-semibold text-primary underline-offset-4 hover:underline"
              >
                Return to the Atlas website
              </Link>
            </CardContent>
          ) : submittedEmail ? (
            <CardContent
              role="status"
              aria-live="polite"
              className="flex flex-col items-center gap-3 px-6 py-12 text-center"
            >
              <CheckCircle2 className="h-10 w-10 text-primary" />
              <CardTitle>Verification email sent</CardTitle>
              <CardDescription className="max-w-md leading-6">
                Your organization has been created in a pending state. Open the
                verification link sent to <strong>{submittedEmail}</strong> to
                activate the workspace, then sign in.
              </CardDescription>
              <Button asChild className="mt-3">
                <Link href="/login">Continue to sign in</Link>
              </Button>
              <Link
                href="/"
                className="mt-1 text-xs font-semibold text-primary underline-offset-4 hover:underline"
              >
                Return to the Atlas website
              </Link>
            </CardContent>
          ) : (
            <>
              <CardHeader className="border-b bg-muted/35 pb-6">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">
                  Organization onboarding
                </p>
                <CardTitle className="font-editorial text-3xl">{title}</CardTitle>
                <CardDescription className="max-w-lg leading-6">
                  Create the first administrator account for your healthcare
                  organization. Access activates only after work email verification.
                </CardDescription>
                <ol className="mt-4 grid gap-2 sm:grid-cols-3">
                  {journeySteps.map(([number, label]) => (
                    <li key={number} className="border-l border-primary/35 pl-3">
                      <span className="block font-editorial text-sm font-bold text-primary">
                        {number}
                      </span>
                      <span className="mt-1 block text-[11px] leading-4 text-muted-foreground">
                        {label}
                      </span>
                    </li>
                  ))}
                </ol>
              </CardHeader>
              <CardContent className="pt-6">
                <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
                  <div className="space-y-2">
                    <Label htmlFor="organization_name">Organization name</Label>
                    <Input
                      id="organization_name"
                      placeholder="Nairobi General Hospital"
                      autoComplete="organization"
                      aria-invalid={Boolean(errors.organization_name)}
                      {...register("organization_name")}
                    />
                    {errors.organization_name && (
                      <p className="text-sm text-destructive">
                        {errors.organization_name.message}
                      </p>
                    )}
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="organization_type">Organization type</Label>
                      <select
                        id="organization_type"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        {...register("organization_type")}
                      >
                        <option value="hospital">Hospital</option>
                        <option value="clinic">Clinic</option>
                        <option value="medical_centre">Medical centre</option>
                        <option value="provider_group">Provider group</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="country">Country</Label>
                      <Input
                        id="country"
                        autoComplete="country-name"
                        aria-invalid={Boolean(errors.country)}
                        {...register("country")}
                      />
                      {errors.country && (
                        <p className="text-sm text-destructive">{errors.country.message}</p>
                      )}
                    </div>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="first_name">First name</Label>
                      <Input
                        id="first_name"
                        placeholder="Sarah"
                        autoComplete="given-name"
                        aria-invalid={Boolean(errors.first_name)}
                        {...register("first_name")}
                      />
                      {errors.first_name && (
                        <p className="text-sm text-destructive">{errors.first_name.message}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="last_name">Last name</Label>
                      <Input
                        id="last_name"
                        placeholder="Wanjiku"
                        autoComplete="family-name"
                        aria-invalid={Boolean(errors.last_name)}
                        {...register("last_name")}
                      />
                      {errors.last_name && (
                        <p className="text-sm text-destructive">{errors.last_name.message}</p>
                      )}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Work email</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="sarah@hospital.com"
                      autoComplete="email"
                      aria-invalid={Boolean(errors.email)}
                      {...register("email")}
                    />
                    {errors.email && (
                      <p className="text-sm text-destructive">{errors.email.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder="At least 10 characters"
                      autoComplete="new-password"
                      aria-invalid={Boolean(errors.password)}
                      aria-describedby="password-requirements"
                      {...register("password")}
                    />
                    <p id="password-requirements" className="text-xs leading-5 text-muted-foreground">
                      Use at least 10 characters with uppercase, lowercase, a number,
                      and a special character.
                    </p>
                    {errors.password && (
                      <p className="text-sm text-destructive">{errors.password.message}</p>
                    )}
                  </div>

                  {serverError && (
                    <div
                      role="alert"
                      className="border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm leading-6 text-destructive"
                    >
                      {serverError}
                    </div>
                  )}

                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Creating organization…
                      </>
                    ) : (
                      submitLabel
                    )}
                  </Button>

                  <p className="text-center text-sm text-muted-foreground">
                    Already have an account?{" "}
                    <Link href="/login" className="text-primary underline-offset-4 hover:underline">
                      Sign in
                    </Link>
                  </p>
                </form>
              </CardContent>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
