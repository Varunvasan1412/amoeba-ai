export const apiFetch = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem("token");
  
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
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
