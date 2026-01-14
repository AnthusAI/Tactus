import * as React from "react"

import { cn } from "@/lib/utils"

export interface LogoProps extends React.HTMLAttributes<HTMLDivElement> {
  showText?: boolean;
}

const Logo = React.forwardRef<HTMLDivElement, LogoProps>(
  ({ className, showText = true, ...props }, ref) => {
    return (
      <div ref={ref} className={cn("flex items-baseline gap-[0.01em]", className)} {...props}>
        {showText && (
          <span className="font-extrabold font-alegreya-sc whitespace-nowrap">Tactus</span>
        )}
      </div>
    )
  }
)
Logo.displayName = "Logo"

export { Logo }
