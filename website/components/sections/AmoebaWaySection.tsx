"use client";
import { motion } from "framer-motion";
import Image from "next/image";
import { Database, LayoutGrid, FileText, Settings, Navigation, Search, BarChart2, FileBarChart, Zap } from "lucide-react";
import { useEffect, useState } from "react";

export function AmoebaWaySection() {
  return (
    <section
      className="relative w-full pb-32 md:pb-16 pt-[100px] -mt-[160px] bg-[#f8fbff] z-10"
      style={{ clipPath: "url(#amoeba-way-clip)" }}
    >
      {/* SVG clip path — both top and bottom waves */}
      <svg className="absolute w-0 h-0">
        <defs>
          <clipPath id="amoeba-way-clip" clipPathUnits="objectBoundingBox">
            <path d="M0,0 L1,0 L1,0.90 C0.65,1.0 0.35,0.85 0,0.95 Z" />
          </clipPath>
        </defs>
      </svg>
      {/* Background glow (Removed per user request) */}
      
      <div className="max-w-[1400px] mx-auto px-8 grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-8 md:gap-12 items-center relative z-10">
        
        {/* Left Side: Text Content */}
        <div className="pt-0 flex flex-col items-center text-center lg:items-start lg:text-left">
          <span className="text-[10px] font-bold tracking-[0.2em] text-[#00d2ff] uppercase mb-4 block">
            The Amoeba Way
          </span>
          <h2 className="text-4xl md:text-5xl font-bold text-[#1e293b] leading-tight mb-6">
            Don't learn <br />
            another system. <br />
            <span className="text-[#00d2ff]">Let</span> the system <br />
            <span className="text-[#f26522]">understand you.</span>
          </h2>
          <p className="text-gray-600 text-lg leading-relaxed max-w-md">
            Amoeba sits between your team and your ERP, understands your intent and gets the work done. 
            No complexity. No switching. <span className="text-[#00d2ff] font-semibold">Just asking.</span>
          </p>
        </div>

        {/* Right Side: Connection Diagram */}
        <div className="relative w-full h-[250px] sm:h-[350px] lg:h-[500px] flex items-center justify-center">
          <div className="absolute w-[800px] lg:w-full h-full flex items-center justify-center scale-[0.4] sm:scale-75 lg:scale-100 origin-center">
          
          {/* Center Robot */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[220px] h-[260px] z-20">
            <motion.div 
              animate={{ y: [-8, 8, -8] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              className="w-full h-full relative"
            >
              <div className="absolute top-[-35px] left-1/2 -translate-x-1/2 text-center w-full">
                <h3 className="bg-gradient-to-r from-[#00d2ff] to-[#3b82f6] text-transparent bg-clip-text font-bold text-[22px]">Amoeba AI</h3>
              </div>
              <div className="absolute bottom-[-35px] left-1/2 -translate-x-1/2 text-center w-full">
                <p className="text-[12px] text-[#00d2ff] font-medium tracking-[0.1em]">Understands • Connects • Acts</p>
              </div>
              <div className="relative w-full h-full rounded-full bg-gradient-to-br from-[#e0ffff]/80 via-[#00d2ff]/30 to-transparent flex items-center justify-center shadow-[0_0_80px_rgba(0,210,255,0.3),inset_0_0_40px_rgba(255,255,255,0.9)] backdrop-blur-md border border-[#00d2ff]/30">
                <div className="relative w-[180px] h-[180px] rounded-full overflow-hidden mix-blend-multiply">
                  <Image src="/robo.png" alt="Amoeba Robot" fill className="object-cover scale-[1.3] pt-2" />
                </div>
              </div>
            </motion.div>
          </div>

          {/* Left Inputs */}
          <div className="absolute left-0 top-1/2 -translate-y-1/2 flex flex-col gap-5 z-10">
            <ConnectionCard icon={<Settings className="w-4 h-4 text-[#00d2ff] group-hover:text-white transition-colors" />} title="ERP Systems" />
            <ConnectionCard icon={<Database className="w-4 h-4 text-[#00d2ff] group-hover:text-white transition-colors" />} title="Databases" />
            <ConnectionCard icon={<LayoutGrid className="w-4 h-4 text-[#00d2ff] group-hover:text-white transition-colors" />} title="Business Apps" />
            <ConnectionCard icon={<FileText className="w-4 h-4 text-[#00d2ff] group-hover:text-white transition-colors" />} title="Files & Documents" />
          </div>

          {/* Right Outputs */}
          <div className="absolute right-0 top-1/2 -translate-y-1/2 flex flex-col gap-5 z-10">
            <ConnectionCard icon={<Navigation className="w-4 h-4 text-[#f26522] group-hover:text-white transition-colors" />} title="Navigation" hoverColor="#f26522" />
            <ConnectionCard icon={<Search className="w-4 h-4 text-[#f26522] group-hover:text-white transition-colors" />} title="Search" hoverColor="#f26522" />
            <ConnectionCard icon={<BarChart2 className="w-4 h-4 text-[#f26522] group-hover:text-white transition-colors" />} title="Analysis" hoverColor="#f26522" />
            <ConnectionCard icon={<FileBarChart className="w-4 h-4 text-[#f26522] group-hover:text-white transition-colors" />} title="Reports" hoverColor="#f26522" />
            <ConnectionCard icon={<Zap className="w-4 h-4 text-[#f26522] group-hover:text-white transition-colors" />} title="Automation" hoverColor="#f26522" />
          </div>

          {/* Advanced IK Network Animation */}
          <div className="hidden lg:block absolute inset-0 pointer-events-none z-[5]">
            <AdvancedNetworkAnimation />
          </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function AdvancedNetworkAnimation() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) return null;

  // Define paths with alternate variations for the "breathing" IK effect
  const leftPaths = [
    { base: "M160,110 C220,110 240,230 270,250", alt: "M160,110 C210,130 250,210 270,250" },
    { base: "M160,180 C220,180 240,240 270,250", alt: "M160,180 C210,190 250,230 270,250" },
    { base: "M160,250 C220,250 240,250 270,250", alt: "M160,250 C220,240 240,260 270,250" },
    { base: "M160,320 C220,320 240,260 270,250", alt: "M160,320 C210,310 250,270 270,250" }
  ];
  
  const rightPaths = [
    { base: "M410,250 C440,240 460,80 530,80", alt: "M410,250 C450,220 480,100 530,80" },
    { base: "M410,250 C440,240 460,140 530,140", alt: "M410,250 C450,230 480,150 530,140" },
    { base: "M410,250 C440,250 460,200 530,200", alt: "M410,250 C450,240 480,210 530,200" },
    { base: "M410,250 C440,250 460,260 530,260", alt: "M410,250 C450,260 480,250 530,260" },
    { base: "M410,250 C440,260 460,320 530,320", alt: "M410,250 C450,280 480,310 530,320" }
  ];

  return (
    <>
      <style>
        {`
          @keyframes data-flow {
            0% { offset-distance: 0%; opacity: 0; transform: scale(0.5); }
            10% { opacity: 1; transform: scale(1); }
            90% { opacity: 1; transform: scale(1); }
            100% { offset-distance: 100%; opacity: 0; transform: scale(0.5); }
          }
          .data-packet {
            animation: data-flow var(--duration) infinite linear;
            animation-delay: var(--delay);
          }
        `}
      </style>
      <svg className="w-full h-full">
        <defs>
          <linearGradient id="left-flow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#00d2ff" stopOpacity="0.1" />
            <stop offset="100%" stopColor="#00d2ff" stopOpacity="0.6" />
          </linearGradient>
          <linearGradient id="right-flow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#00d2ff" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#f26522" stopOpacity="0.1" />
          </linearGradient>
        </defs>

        {/* Convergence Dots */}
        <circle cx="270" cy="250" r="3.5" fill="#00d2ff" className="drop-shadow-[0_0_8px_rgba(0,210,255,1)]" />
        <circle cx="410" cy="250" r="3.5" fill="#00d2ff" className="drop-shadow-[0_0_8px_rgba(0,210,255,1)]" />

        {/* Render Left IK Tentacles and Data */}
        {leftPaths.map((path, i) => (
          <g key={`l-${i}`}>
            <motion.path
              fill="none"
              stroke="url(#left-flow)"
              strokeWidth="2"
              animate={{ d: [path.base, path.alt, path.base] }}
              transition={{ duration: 4 + i, repeat: Infinity, ease: "easeInOut" }}
            />
            {/* Glowing moving data packet */}
            <circle
              r="4"
              fill="#00d2ff"
              className="data-packet shadow-[0_0_10px_#00d2ff]"
              style={{
                offsetPath: `path('${path.base}')`,
                '--duration': `${2 + i * 0.2}s`,
                '--delay': `${i * 0.5}s`
              } as any}
            />
          </g>
        ))}

        {/* Render Right IK Tentacles and Data */}
        {rightPaths.map((path, i) => (
          <g key={`r-${i}`}>
            <motion.path
              fill="none"
              stroke="url(#right-flow)"
              strokeWidth="2"
              animate={{ d: [path.base, path.alt, path.base] }}
              transition={{ duration: 4.5 + i, repeat: Infinity, ease: "easeInOut" }}
            />
            {/* Glowing moving data packet */}
            <circle
              r="4"
              fill="#f26522"
              className="data-packet shadow-[0_0_10px_#f26522]"
              style={{
                offsetPath: `path('${path.base}')`,
                '--duration': `${2.5 + i * 0.2}s`,
                '--delay': `${i * 0.4}s`
              } as any}
            />
          </g>
        ))}
      </svg>
    </>
  );
}

function ConnectionCard({ icon, title, hoverColor = "#00d2ff" }: { icon: React.ReactNode, title: string, hoverColor?: string }) {
  return (
    <motion.div 
      whileHover={{ scale: 1.05, x: 5 }}
      className="group bg-white rounded-full py-2.5 px-3 pr-6 shadow-[0_8px_30px_rgba(0,0,0,0.06)] hover:shadow-[0_8px_30px_rgba(0,210,255,0.15)] flex items-center gap-3 w-[180px] cursor-pointer transition-all duration-300"
      style={{ '--hover-color': hoverColor } as any}
    >
      <div 
        className="w-8 h-8 rounded-full bg-[#f0f7ff] flex items-center justify-center flex-shrink-0 transition-colors duration-300"
        style={{ backgroundColor: 'var(--bg-color, #f0f7ff)' }}
        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = hoverColor}
        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#f0f7ff'}
      >
        {icon}
      </div>
      <span className="text-slate-700 group-hover:text-slate-900 text-[13px] font-medium transition-colors duration-300">{title}</span>
    </motion.div>
  );
}
