
export type AppStep = 'NAME_INPUT' | 'PDF_UPLOAD' | 'PROCESSING' | 'CHAT' | 'HOW_IT_WORKS';

export const AppStep = {
  NAME_INPUT: 'NAME_INPUT',
  PDF_UPLOAD: 'PDF_UPLOAD',
  PROCESSING: 'PROCESSING',
  CHAT: 'CHAT',
  HOW_IT_WORKS: 'HOW_IT_WORKS'
} as const;

export interface Message {
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
}

export interface UserData {
  name: string;
  fileName?: string;
}
