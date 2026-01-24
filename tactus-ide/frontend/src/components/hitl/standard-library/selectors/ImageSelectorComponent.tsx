import React from 'react';
import { Check, RotateCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { HITLComponentRendererProps } from '../../types';

/**
 * Image Selector Component
 *
 * Displays a grid of images and allows the user to select one.
 * Optionally supports action buttons like "Regenerate".
 *
 * Metadata schema:
 * ```typescript
 * {
 *   component_type: "image-selector",
 *   data: {
 *     images: Array<{url: string, label: string}>,
 *     aspect_ratio?: "1:1" | "4:3" | "16:9" | "21:9",
 *     allow_multiple?: boolean
 *   },
 *   actions?: Array<{id: string, label: string, style?: string}>
 * }
 * ```
 */
export const ImageSelectorComponent: React.FC<HITLComponentRendererProps> = ({
  item,
  value,
  onValueChange,
  responded
}) => {
  const images = item.metadata?.data?.images || [];
  const actions = item.metadata?.actions || [];
  const aspectRatio = item.metadata?.data?.aspect_ratio || '16:9';

  // Map aspect ratio to Tailwind class
  const aspectClass = {
    '1:1': 'aspect-square',
    '4:3': 'aspect-[4/3]',
    '16:9': 'aspect-video',
    '21:9': 'aspect-[21/9]'
  }[aspectRatio] || 'aspect-video';

  if (images.length === 0) {
    return (
      <div className="text-sm text-muted-foreground p-4 border rounded-md">
        No images provided
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Image grid */}
      <div className="grid grid-cols-2 gap-4">
        {images.map((img: any, idx: number) => {
          const isSelected = value === img.url || (typeof value === 'object' && value?.url === img.url);

          return (
            <button
              key={idx}
              onClick={() => !responded && onValueChange(img.url)}
              disabled={responded}
              className={cn(
                "relative border-2 rounded-lg overflow-hidden transition",
                "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                isSelected
                  ? "border-primary ring-2 ring-primary/20"
                  : "border-border hover:border-primary/50",
                responded && "opacity-70 cursor-not-allowed"
              )}
            >
              <img
                src={img.url}
                alt={img.label || `Image ${idx + 1}`}
                className={cn("w-full object-cover", aspectClass)}
                loading="lazy"
              />

              {/* Selection indicator */}
              {isSelected && (
                <div className="absolute inset-0 bg-primary/10 flex items-center justify-center">
                  <div className="bg-primary rounded-full p-2">
                    <Check className="h-6 w-6 text-primary-foreground" />
                  </div>
                </div>
              )}

              {/* Label */}
              <div className="absolute bottom-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                {img.label || `Image ${idx + 1}`}
              </div>
            </button>
          );
        })}
      </div>

      {/* Action buttons */}
      {actions.length > 0 && !responded && (
        <div className="flex gap-2 justify-end pt-2 border-t">
          {actions.map((action: any) => (
            <Button
              key={action.id}
              variant={action.style === 'secondary' || action.style === 'outline' ? 'outline' : 'default'}
              size="sm"
              onClick={() => onValueChange({ action: action.id })}
              className="gap-2"
            >
              {action.id === 'regenerate' && <RotateCw className="h-4 w-4" />}
              {action.label}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
};
