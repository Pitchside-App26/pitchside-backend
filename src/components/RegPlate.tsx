import { cn } from '@/lib/utils'

interface RegPlateProps {
  reg: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizeClasses = {
  sm: 'h-7 px-2 text-sm gap-1.5',
  md: 'h-9 px-3 text-base gap-2',
  lg: 'h-12 px-4 text-xl gap-2.5',
}

export function RegPlate({ reg, size = 'md', className }: RegPlateProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center rounded border-2 border-ink/20 bg-signal font-mono font-bold tracking-widest text-ink shadow-sm',
        sizeClasses[size],
        className
      )}
      aria-label={`Registration plate: ${reg}`}
    >
      <span className="flex flex-col items-center justify-center rounded-sm bg-blue-700 px-0.5 text-white leading-tight"
        style={{ fontSize: '60%', minWidth: '14px' }}>
        <span style={{ fontSize: '80%' }}>GB</span>
        <span>⭐</span>
      </span>
      <span>{reg.toUpperCase()}</span>
    </div>
  )
}
