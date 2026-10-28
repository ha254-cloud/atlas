import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface Props {
  className?: string;
  size?: "sm" | "md" | "lg";
  text?: string;
}

const SIZES = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-8 w-8" };

export function Loader({ className, size = "md", text }: Props) {
  return (
    <div className={cn("flex items-center justify-center gap-2 text-muted-foreground", className)}>
      <Loader2 className={cn("animate-spin", SIZES[size])} />
      {text && <span className="text-sm">{text}</span>}
    </div>
  );
}

export function PageLoader({ text = "Loading…" }: { text?: string }) {
  return (
    <div className="flex h-full items-center justify-center">
      <Loader size="lg" text={text} />
    </div>
  );
}
