import React, { createContext, useContext } from 'react';

export type ProjectInfo = { id: number; code: string; name: string; contract_number?: string | null; status?: string } | null;
export const ProjectContext = createContext<{ project: ProjectInfo; role: string | null; category: string | null }>({ project: null, role: null, category: null });
export const useProject = () => useContext(ProjectContext);

export function categoryOf(role?: string | null): string | null {
  if (!role) return null;
  if (role === 'ADMIN') return '1';
  if (['RE', 'DRE', 'ARE'].includes(role)) return '2.1';
  if (['WORK_INSPECTOR', 'STRUCTURE_INSPECTOR', 'SURVEYOR', 'SENIOR_SURVEYOR', 'MATERIAL_INSPECTOR', 'LAB_TECHNICIAN', 'MATERIAL_ENGINEER'].includes(role)) return '2.2';
  if (['QUANTITY_SURVEYOR', 'DRAFTSPERSON', 'SECRETARY', 'PROJECT_MANAGER', 'VIEWER'].includes(role)) return '2.3';
  if (['DATA_ENCODER', 'OFFICE_ENGINEER', 'CONTRACTOR', 'SITE_ENGINEER'].includes(role)) return '3';
  return null;
}
export const CATEGORY_NAME: Record<string, string> = { '1': 'System Admin', '2.1': 'RE / DRE', '2.2': 'Inspector', '2.3': 'Office', '3': 'Contractor' };
