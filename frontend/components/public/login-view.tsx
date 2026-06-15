"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

interface LoginViewProps {
  onClose: () => void;
  onSuccess?: () => void;
}

export function LoginView({ onClose }: LoginViewProps) {
  return (
    <div className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Public accounts are not available yet.</h2>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close login"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-2 text-sm text-muted-foreground">
        <p>Google login/email login will be added in a later phase.</p>
        <p>Guest reading is still available.</p>
      </div>

      <div className="mt-5 flex justify-end">
        <Button type="button" variant="outline" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}
