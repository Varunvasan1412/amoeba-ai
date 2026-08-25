export const apiFetch = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem("token");
  
  // 1. Strip absolute hostnames
  let cleanUrl = url
    .replace(/^https?:\/\/(backend|localhost):8000\/?/, '/')
    .replace(/^\/api\/api/, '/api');

  // 3. Ensure /api prefix (if not absolute)
  if (!cleanUrl.startsWith('http') && !cleanUrl.startsWith('/api')) {
      cleanUrl = `/api${cleanUrl.startsWith('/') ? '' : '/'}${cleanUrl}`;
  }

  // 4. FORCE same-origin proxying (Fixes ERR_NAME_NOT_RESOLVED)
  const finalUrl = cleanUrl.startsWith('http') 
    ? cleanUrl 
    : `${window.location.origin}${cleanUrl.startsWith('/') ? '' : '/'}${cleanUrl}`;

  console.log("🚀 Fetching from:", finalUrl);

  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  
  if (options.body && typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(finalUrl, {
    ...options,
    headers,
  });


  if (response.status === 401) {
    // Optional: handle unauthorized
    // localStorage.removeItem("token");
    // window.location.href = "/login";
  }

  return response;
};
