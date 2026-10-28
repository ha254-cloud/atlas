export interface Patient {
  id: number;
  first_name: string;
  last_name: string;
  medical_record_number: string;
  date_of_birth: string;
  created_at: string;
  updated_at: string;
}

export interface PatientCreateInput {
  first_name: string;
  last_name: string;
  medical_record_number: string;
  date_of_birth: string;
}

export type PatientUpdateInput = Partial<PatientCreateInput>;