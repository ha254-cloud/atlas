import Link from "next/link";
import { AtlasMark } from "@/components/brand/atlas-mark";
import { RecoveryJourneyScene } from "@/components/home/recovery-journey-scene";

const capabilities = [
  {
    number: "01",
    title: "See the work clearly",
    body: "Bring claims, documents, denials, tasks, and payer activity into one operational record.",
  },
  {
    number: "02",
    title: "Recover with discipline",
    body: "Prioritise opportunities, prepare evidence, manage appeals, and keep human approval explicit.",
  },
  {
    number: "03",
    title: "Account for every result",
    body: "Reconcile payments, attribute recoveries, and preserve the history behind each decision.",
  },
];

const controls = [
  "Role-based access",
  "Tenant-isolated records",
  "Human approval",
  "Versioned evidence",
  "Immutable audit history",
  "Traceable integrations",
];

export default function HomePage() {
  return (
    <main className="atlas-public-surface min-h-screen bg-[#f8fbf9] text-[#17332f]">
      <a
        href="#main-content"
        className="sr-only z-50 bg-[#173f33] px-4 py-3 text-white focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to content
      </a>

      <header className="border-b border-[#145d55]/20">
        <div className="mx-auto flex min-h-20 max-w-[1480px] items-center justify-between px-5 sm:px-8 lg:px-12">
          <Link href="/" aria-label="Atlas home" className="group flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center border border-[#145d55] text-[#145d55] transition-colors group-hover:bg-[#145d55] group-hover:text-white">
              <AtlasMark className="h-6 w-6" />
            </span>
            <span>
              <span className="block font-editorial text-xl font-bold leading-none tracking-[-0.02em]">
                Atlas
              </span>
              <span className="mt-1 block text-[11px] font-semibold uppercase tracking-[0.12em] text-[#48635d]">
                Health Systems
              </span>
            </span>
          </Link>

          <nav aria-label="Primary navigation" className="hidden items-center gap-8 lg:flex">
            <a className="public-nav-link" href="#method">
              Method
            </a>
            <a className="public-nav-link" href="#platform">
              Platform
            </a>
            <a className="public-nav-link" href="#governance">
              Governance
            </a>
            <a className="public-nav-link" href="#standards">
              Standards
            </a>
          </nav>

          <div className="flex items-center gap-2 sm:gap-3">
            <Link
              href="/login"
              className="border border-[#145d55]/40 px-3 py-2.5 text-sm font-semibold uppercase tracking-[0.08em] transition-colors hover:border-[#145d55] hover:bg-white/70 sm:px-5"
            >
              Sign in
            </Link>
            <Link
              href="/register?intent=request-access"
              className="hidden bg-[#14766c] px-5 py-3 text-sm font-semibold uppercase tracking-[0.08em] text-white transition-colors hover:bg-[#105d55] sm:inline-block"
            >
              Request access
            </Link>
          </div>
        </div>
      </header>

      <section
        id="main-content"
        className="mx-auto grid max-w-[1480px] border-x border-[#145d55]/15 lg:min-h-[740px] lg:grid-cols-[1.08fr_0.92fr]"
      >
        <div className="flex flex-col justify-between border-b border-[#145d55]/16 px-5 py-16 sm:px-10 sm:py-20 lg:border-b-0 lg:border-r lg:px-14 lg:py-24 xl:px-20">
          <div>
            <p className="mb-8 flex items-center gap-4 text-xs font-bold uppercase tracking-[0.14em] text-[#b74a35]">
              <span className="h-px w-12 bg-[#b74a35]" />
              Healthcare revenue recovery
            </p>
            <h1 className="max-w-4xl font-editorial text-[clamp(3.6rem,7.5vw,7.4rem)] font-bold leading-[0.91] tracking-[-0.055em] text-[#145d55]">
              Recover revenue.
              <br />
              Preserve trust.
            </h1>
            <p className="mt-9 max-w-2xl text-lg leading-8 text-[#405b55]">
              Atlas gives healthcare teams one disciplined place to investigate
              denied claims, prepare evidence, approve appeals, track payments,
              and account for every action.
            </p>
            <div className="mt-10 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/register?intent=recovery-practice"
                className="bg-[#14766c] px-7 py-4 text-center text-sm font-bold uppercase tracking-[0.08em] text-white transition-colors hover:bg-[#105d55]"
              >
                Build your recovery practice
              </Link>
              <a
                href="#method"
                className="border border-[#145d55]/40 px-7 py-4 text-center text-sm font-bold uppercase tracking-[0.08em] transition-colors hover:border-[#145d55] hover:bg-white/70"
              >
                Explore the method
              </a>
            </div>
          </div>

          <div className="mt-16 grid gap-5 border-t border-[#145d55]/20 pt-6 text-xs font-bold uppercase tracking-[0.1em] text-[#48635d] sm:grid-cols-3 lg:mt-20">
            <span>Built for Kenya</span>
            <span>Human governed</span>
            <span>Evidence preserved</span>
          </div>
        </div>

        <div className="atlas-ledger-grid relative flex items-center px-5 py-12 sm:px-10 lg:px-14 xl:px-20">
          <RecoveryJourneyScene />
        </div>
      </section>

      <section id="method" className="bg-[#e3f2ee] text-[#173d38]">
        <div className="mx-auto max-w-[1480px] px-5 py-20 sm:px-10 lg:px-14 lg:py-28 xl:px-20">
          <div className="grid gap-10 border-b border-[#145d55]/20 pb-12 lg:grid-cols-[0.75fr_1.25fr]">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#b74a35]">
              The Atlas method
            </p>
            <h2 className="max-w-4xl font-editorial text-4xl font-bold leading-tight tracking-[-0.035em] sm:text-5xl lg:text-6xl">
              A recovery practice built on clarity, judgement, and proof.
            </h2>
          </div>

          <div className="grid lg:grid-cols-3">
            {capabilities.map((capability) => (
              <article
                key={capability.number}
                className="border-b border-[#145d55]/15 py-10 lg:border-b-0 lg:border-r lg:border-[#145d55]/20 lg:px-9 lg:first:pl-0 lg:last:border-r-0 lg:last:pr-0"
              >
                <p className="font-editorial text-2xl font-bold text-[#14766c]">
                  {capability.number}
                </p>
                <h3 className="mt-12 font-editorial text-2xl font-bold">
                  {capability.title}
                </h3>
                <p className="mt-4 max-w-sm text-base leading-7 text-[#405b55]">
                  {capability.body}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="platform" className="border-b border-[#145d55]/15 bg-white">
        <div className="mx-auto grid max-w-[1480px] lg:grid-cols-2">
          <div className="border-b border-[#145d55]/15 px-5 py-20 sm:px-10 lg:border-b-0 lg:border-r lg:px-14 lg:py-28 xl:px-20">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#b74a35]">
              One operating record
            </p>
            <h2 className="mt-7 max-w-xl font-editorial text-4xl font-bold leading-tight tracking-[-0.035em] text-[#145d55] sm:text-5xl">
              From denial to verified recovery.
            </h2>
            <p className="mt-7 max-w-xl text-lg leading-8 text-[#405b55]">
              Atlas connects the work that is usually scattered across
              spreadsheets, inboxes, payer portals, and individual memory.
              Every handoff has an owner. Every decision keeps its context.
            </p>
          </div>

          <div className="grid sm:grid-cols-2">
            {[
              ["Claims", "A complete, searchable operational record."],
              ["Recovery", "Prioritised work with accountable ownership."],
              ["Appeals", "Evidence preparation with human approval."],
              ["Payments", "Reconciliation from expected to received."],
              ["Documents", "Controlled evidence linked to the work."],
              ["Integrations", "Visible connection health and exchange history."],
            ].map(([title, body], index) => (
              <article
                key={title}
                className={`min-h-48 border-[#173f33]/20 p-7 ${
                  index < 4 ? "border-b" : ""
                } ${index % 2 === 0 ? "sm:border-r" : ""}`}
              >
                <p className="text-xs font-bold uppercase tracking-[0.1em] text-[#b74a35]">
                  {String(index + 1).padStart(2, "0")}
                </p>
                <h3 className="mt-7 font-editorial text-xl font-bold text-[#145d55]">
                  {title}
                </h3>
                <p className="mt-3 text-base leading-7 text-[#405b55]">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="governance" className="bg-[#edf5f2]">
        <div className="mx-auto grid max-w-[1480px] lg:grid-cols-[0.9fr_1.1fr]">
          <div className="border-b border-[#145d55]/15 px-5 py-20 sm:px-10 lg:border-b-0 lg:border-r lg:px-14 lg:py-28 xl:px-20">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#b74a35]">
              Designed for scrutiny
            </p>
            <blockquote className="mt-8 max-w-2xl font-editorial text-4xl font-bold leading-[1.15] tracking-[-0.035em] text-[#145d55] sm:text-5xl">
              Technology can assist the work. People remain accountable for the decision.
            </blockquote>
          </div>

          <div className="px-5 py-20 sm:px-10 lg:px-14 lg:py-28 xl:px-20">
            <p className="max-w-2xl text-lg leading-8 text-[#405b55]">
              Revenue recovery touches patient records, clinical evidence, payer
              obligations, and hospital finances. Atlas is built so authorised
              teams can explain who acted, what changed, why it changed, and what
              evidence supported the outcome.
            </p>
            <div className="mt-12 grid border-l border-t border-[#145d55]/25 sm:grid-cols-2">
              {controls.map((control) => (
                <div
                  key={control}
                  className="border-b border-r border-[#145d55]/25 px-5 py-5 text-sm font-bold uppercase tracking-[0.06em]"
                >
                  {control}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="standards" className="bg-white">
        <div className="mx-auto grid max-w-[1480px] items-end gap-12 px-5 py-20 sm:px-10 lg:grid-cols-[1.15fr_0.85fr] lg:px-14 lg:py-28 xl:px-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#b74a35]">
              Interoperability, deliberately governed
            </p>
            <h2 className="mt-7 max-w-3xl font-editorial text-4xl font-bold leading-tight tracking-[-0.035em] text-[#145d55] sm:text-5xl lg:text-6xl">
              Built to meet healthcare systems where they are.
            </h2>
          </div>
          <div>
            <p className="text-lg leading-8 text-[#405b55]">
              Connector-based workflows support payer portals, secure file
              exchange, APIs, and FHIR-based claims exchange. Connection health,
              credentials, failures, and evidence remain visible to authorised
              operators.
            </p>
            <p className="mt-6 border-l-2 border-[#b74a35] pl-5 text-base leading-7 text-[#405b55]">
              Availability and certification vary by integration. Atlas presents
              connection status plainly and does not treat technical readiness as
              regulatory approval.
            </p>
          </div>
        </div>
      </section>

      <section className="border-y border-[#e5b5a7] bg-[#fbe8e0] text-[#4c302b]">
        <div className="mx-auto flex max-w-[1480px] flex-col gap-8 px-5 py-16 sm:px-10 lg:flex-row lg:items-center lg:justify-between lg:px-14 xl:px-20">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#813e32]">
              Begin with the work that matters
            </p>
            <h2 className="mt-4 font-editorial text-3xl font-bold text-[#58332c] sm:text-4xl">
              Build a recovery practice your institution can trust.
            </h2>
          </div>
          <Link
            href="/register?intent=request-access"
            className="shrink-0 border border-[#a63f2e] bg-[#a63f2e] px-7 py-4 text-center text-sm font-bold uppercase tracking-[0.08em] text-white transition-colors hover:bg-transparent hover:text-[#873324]"
          >
            Request access
          </Link>
        </div>
      </section>

      <footer className="bg-[#e7f1ee] text-[#173d38]">
        <div className="mx-auto grid max-w-[1480px] gap-12 px-5 py-14 sm:px-10 lg:grid-cols-[1fr_auto] lg:px-14 xl:px-20">
          <div>
            <div className="flex items-center gap-3">
              <AtlasMark className="h-7 w-7" />
              <span className="font-editorial text-xl font-bold">Atlas Health Systems</span>
            </div>
            <p className="mt-4 max-w-md text-base leading-7 text-[#405b55]">
              Healthcare revenue recovery infrastructure for accountable teams.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-x-10 gap-y-3 text-sm text-[#315b54] sm:grid-cols-3">
            <a href="#method" className="hover:text-[#a63f2e]">Method</a>
            <a href="#platform" className="hover:text-[#a63f2e]">Platform</a>
            <a href="#governance" className="hover:text-[#a63f2e]">Governance</a>
            <a href="#standards" className="hover:text-[#a63f2e]">Standards</a>
            <Link href="/login" className="hover:text-[#a63f2e]">Sign in</Link>
            <Link href="/register?intent=request-access" className="hover:text-[#a63f2e]">Request access</Link>
          </div>
        </div>
        <div className="border-t border-[#145d55]/15">
          <div className="mx-auto flex max-w-[1480px] flex-col gap-2 px-5 py-5 text-xs font-bold uppercase tracking-[0.08em] text-[#48635d] sm:flex-row sm:justify-between sm:px-10 lg:px-14 xl:px-20">
            <span>Atlas Health Systems</span>
            <span>Nairobi, Kenya</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
