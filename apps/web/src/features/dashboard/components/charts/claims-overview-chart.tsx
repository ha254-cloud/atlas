"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface TrendPoint {
  month: string;
  claims: number;
  estimated_value: number;
}

const FALLBACK = [
  { month: "Jan", claims: 0, estimated_value: 0 },
  { month: "Feb", claims: 0, estimated_value: 0 },
];

export function ClaimsOverviewChart({ data }: { data?: TrendPoint[] }) {
  const chartData = data?.length ? data : FALLBACK;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Claims Overview</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={chartData} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="colorClaims" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "6px",
                fontSize: "12px",
              }}
            />
            <Area type="monotone" dataKey="claims" stroke="#3b82f6" fill="url(#colorClaims)" strokeWidth={2} name="Claims" />
            <Area type="monotone" dataKey="estimated_value" stroke="#10b981" fill="url(#colorRecovered)" strokeWidth={2} name="Estimated Recovery" />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
