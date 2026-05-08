import { Nav } from '@/components/Nav'
import { Footer } from '@/components/Footer'

export default function HomePage() {
  return (
    <>
      <Nav />
      <main className="flex-1 flex items-center justify-center py-24">
        <div className="space-y-6 px-4">
          <p className="eyebrow">Milestone 1 — Foundation</p>
          <h1 className="font-serif text-display-lg text-ink">
            Handover
          </h1>
          <p className="text-ink-60 max-w-sm text-sm leading-relaxed">
            Fonts, colours, and tokens confirmed. Full landing page in Milestone 2.
          </p>
          <div className="flex flex-wrap gap-2 pt-2">
            <span className="inline-block px-3 py-1 rounded-full bg-forest text-cream text-xs font-mono">forest</span>
            <span className="inline-block px-3 py-1 rounded-full bg-forest-soft text-forest text-xs font-mono">forest-soft</span>
            <span className="inline-block px-3 py-1 rounded-full bg-signal text-ink text-xs font-mono">signal</span>
            <span className="inline-block px-3 py-1 rounded-full bg-ink text-cream text-xs font-mono">ink</span>
            <span className="inline-block px-3 py-1 rounded-full bg-cream-dark border border-cream-border text-ink text-xs font-mono">cream</span>
          </div>
          <p className="font-serif italic text-display-sm text-forest">
            Instrument Serif italic
          </p>
          <p className="font-mono text-sm tracking-widest uppercase text-forest">
            Geist Mono eyebrow
          </p>
        </div>
      </main>
      <Footer />
    </>
  )
}
