'use client'

import { useEffect, useRef } from 'react'
import { useMotionValue, useSpring, useInView } from 'framer-motion'

interface CountUpProps {
  to: number
  from?: number
  prefix?: string
  suffix?: string
  decimals?: number
  duration?: number
  className?: string
  triggerOnView?: boolean
}

export function CountUp({
  to,
  from = 0,
  prefix = '',
  suffix = '',
  decimals = 0,
  className,
  triggerOnView = false,
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const motionValue = useMotionValue(triggerOnView ? from : from)
  const springValue = useSpring(motionValue, { damping: 22, stiffness: 80 })
  const isInView = useInView(ref, { once: true, margin: '0px 0px -10% 0px' })

  useEffect(() => {
    if (!triggerOnView) {
      // Start after a short delay for page-load animations
      const t = setTimeout(() => motionValue.set(to), 400)
      return () => clearTimeout(t)
    }
  }, [to, motionValue, triggerOnView])

  useEffect(() => {
    if (triggerOnView && isInView) {
      motionValue.set(to)
    }
  }, [isInView, to, motionValue, triggerOnView])

  useEffect(() => {
    const unsubscribe = springValue.on('change', (latest) => {
      if (ref.current) {
        const formatted = latest.toFixed(decimals)
        const withCommas = Number(formatted).toLocaleString('en-GB', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        })
        ref.current.textContent = `${prefix}${withCommas}${suffix}`
      }
    })
    return unsubscribe
  }, [springValue, prefix, suffix, decimals])

  return (
    <span
      ref={ref}
      className={className}
      style={{ fontVariantNumeric: 'tabular-nums' }}
    >
      {prefix}{from.toLocaleString('en-GB')}{suffix}
    </span>
  )
}
