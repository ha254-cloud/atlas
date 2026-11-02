import { Suspense } from "react";
import { RegisterForm } from "@/features/auth/components/register-form";

export default function RegisterPage() {
  const registrationEnabled =
    process.env.NEXT_PUBLIC_REGISTRATION_ENABLED !== "false";

  return (
    <Suspense>
      <RegisterForm registrationEnabled={registrationEnabled} />
    </Suspense>
  );
}
