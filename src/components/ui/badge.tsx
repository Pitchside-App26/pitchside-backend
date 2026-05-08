import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-forest text-cream shadow hover:bg-forest-dark',
        forest: 'border-transparent bg-forest-tint text-forest',
        signal: 'border-transparent bg-signal text-ink',
        amber: 'border-transparent bg-amber-tint text-amber border-amber/20',
        secondary: 'border-transparent bg-cream-dark text-ink hover:bg-cream-border',
        destructive: 'border-transparent bg-red-100 text-red-800',
        outline: 'text-ink border-cream-border',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
