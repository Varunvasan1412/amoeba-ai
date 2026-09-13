"use client";
import { motion } from "framer-motion";

export function Navbar() {
  return (
    <motion.nav 
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="flex items-center justify-between py-6 px-8 max-w-[1400px] mx-auto w-full absolute top-0 left-0 right-0 z-50"
    >
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 flex items-center justify-center relative">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/Amoeba.png" alt="Amoeba Logo" className="w-full h-full object-contain mix-blend-screen" />
        </div>
        <div className="leading-tight">
          <h1 className="text-[17px] font-bold text-white tracking-wide">
            Amoeba <span className="text-[#00d2ff]">AI</span>
          </h1>
          <p className="text-[7.5px] text-gray-400 font-bold tracking-[0.2em] uppercase mt-0.5">ERP Intelligence</p>
        </div>
      </div>

      <div className="flex items-center gap-4 sm:gap-6">
        <a href="https://app.amoeba.space" className="text-white/80 hover:text-[#00d2ff] font-medium text-sm transition-colors hidden sm:block">
          Login
        </a>
        <button className="px-4 py-2 sm:px-6 sm:py-2.5 rounded-full bg-gradient-to-r from-[#00c4e0] via-[#00b0d8] to-[#f05a1a] text-white font-semibold text-xs sm:text-sm hover:scale-105 transition-transform shadow-[0_0_15px_rgba(0,196,224,0.4)]">
           Get Early Access
        </button>
      </div>
    </motion.nav>
  );
}
