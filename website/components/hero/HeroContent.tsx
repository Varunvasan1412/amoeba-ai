"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, X } from "lucide-react";

export function HeroContent() {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.2, delayChildren: 0.3 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.6, type: "spring" as const } }
  };

  return (
    <>
    <motion.div 
      className="flex flex-col justify-center items-center lg:items-start text-center lg:text-left max-w-2xl z-10 mx-auto lg:mx-0"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      <motion.div variants={itemVariants} className="mb-4 inline-block">
        <span className="text-[10px] font-bold tracking-[0.2em] text-[#00d2ff] uppercase bg-[#00d2ff]/10 px-3 py-1 rounded-full border border-[#00d2ff]/20">
          The Next Evolution of ERP
        </span>
      </motion.div>

      <motion.h1 variants={itemVariants} className="text-7xl md:text-[90px] lg:text-[120px] font-bold text-white leading-[0.85] mb-6 tracking-wide md:tracking-wider">
        Meet <br />
        <span className="text-[#f26522]">Amoeba.</span>
      </motion.h1>

      <motion.h2 variants={itemVariants} className="text-2xl md:text-3xl font-semibold text-gray-200 mb-6 leading-snug">
        AI that understands <br /> your business.
      </motion.h2>

      <motion.p variants={itemVariants} className="text-gray-400 text-lg mb-10 leading-relaxed max-w-md">
        Amoeba AI connects with your ERP, understands your data and helps your team navigate, analyze, report and act — using natural language.
      </motion.p>

      <motion.div variants={itemVariants} className="flex items-center justify-center lg:justify-start gap-6">
        <button className="px-8 py-4 rounded-full bg-gradient-to-r from-[#00c4e0] via-[#00b0d8] to-[#f05a1a] text-white font-semibold hover:scale-105 transition-transform flex items-center gap-2 shadow-[0_0_25px_rgba(0,196,224,0.5)]">
          Explore Amoeba
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </button>

        <button 
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-3 text-white hover:text-[#00d2ff] transition-colors group"
        >
          <div className="w-12 h-12 rounded-full border border-white/30 flex items-center justify-center group-hover:border-[#00d2ff] group-hover:bg-[#00d2ff]/10 transition-all">
            <Play className="w-5 h-5 ml-1" />
          </div>
          <span className="font-medium">See It in Action</span>
        </button>
      </motion.div>
      </motion.div>

      <AnimatePresence>
        {isModalOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
            onClick={() => setIsModalOpen(false)}
          >
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative w-full max-w-5xl aspect-video bg-black rounded-2xl overflow-hidden shadow-2xl border border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <button 
                onClick={() => setIsModalOpen(false)}
                className="absolute top-4 right-4 z-10 w-10 h-10 rounded-full bg-black/50 hover:bg-black/80 text-white flex items-center justify-center transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
              <video 
                src="/Create_a_professional_cinemat.mp4" 
                controls 
                autoPlay 
                className="w-full h-full object-cover"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
