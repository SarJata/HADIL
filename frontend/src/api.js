import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const API_URL = `${API_BASE}/api`;

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

let onUnauthorizedCallback = null;
let onForbiddenCallback = null;

export const setAuthCallbacks = ({ onUnauthorized, onForbidden }) => {
  onUnauthorizedCallback = onUnauthorized;
  onForbiddenCallback = onForbidden;
};

// Request Interceptor: Attach JWT Bearer Token to all outgoing requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('hadil_jwt_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Centralized 401 & 403 error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response ? error.response.status : null;

    if (status === 401) {
      // 401: Unauthorized - Token invalid, expired, or missing
      localStorage.removeItem('hadil_jwt_token');
      if (onUnauthorizedCallback) {
        onUnauthorizedCallback(error.response?.data?.detail || 'Authentication expired. Please log in again.');
      }
    } else if (status === 403) {
      // 403: Forbidden - Authenticated but lacks permission on active database
      const detailMsg = error.response?.data?.detail || 'Access Denied: You do not have permission to perform this action.';
      if (onForbiddenCallback) {
        onForbiddenCallback(detailMsg);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
