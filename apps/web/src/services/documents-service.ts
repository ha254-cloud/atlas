import { api, apiClient } from "@/lib/api-client";
import type { ClaimDocument, DocumentType } from "@/types";

export const documentsService = {
  listForClaim: (claimId: number) =>
    api.get<ClaimDocument[]>(`/api/v1/claims/${claimId}/documents`),

  upload: (claimId: number, file: File, documentType: DocumentType) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    return api.upload<ClaimDocument>(`/api/v1/claims/${claimId}/documents`, formData);
  },

  summarize: (documentId: number) =>
    api.post<ClaimDocument>(`/api/v1/documents/${documentId}/summarize`),

  download: async (document: ClaimDocument) => {
    const response = await apiClient.get<Blob>(
      `/api/v1/documents/${document.id}/download`,
      { responseType: "blob" },
    );
    const url = URL.createObjectURL(response.data);
    const link = window.document.createElement("a");
    link.href = url;
    link.download = document.filename;
    link.click();
    URL.revokeObjectURL(url);
  },
};