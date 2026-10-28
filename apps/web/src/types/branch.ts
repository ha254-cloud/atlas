export interface Branch {
  id: number;
  organization_id: number;
  name: string;
  code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Department {
  id: number;
  organization_id: number;
  branch_id: number;
  name: string;
  code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BranchMembership {
  id: number;
  organization_id: number;
  branch_id: number;
  user_id: number;
  role_template: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}