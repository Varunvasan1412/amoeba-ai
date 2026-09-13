  "use client";
import { motion } from "framer-motion";
import { ReactNode } from "react";

export function GlassCard({ children, className = "", delay = 0, style }: { children: ReactNode, className?: string, delay?: number, style?: React.CSSProperties }) {
  return (
    <motion.div
      style={style}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.8, delay, type: "spring", stiffness: 100 }}
      whileHover={{ y: -2, scale: 1.02 }}
      className={`bg-white/10 backdrop-blur-xl border border-white/20 shadow-[0_8px_32px_rgba(0,0,0,0.2)] relative flex flex-col justify-center ${className}`}
    >
      {children}
    </motion.div>
  );
}
