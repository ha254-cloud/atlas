"use client";

import { useState } from "react";
import { Loader2, ShieldCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getErrorMessage } from "@/lib/api-client";
import { integrationsService } from "@/services/integrations-service";

interface Props {
  onCreated: () => void;
  onCancel: () => void;
}

export function SftpIntegrationForm({ onCreated, onCancel }: Props) {
  const [hostname, setHostname] = useState("");
  const [port, setPort] = useState("22");
  const [username, setUsername] = useState("");
  const [authMethod, setAuthMethod] = useState<"password" | "private_key">("password");
  const [password, setPassword] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [remotePath, setRemotePath] = useState("/claims");
  const [filePattern, setFilePattern] = useState("*.csv");
  const [fingerprint, setFingerprint] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await integrationsService.create({
        provider: "sftp",
        settings: {
          hostname,
          port: Number(port),
          username,
          remote_path: remotePath,
          file_pattern: filePattern,
          host_key_sha256: fingerprint,
        },
        ...(authMethod === "password" ? { access_token: password } : { refresh_token: privateKey }),
      });
      onCreated();
    } catch (caught) {
      setError(getErrorMessage(caught, "SFTP connection could not be saved."));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="border-y bg-muted/20 p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-700" />
          <h3 className="text-sm font-semibold">Secure SFTP claim feed</h3>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onCancel} title="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <label className="space-y-1 text-xs font-medium">Host<Input required value={hostname} onChange={(event) => setHostname(event.target.value)} placeholder="sftp.hospital.org" /></label>
        <label className="space-y-1 text-xs font-medium">Port<Input required type="number" min="1" max="65535" value={port} onChange={(event) => setPort(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium">Username<Input required value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
        <label className="space-y-1 text-xs font-medium">Authentication<select value={authMethod} onChange={(event) => setAuthMethod(event.target.value as "password" | "private_key")} className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"><option value="password">Password</option><option value="private_key">SSH private key</option></select></label>
        {authMethod === "password" ? <label className="space-y-1 text-xs font-medium">Password<Input required type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" /></label> : <label className="space-y-1 text-xs font-medium md:col-span-2"><span>SSH private key</span><textarea required value={privateKey} onChange={(event) => setPrivateKey(event.target.value)} className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs" /></label>}
        <label className="space-y-1 text-xs font-medium">Remote folder<Input required value={remotePath} onChange={(event) => setRemotePath(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium">File pattern<Input required value={filePattern} onChange={(event) => setFilePattern(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium md:col-span-2">Host key fingerprint<Input required value={fingerprint} onChange={(event) => setFingerprint(event.target.value)} placeholder="SHA256:..." /></label>
      </div>
      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={pending}>{pending && <Loader2 className="h-4 w-4 animate-spin" />}Save SFTP feed</Button>
      </div>
    </form>
  );
}
