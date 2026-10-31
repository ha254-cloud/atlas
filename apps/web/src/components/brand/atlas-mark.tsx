import { cn } from "@/lib/utils";

interface AtlasMarkProps {
  className?: string;
}

export function AtlasMark({ className }: AtlasMarkProps) {
  return (
    <svg
      aria-hidden="true"
      className={cn("h-6 w-6", className)}
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        d="M4.5 19 10.25 5h3.5L19.5 19M7.25 13.5h9.5"
        stroke="currentColor"
        strokeLinecap="square"
        strokeLinejoin="miter"
        strokeWidth="2"
      />
    </svg>
  );
}
