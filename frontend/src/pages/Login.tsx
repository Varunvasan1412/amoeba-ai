import React, { useState, useEffect } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const Login: React.FC = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [companyCode, setCompanyCode] = useState("");
  const [isPlatformOwner, setIsPlatformOwner] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (user) {
      const origin = (location.state as any)?.from?.pathname || "/admin";
      navigate(origin, { replace: true });
    }
  }, [user, navigate, location]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch('/api/login/access-token', {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username,
          password,
          company_code: isPlatformOwner ? null : (companyCode || null)
        }),
      });

      const data = await response.json().catch(() => null);

      if (response.ok && data) {
        login(data.access_token);
        const origin = (location.state as any)?.from?.pathname || "/admin";
        navigate(origin, { replace: true });
      } else {
        const errorMsg = data?.message || data?.detail || `Error ${response.status}: ${response.statusText}`;
        setError(errorMsg);
      }
    } catch (err: any) {
      setError(err?.message || "Connection failed. Is the backend running?");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full max-w-md p-8 bg-white rounded-lg shadow-md relative">
        {/* Toggle Button */}
        <button
          type="button"
          onClick={() => setIsPlatformOwner(!isPlatformOwner)}
          className="absolute top-4 right-4 text-xs font-semibold px-3 py-1.5 rounded-full transition-colors border"
          style={{
            backgroundColor: isPlatformOwner ? "#EFF6FF" : "transparent",
            color: isPlatformOwner ? "#2563EB" : "#6B7280",
            borderColor: isPlatformOwner ? "#BFDBFE" : "#E5E7EB",
          }}
        >
          {isPlatformOwner ? "Platform Login Active" : "Sign as Platform Owner"}
        </button>

        <div className="flex flex-col items-center mb-6 mt-4">
            <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mb-4 shadow-lg shadow-blue-100">
                <span className="text-white text-3xl font-black">A</span>
            </div>
            <h2 className="text-3xl font-black text-gray-900">Amoeba AI</h2>
            <p className="text-gray-500 mt-1">Enterprise Intelligence Platform</p>
        </div>

        {error && (
          <div className="p-3 mb-4 text-sm text-red-700 bg-red-100 rounded-lg flex items-center gap-2" role="alert">
            <div className="w-1.5 h-1.5 bg-red-600 rounded-full animate-pulse" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block mb-1.5 text-sm font-semibold text-gray-700 uppercase tracking-wider">Email or Username</label>
            <input
              type="text"
              value={username}
              placeholder="e.g. you@amoeba.ai"
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all bg-gray-50"
              required
            />
          </div>

          {!isPlatformOwner && (
            <div>
              <label className="block mb-1.5 text-sm font-semibold text-gray-700 uppercase tracking-wider">Company Code</label>
              <input
                type="text"
                value={companyCode}
                placeholder="Enter company code"
                onChange={(e) => setCompanyCode(e.target.value)}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all bg-gray-50"
                required={!isPlatformOwner}
              />
            </div>
          )}

          <div className="relative">
            <label className="block mb-1.5 text-sm font-semibold text-gray-700 uppercase tracking-wider">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                placeholder="••••••••"
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all bg-gray-50 pr-12"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-blue-600 transition-colors"
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className={`w-full py-4 text-white bg-blue-600 rounded-xl font-bold hover:bg-blue-700 transition duration-300 shadow-lg shadow-blue-100 flex items-center justify-center gap-2 ${
              isLoading ? "opacity-50 cursor-not-allowed" : ""
            }`}
          >
            {isLoading ? (
                <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Authenticating...
                </>
            ) : (
                "Log In"
            )}
          </button>
        </form>

      </div>
    </div>
  );
};

export default Login;
