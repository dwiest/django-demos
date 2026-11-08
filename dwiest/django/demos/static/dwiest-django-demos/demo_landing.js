import React, { useState } from "react";
import { Home, Folder, Image as ImageIcon, Timer, Globe, ChevronDown, ChevronRight, ExternalLink } from "lucide-react";

// Minimal card + sidebar UI using Tailwind
// Drop this into your project or use as a starting point.

const demos = [
  {
    key: "files",
    title: "Files",
    icon: <Folder className="h-4 w-4" />,
    links: [
      { label: "File manager", href: "/files/manager/" },
    ],
  },
  {
    key: "graphics",
    title: "Graphics",
    icon: <ImageIcon className="h-4 w-4" />,
    links: [
      { label: "QR code generator", href: "/graphics/qr/" },
    ],
  },
  {
    key: "otp",
    title: "OTP",
    icon: <Timer className="h-4 w-4" />,
    links: [
      { label: "Time-based", href: "/otp/time/" },
    ],
  },
  {
    key: "web",
    title: "Web",
    icon: <Globe className="h-4 w-4" />,
    links: [
      { label: "Bookmarks", href: "/web/bookmarks/" },
      { label: "Expense Tracker", href: "/web/expenses/" },
      { label: "Google reCAPTCHA", href: "/web/recaptcha/" },
      { label: "Inventory Tracker", href: "/web/inventory/" },
      { label: "Invoicer", href: "/web/invoicer/" },
      { label: "Journal", href: "/web/journal/" },
      { label: "Websockets", href: "/web/ws/" },
      { label: "Selenium", href: "/web/selenium/" },
    ],
  },
];

function Sidebar({ openSections, onToggle }) {
  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-neutral-900 text-neutral-100 shadow-lg">
      <div className="px-4 py-4 border-b border-neutral-800 flex items-center gap-2">
        <Home className="h-5 w-5" />
        <span className="font-semibold tracking-wide">Django Demos</span>
      </div>
      <nav className="px-2 py-3 space-y-1 overflow-y-auto h-[calc(100vh-56px)]">
        {demos.map((group) => {
          const isOpen = openSections[group.key];
          return (
            <div key={group.key} className="rounded-xl">
              <button
                className="w-full flex items-center justify-between rounded-lg px-3 py-2 hover:bg-neutral-800/70"
                onClick={() => onToggle(group.key)}
              >
                <div className="flex items-center gap-2">
                  {group.icon}
                  <span className="text-sm font-medium">{group.title}</span>
                </div>
                {isOpen ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </button>
              {isOpen && (
                <ul className="mt-1 space-y-1 pl-9 pr-2">
                  {group.links.map((l) => (
                    <li key={l.href}>
                      <a
                        className="block rounded-md px-2 py-1.5 text-sm text-neutral-300 hover:text-white hover:bg-neutral-800/60"
                        href={l.href}
                      >
                        {l.label}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

function Card({ title, children }) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-5 shadow-sm hover:shadow-md transition-shadow">
      <div className="mb-3 text-sm font-semibold tracking-wide text-neutral-700">{title}</div>
      <div className="space-y-1 text-sm">
        {children}
      </div>
    </div>
  );
}

export default function DemoLanding() {
  // Sidebar collapsed by default (all false)
  const [open, setOpen] = useState(() => ({ files: false, graphics: false, otp: false, web: false }));
  const toggle = (k) => setOpen((s) => ({ ...s, [k]: !s[k] }));

  return (
    <div className="min-h-screen bg-neutral-50">
      <Sidebar openSections={open} onToggle={toggle} />

      <main className="ml-64 p-6">
        <header className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Django Demo Apps</h1>
          <a
            href="/"
            className="inline-flex items-center gap-1 text-sm text-neutral-600 hover:text-neutral-900"
          >
            View Source <ExternalLink className="h-4 w-4" />
          </a>
        </header>

        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {demos.map((group) => (
            <Card key={group.key} title={group.title}>
              <ul className="space-y-1">
                {group.links.map((l) => (
                  <li key={l.href}>
                    <a className="text-neutral-900 hover:underline" href={l.href}>{l.label}</a>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </section>

        <footer className="mt-10 text-xs text-neutral-500">
          Built with Django • Minimal CSS via Tailwind classes
        </footer>
      </main>
    </div>
  );
}
