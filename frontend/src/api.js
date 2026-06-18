import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Wrap MangaDex / MangaSpark image URLs through our backend proxy so the browser
// doesn't get blocked by referer/rate-limit on direct CDN requests.
export function proxyImg(url) {
  if (!url) return "https://placehold.co";
  if (url.startsWith("//")) return `https:${url}`;
  return `${process.env.REACT_APP_BACKEND_URL}/api/proxy/image?url=${encodeURIComponent(url)}`;
}

const api = axios.create({ baseURL: API });

// Convert backend-relative paths (e.g. /api/uploads/<id>) to absolute URLs for <img src>
export function assetUrl(path) {
  if (!path) return path;
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:")) return path;
  if (path.startsWith("/api/")) return `${process.env.REACT_APP_BACKEND_URL}${path}`;
  return path;
}

// Upload a file (avatar / background) to the backend, returns full URL
export async function uploadImage(file) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post("/uploads/image", fd, { headers: { "Content-Type": "multipart/form-data" } });
  return { url: assetUrl(data.url), id: data.id };
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function fmtError(detail) {
  if (detail == null) return "حدث خطأ ما";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
