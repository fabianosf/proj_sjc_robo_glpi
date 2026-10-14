import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/utils'

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn('grid grid-cols-2 rounded-md bg-canvas p-1', className)}
      {...props}
    />
  )
}

export function TabsTrigger({
  className,
  ...props
}: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'rounded-sm px-3 py-2 text-left text-sm font-medium text-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 data-[state=active]:bg-panel data-[state=active]:text-ink data-[state=active]:shadow-sm',
        className,
      )}
      {...props}
    />
  )
}

export const Tabs = TabsPrimitive.Root
export const TabsContent = TabsPrimitive.Content
