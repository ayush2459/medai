import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
});

// Attach the access token to every outgoing request, if present.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("medintel_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If a request comes back unauthorized, clear the stored session so the app
// falls back to the login screen instead of looping on stale tokens.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("medintel_access_token");
      localStorage.removeItem("medintel_refresh_token");
    }
    return Promise.reject(error);
  }
);
