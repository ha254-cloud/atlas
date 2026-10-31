import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageContainerProps {
  children: ReactNode;
  className?: string;
  width?: "standard" | "wide";
}

export function PageContainer({ children, className, width = "wide" }: PageContainerProps) {
  return (
    <div
      className={cn(
        "mx-auto w-full space-y-6 p-4 sm:p-6 lg:p-8 lg:pt-7",
        width === "wide" ? "max-w-[1440px]" : "max-w-7xl",
        className,
      )}
    >
      {children}
    </div>
  );
}