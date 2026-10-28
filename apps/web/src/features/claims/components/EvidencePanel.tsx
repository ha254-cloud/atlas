import { CheckCircle, XCircle, HelpCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface EvidenceItem {
  source: string;
  status: "confirmed" | "not_applicable" | "unknown";
  note?: string;
}

interface Props {
  denial_code?: string | null;
}

function deriveEvidence(denial_code?: string | null): EvidenceItem[] {
  return [
    {
      source: "Payer denial notice",
      status: denial_code ? "confirmed" : "unknown",
      note: denial_code ? `Recorded denial code: ${denial_code}` : "No denial code recorded",
    },
    {
      source: "Payer contract and benefit schedule",
      status: "unknown",
      note: "Requires a reviewed, effective contract or SHA benefit schedule",
    },
    {
      source: "Payer submission guidance",
      status: "unknown",
      note: "Requires verified payer or SHA operating guidance",
    },
    {
      source: "Clinical and billing documents",
      status: "unknown",
      note: "Confirm supporting records before approval",
    },
  ];
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  confirmed:       <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />,
  not_applicable:  <XCircle className="h-4 w-4 text-muted-foreground shrink-0" />,
  unknown:         <HelpCircle className="h-4 w-4 text-yellow-500 shrink-0" />,
};

export function EvidencePanel({ denial_code }: Props) {
  const evidence = deriveEvidence(denial_code);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Evidence</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {evidence.map((item) => (
          <div key={item.source} className="flex items-start gap-2.5">
            {STATUS_ICON[item.status]}
            <div>
              <p className="text-sm font-medium">{item.source}</p>
              {item.note && <p className="text-xs text-muted-foreground">{item.note}</p>}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
