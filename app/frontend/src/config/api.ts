/**
 * API configuration
 * Centralized API base URL that can be configured via environment variables
 */
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
