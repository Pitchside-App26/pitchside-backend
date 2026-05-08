import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-forest text-cream shadow hover:bg-forest-dark',
        forest: 'bg-forest text-cream shadow hover:bg-forest-dark',
        ink: 'bg-ink text-cream shadow hover:bg-ink-80',
        signal: 'bg-signal text-ink shadow hover:bg-signal-dark font-semibold',
        destructive: 'bg-red-600 text-cream shadow-sm hover:bg-red-700',
        outline: 'border border-cream-border bg-transparent shadow-sm hover:bg-cream-dark text-ink',
        'outline-dark': 'border border-cream/30 bg-transparent text-cream hover:bg-cream/10',
        secondary: 'bg-cream-dark text-ink shadow-sm hover:bg-cream-border',
        ghost: 'hover:bg-cream-dark hover:text-ink',
        link: 'text-forest underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-11 rounded-md px-8 text-base',
        xl: 'h-14 rounded-lg px-10 text-base',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
