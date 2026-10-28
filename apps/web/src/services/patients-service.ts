import { api } from "@/lib/api-client";
import type { Patient, PatientCreateInput, PatientUpdateInput } from "@/types";

export interface PatientListParams {
  limit?: number;
  offset?: number;
  search?: string;
  date_of_birth?: string;
}

export const patientsService = {
  list: (params?: PatientListParams) =>
    api.get<Patient[]>("/api/v1/patients", {
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
      ...(params?.search ? { search: params.search } : {}),
      ...(params?.date_of_birth ? { date_of_birth: params.date_of_birth } : {}),
    }),
  get: (id: number) => api.get<Patient>(`/api/v1/patients/${id}`),
  create: (payload: PatientCreateInput) =>
    api.post<Patient>("/api/v1/patients", payload),
  update: (id: number, payload: PatientUpdateInput) =>
    api.put<Patient>(`/api/v1/patients/${id}`, payload),
};