import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';
import { AlertCircle } from 'lucide-react';

interface AuthErrorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  errorMessage?: string;
  onOpenSettings: () => void;
}

export const AuthErrorDialog: React.FC<AuthErrorDialogProps> = ({
  open,
  onOpenChange,
  errorMessage,
  onOpenSettings,
}) => {
  const handleOpenSettings = () => {
    onOpenSettings();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-amber-500 mt-0.5" />
            <div>
              <DialogTitle>API Authentication Required</DialogTitle>
              <DialogDescription className="mt-2">
                Your API credentials are missing or invalid.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <div className="py-4">
          {errorMessage && (
            <p className="text-sm text-muted-foreground mb-4 font-mono bg-muted p-3 rounded">
              {errorMessage}
            </p>
          )}
          <p className="text-sm">
            Would you like to configure your API keys now?
          </p>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Not Now
          </Button>
          <Button onClick={handleOpenSettings}>
            Open Settings
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
