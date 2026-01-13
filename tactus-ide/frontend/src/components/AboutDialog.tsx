import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Info, ExternalLink } from 'lucide-react';

interface AboutInfo {
  version: string;
  name: string;
  description: string;
  author: string;
  license: string;
  repository: string;
  documentation: string;
  issues: string;
}

interface AboutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export const AboutDialog: React.FC<AboutDialogProps> = ({ open, onOpenChange }) => {
  const [aboutInfo, setAboutInfo] = useState<AboutInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      // Fetch about info when dialog opens
      fetch('/api/about')
        .then((res) => {
          if (!res.ok) throw new Error('Failed to fetch about info');
          return res.json();
        })
        .then((data) => {
          setAboutInfo(data);
          setLoading(false);
        })
        .catch((err) => {
          console.error('Error fetching about info:', err);
          setError(err.message);
          setLoading(false);
        });
    }
  }, [open]);

  const openLink = (url: string) => {
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            About Tactus
          </DialogTitle>
          <DialogDescription>
            {aboutInfo?.description || 'A Lua-based DSL for agentic workflows'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {loading && (
            <div className="text-sm text-muted-foreground">Loading...</div>
          )}

          {error && (
            <div className="text-sm text-red-500">
              Error loading version information: {error}
            </div>
          )}

          {aboutInfo && (
            <>
              {/* Version - prominent display */}
              <div className="space-y-1">
                <div className="text-3xl font-semibold">v{aboutInfo.version}</div>
              </div>

              {/* Links */}
              <div className="space-y-2">
                <div className="text-sm font-medium">Links</div>
                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => openLink(aboutInfo.repository)}
                    className="flex items-center gap-2 text-sm text-primary hover:underline text-left"
                  >
                    <ExternalLink className="h-3 w-3" />
                    GitHub Repository
                  </button>
                  <button
                    onClick={() => openLink(aboutInfo.documentation)}
                    className="flex items-center gap-2 text-sm text-primary hover:underline text-left"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Documentation
                  </button>
                  <button
                    onClick={() => openLink(aboutInfo.issues)}
                    className="flex items-center gap-2 text-sm text-primary hover:underline text-left"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Report an Issue
                  </button>
                </div>
              </div>

              {/* License */}
              <div className="space-y-1">
                <div className="text-sm font-medium">License</div>
                <div className="text-sm text-muted-foreground">{aboutInfo.license}</div>
              </div>

              {/* Author */}
              <div className="space-y-1">
                <div className="text-sm font-medium">Author</div>
                <div className="text-sm text-muted-foreground">{aboutInfo.author}</div>
              </div>
            </>
          )}
        </div>

        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
