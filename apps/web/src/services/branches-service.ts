import { api } from "@/lib/api-client";
import type { Branch, BranchMembership, Department } from "@/types";

export const branchesService = {
  list: () => api.get<Branch[]>("/api/v1/branches"),
  create: (payload: { name: string; code: string; reason: string }) =>
    api.post<Branch>("/api/v1/branches", payload),
  listDepartments: (branchId: number) =>
    api.get<Department[]>(`/api/v1/branches/${branchId}/departments`),
  createDepartment: (
    branchId: number,
    payload: { name: string; code: string; reason: string },
  ) => api.post<Department>(`/api/v1/branches/${branchId}/departments`, payload),
  listMemberships: (branchId: number) =>
    api.get<BranchMembership[]>(`/api/v1/branches/${branchId}/memberships`),
  assignMembership: (
    branchId: number,
    payload: { user_id: number; role_template: string; reason: string },
  ) => api.post<BranchMembership>(`/api/v1/branches/${branchId}/memberships`, payload),
};