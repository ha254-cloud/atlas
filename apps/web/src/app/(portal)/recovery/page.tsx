"use client";

import React from "react";
import { Header } from "@/components/layout/header";
import { RecoveryWorkspace } from "@/features/recovery/components/recovery-workspace";

export default function RecoveryPage() {
  return (
    <div className="flex flex-col h-full">
      <Header title="Recovery Workspace" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-6xl">
        <RecoveryWorkspace />
        </div>
      </div>
    </div>
  );
}
