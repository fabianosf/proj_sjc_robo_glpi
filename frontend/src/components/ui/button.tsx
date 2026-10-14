import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

const buttonVariants = cva(
  'inline-flex min-h-9 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-accent text-white hover:opacity-90',
        outline: 'border border-line bg-panel text-ink hover:bg-canvas',
        secondary: 'bg-accent-soft text-accent hover:opacity-80',
        ghost: 'text-ink hover:bg-canvas',
        destructive: 'bg-danger text-white hover:opacity-90',
      },
      size: {
        default: 'min-h-9 px-3 py-2',
        sm: 'min-h-8 px-2.5 py-1.5 text-xs',
        lg: 'min-h-10 px-4 py-2.5',
        icon: 'h-9 w-9 p-0',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }

export function Button({
  asChild = false,
  className,
  size,
  variant,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : 'button'
  return (
    <Component
      className={cn(buttonVariants({ className, size, variant }))}
      {...props}
    />
  )
}
