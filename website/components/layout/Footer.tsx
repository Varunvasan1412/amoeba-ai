import Link from "next/link";

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="w-full bg-black text-gray-400 py-6 px-8 relative z-50">
      <div className="max-w-[1400px] mx-auto flex flex-col md:flex-row items-center justify-between text-sm">
        
        {/* Left Side: Copyrights */}
        <div className="mb-4 md:mb-0">
          &copy; {currentYear}{" "}
          <a
            href="https://ahattrickz.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-white hover:text-[#00d2ff] transition-colors font-medium"
          >
            Ahattrickz
          </a>{" "}
          All Rights Reserved.
        </div>

        {/* Right Side: Links */}
        <div className="flex items-center gap-2">
          <a
            href="#"
            className="hover:text-white transition-colors"
          >
            Terms & Conditions
          </a>
          <span>|</span>
          <a
            href="#"
            className="hover:text-white transition-colors"
          >
            Privacy Policy
          </a>
        </div>

      </div>
    </footer>
  );
}
