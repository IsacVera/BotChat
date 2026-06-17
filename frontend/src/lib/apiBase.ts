const envApiBase = (import.meta as any).env?.VITE_API_BASE;

export const apiBase = envApiBase || new URL('/botchat-api', window.location.origin).toString();