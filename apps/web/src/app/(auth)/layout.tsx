import { AtlasMark } from "@/components/brand/atlas-mark";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f4f2ea]">
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full text-[#17624b]"
        preserveAspectRatio="none"
      >
        <defs>
          <pattern id="clinical-grid" width="48" height="48" patternUnits="userSpaceOnUse">
            <path
              d="M 48 0 L 0 0 0 48"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.055"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#clinical-grid)" />
      </svg>

      <div className="relative mx-auto grid min-h-screen max-w-[1440px] lg:grid-cols-[minmax(360px,0.85fr)_minmax(520px,1.15fr)]">
        <aside className="relative hidden border-r border-[#17624b]/20 px-14 py-16 lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="mb-20 flex items-center gap-3 text-[#17624b]">
              <AtlasMark className="h-8 w-8" />
              <span className="text-sm font-semibold uppercase tracking-[0.2em]">
                Atlas Health Systems
              </span>
            </div>

            <div className="max-w-md border-t-4 border-[#17624b] pt-8">
              <p className="mb-5 text-xs font-semibold uppercase tracking-[0.24em] text-[#17624b]">
                Clinical revenue operations
              </p>
              <h1 className="text-4xl font-semibold leading-tight tracking-[-0.03em] text-[#18241f] xl:text-5xl">
                Responsible recovery for better care.
              </h1>
              <p className="mt-6 max-w-sm text-base leading-7 text-[#52615a]">
                A secure workspace for Kenyan healthcare teams managing claims,
                denials, and appeals with clear human oversight.
              </p>
            </div>
          </div>

          <div className="flex items-end justify-between border-t border-[#17624b]/25 pt-6 text-xs uppercase tracking-[0.18em] text-[#52615a]">
            <span>Kenya</span>
            <span>Claims operations</span>
          </div>

          <div
            aria-hidden="true"
            className="absolute bottom-28 right-14 h-32 w-32 text-[#17624b]/10"
          >
            <span className="absolute left-1/2 top-0 h-full w-8 -translate-x-1/2 bg-current" />
            <span className="absolute left-0 top-1/2 h-8 w-full -translate-y-1/2 bg-current" />
          </div>
        </aside>

        <section className="flex min-h-screen items-center border-t-4 border-[#17624b] bg-[#faf9f5]/95 lg:border-t-0">
          {children}
        </section>
      </div>
    </main>
  );
}
