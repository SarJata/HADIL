import axios from 'axios';

const getDynamicDefaultAddress = () => {
  if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  if (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin !== 'null') {
    const protocol = window.location.protocol;
    if (protocol === 'http:' || protocol === 'https:') {
      return window.location.origin;
    }
  }
  return 'http://localhost:8000';
};

const DEFAULT_SERVER_ADDRESS = getDynamicDefaultAddress();


export const validateAndNormalizeServerAddress = (rawUrl) => {
  if (!rawUrl) return { isValid: false, normalized: '', error: 'Please enter a valid HADIL server address beginning with http:// or https://.' };
  
  const cleaned = rawUrl.trim();
  if (!cleaned) return { isValid: false, normalized: '', error: 'Please enter a valid HADIL server address beginning with http:// or https://.' };

  try {
    const parsed = new URL(cleaned);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return { isValid: false, normalized: '', error: 'Address must begin with http:// or https://.' };
    }
    if (!parsed.hostname) {
      return { isValid: false, normalized: '', error: 'Please enter a valid HADIL server address with a hostname.' };
    }
    
    // Construct base origin and strip any ending /api or trailing slashes to prevent duplication
    let basePath = parsed.pathname.replace(/\/+$/, '');
    if (basePath.endsWith('/api')) {
      basePath = basePath.slice(0, -4);
    }
    let normalized = `${parsed.protocol}//${parsed.host}${basePath}`;
    normalized = normalized.replace(/\/+$/, '');
    return { isValid: true, normalized, error: null };
  } catch (e) {
    return { isValid: false, normalized: '', error: 'Please enter a valid HADIL server address beginning with http:// or https://.' };
  }
};

export const normalizeServerAddress = (rawUrl) => {
  const result = validateAndNormalizeServerAddress(rawUrl);
  return result.isValid ? result.normalized : DEFAULT_SERVER_ADDRESS;
};

export const getStoredServerAddress = () => {
  const saved = localStorage.getItem('hadil_server_address');
  if (saved) {
    const validation = validateAndNormalizeServerAddress(saved);
    if (validation.isValid) return validation.normalized;
  }
  return DEFAULT_SERVER_ADDRESS;
};

export const getApiBaseUrl = () => `${getStoredServerAddress()}/api`;

const api = axios.create({
  baseURL: getApiBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true'
  },
});

export const updateServerAddress = (newAddress) => {
  const validation = validateAndNormalizeServerAddress(newAddress);
  if (!validation.isValid) {
    throw new Error(validation.error);
  }
  localStorage.setItem('hadil_server_address', validation.normalized);
  const newBaseUrl = `${validation.normalized}/api`;
  api.defaults.baseURL = newBaseUrl;
  return validation.normalized;
};

export const testServerConnection = async (targetAddress) => {
  const validation = validateAndNormalizeServerAddress(targetAddress);
  if (!validation.isValid) {
    return { success: false, message: validation.error };
  }
  
  const headers = { 'ngrok-skip-browser-warning': 'true' };

  // Attempt endpoints in priority order: /api/health -> /health -> /api/setup/status
  const candidateEndpoints = [
    `${validation.normalized}/api/health`,
    `${validation.normalized}/health`,
    `${validation.normalized}/api/setup/status`
  ];

  let lastErrorDetail = null;

  for (const testUrl of candidateEndpoints) {
    try {
      const res = await axios.get(testUrl, { timeout: 7000, headers });
      if (res.status === 200) {
        return { success: true, message: 'HADIL service is reachable.' };
      }
    } catch (err) {
      if (err.response) {
        // Server responded with an HTTP error status (e.g. 404, 500)
        lastErrorDetail = `Service responded with HTTP ${err.response.status}: ${err.response.data?.detail || err.response.statusText}`;
      } else if (err.request) {
        // Request made but no response received
        lastErrorDetail = `Network error: Could not connect to HADIL. Verify connection address and network connectivity.`;
      } else {
        lastErrorDetail = err.message;
      }
    }
  }

  return { 
    success: false, 
    message: lastErrorDetail || 'Could not reach HADIL. Check connection settings and try again.' 
  };
};

let onUnauthorizedCallback = null;
let onForbiddenCallback = null;

export const setAuthCallbacks = ({ onUnauthorized, onForbidden }) => {
  onUnauthorizedCallback = onUnauthorized;
  onForbiddenCallback = onForbidden;
};

// Request Interceptor: Ensure dynamic baseURL synchronization & attach JWT Bearer Token
api.interceptors.request.use(
  (config) => {
    config.baseURL = getApiBaseUrl();
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
      // Do NOT trigger session wipe/callback for login endpoint errors
      const isLoginRequest = error.config?.url?.endsWith('/auth/login');
      if (!isLoginRequest) {
        localStorage.removeItem('hadil_jwt_token');
        if (onUnauthorizedCallback) {
          onUnauthorizedCallback(error.response?.data?.detail || 'Authentication expired. Please log in again.');
        }
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

// Policy Documents RAG Subsystem APIs
export const fetchPolicies = async () => {
  const response = await api.get('/policies');
  return response.data;
};

export const uploadPolicy = async (formData) => {
  const response = await api.post('/policies/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const deletePolicy = async (docId) => {
  const response = await api.delete(`/policies/${docId}`);
  return response.data;
};

export const fetchPolicyConfig = async () => {
  const response = await api.get('/policies/config');
  return response.data;
};

export const updatePolicyConfig = async (threshold) => {
  const response = await api.post('/policies/config', { threshold });
  return response.data;
};

export default api;

export const DEFAULT_DESKTOP_CAPABILITIES = {
  deployment_mode: 'desktop',
  sqlite_local: true,
  sqlite_upload: true,
  sqlite_file_location: true,
  sqlite_directory_scan: true,
  remote_mysql: true,
  remote_postgresql: true,
  server_shutdown: true,
  windows_runtime: true,
  organization_signup: false,
};

export const fetchDeploymentCapabilities = async () => {
  const response = await api.get('/capabilities');
  return { ...DEFAULT_DESKTOP_CAPABILITIES, ...(response.data || {}) };
};

