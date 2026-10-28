import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number, currency = "KES"): string {
  const normalizedCurrency = currency.toUpperCase();
  const amount = new Intl.NumberFormat(normalizedCurrency === "KES" ? "en-KE" : "en", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  if (normalizedCurrency === "KES") return `KSh ${amount}`;
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: normalizedCurrency,
    currencyDisplay: "narrowSymbol",
  }).format(value);
}

export function formatDate(value: string | Date): string {
  const d = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(d);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}
