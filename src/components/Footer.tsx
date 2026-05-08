import Link from 'next/link'
import { ArrowUpRight } from 'lucide-react'

const FOOTER_LINKS = {
  Product: [
    { href: '/browse', label: 'Browse cars' },
    { href: '/sell', label: 'Sell your car' },
    { href: '/#how', label: 'How it works' },
    { href: '/#compare', label: 'Compare options' },
  ],
  Company: [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/operator', label: 'Operator' },
  ],
  Legal: [
    { href: '#', label: 'Privacy policy' },
    { href: '#', label: 'Terms of service' },
    { href: '#', label: 'Cookie policy' },
  ],
}

export function Footer() {
  return (
    <footer className="border-t border-cream-border bg-cream-dark">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 gap-8 lg:grid-cols-5">
          {/* Brand */}
          <div className="col-span-2">
            <Link href="/" className="flex items-center gap-2 group mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ink">
                <ArrowUpRight className="h-4 w-4 text-cream" strokeWidth={2.5} aria-hidden="true" />
              </div>
              <span className="font-serif text-xl text-ink">Handover</span>
            </Link>
            <p className="text-sm text-ink-60 max-w-xs leading-relaxed">
              The car is yours. The finance is theirs. We sort the rest.
            </p>
            <p className="mt-4 font-mono text-[10px] uppercase tracking-widest text-ink-40">
              Pending FCA authorisation · Funds held in escrow
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(FOOTER_LINKS).map(([category, links]) => (
            <div key={category}>
              <p className="eyebrow mb-4">{category}</p>
              <ul className="space-y-2.5">
                {links.map(link => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-ink-60 hover:text-ink transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom strip */}
        <div className="mt-10 flex flex-col gap-2 border-t border-cream-border pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-40">
            &copy; {new Date().getFullYear()} Handover Technologies Ltd. All rights reserved.
          </p>
          <p className="font-mono text-[10px] uppercase tracking-widest text-ink-40">
            v0.1 · investor preview
          </p>
        </div>
      </div>
    </footer>
  )
}
