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

export function ShaIntegrationForm({ onCreated, onCancel }: Props) {
  const [baseUrl, setBaseUrl] = useState("https://hie-test.dha.go.ke/fhir");
  const [tokenUrl, setTokenUrl] = useState("");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [providerNumber, setProviderNumber] = useState("");
  const [facilityName, setFacilityName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await integrationsService.create({
        provider: "sha",
        settings: {
          base_url: baseUrl,
          token_url: tokenUrl,
          client_id: clientId,
          provider_number: providerNumber,
          facility_name: facilityName,
          scopes: "system/Claim.write system/ClaimResponse.read system/Coverage.read",
          token_auth_method: "client_secret_basic",
        },
        credentials: {
          kind: "oauth2_client_credentials",
          client_secret: clientSecret,
        },
      });
      onCreated();
    } catch (caught) {
      setError(getErrorMessage(caught, "SHA connection could not be saved."));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="border-y bg-muted/20 p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-700" />
          <div>
            <h3 className="text-sm font-semibold">DHA/SHA eClaims connection</h3>
            <p className="text-xs text-muted-foreground">
              Use only endpoints and OAuth credentials issued through DHA onboarding.
            </p>
          </div>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onCancel} title="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        <label className="space-y-1 text-xs font-medium">
          FHIR base URL
          <Input
            required
            type="url"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-xs font-medium">
          OAuth token URL
          <Input
            required
            type="url"
            value={tokenUrl}
            onChange={(event) => setTokenUrl(event.target.value)}
            placeholder="DHA-issued HTTPS token endpoint"
          />
        </label>
        <label className="space-y-1 text-xs font-medium">
          OAuth client ID
          <Input
            required
            value={clientId}
            onChange={(event) => setClientId(event.target.value)}
            autoComplete="username"
          />
        </label>
        <label className="space-y-1 text-xs font-medium">
          OAuth client secret
          <Input
            required
            type="password"
            value={clientSecret}
            onChange={(event) => setClientSecret(event.target.value)}
            autoComplete="new-password"
          />
        </label>
        <label className="space-y-1 text-xs font-medium">
          DHA/SHA provider number
          <Input
            required
            value={providerNumber}
            onChange={(event) => setProviderNumber(event.target.value)}
            placeholder="PROV-KE-..."
          />
        </label>
        <label className="space-y-1 text-xs font-medium">
          Certified facility name
          <Input
            required
            value={facilityName}
            onChange={(event) => setFacilityName(event.target.value)}
          />
        </label>
      </div>
      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={pending}>
          {pending && <Loader2 className="h-4 w-4 animate-spin" />}
          Save SHA connection
        </Button>
      </div>
    </form>
  );
}
