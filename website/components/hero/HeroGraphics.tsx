"use client"; 
import { motion } from "framer-motion"; 
import { GlassCard } from "../ui/GlassCard"; 
import { Compass, Search, FileText, Zap, Send } from "lucide-react"; 
import Image from "next/image"; 
import { ReactNode } from "react"; 
 
const AMOEBA_PATH = "M 150,-180 C 250,-200 280,-50 250,50 C 220,150 150,220 50,220 C -50,220 -200,150 -220,50 C -240,-50 -200,-180 -100,-200 C 0,-220 50,-160 150,-180 Z"; 
 
const PathCard = ({ delay, children }: { delay: number; children: ReactNode }) => { 
  return ( 
    <div 
      className="absolute flex items-center justify-center pointer-events-none z-40 path-card" 
      style={{ 
        animationDelay: `${delay}s` 
      }} 
    > 
      <div className="pointer-events-auto origin-center"> 
        {children} 
      </div> 
    </div> 
  ); 
}; 
 
export function HeroGraphics() { 
  return ( 
    <> 
      <style dangerouslySetInnerHTML={{ 
        __html: ` 
        @keyframes orbit-path { 
          0% { offset-distance: 0%; } 
          100% { offset-distance: 100%; } 
        } 
        .path-card { 
          offset-path: path("${AMOEBA_PATH}"); 
          offset-rotate: 0deg; 
          animation: orbit-path 40s linear infinite; 
        } 
      `}} /> 
      <div className="relative w-full h-[300px] sm:h-[400px] lg:h-[600px] flex items-center justify-center"> 
        <div className="absolute inset-0 flex items-center justify-center scale-50 sm:scale-75 lg:scale-100 origin-center"> 
          {/* Master Container for Robot and Cards */} 
          <div className="relative w-[350px] h-[400px]"> 
            {/* Central Robot Image */} 
            <motion.div 
              animate={{ y: [0, -15, 0] }} 
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }} 
              className="absolute inset-0 z-20" 
            > 
              {/* Soft background glow to blend */} 
              <div className="absolute inset-0 w-full h-full flex items-center justify-center z-0"> 
                <div className="w-[65%] h-[65%] bg-[#00d2ff]/20 blur-[60px] rounded-full mix-blend-screen" /> 
              </div> 
 
              {/* Neon amoeba curve removed as requested */} 
 
              {/* Robot Image with a soft mask to fade out the square background edges */} 
              <div 
                className="relative w-full h-full z-10" 
                style={{ 
                  maskImage: "radial-gradient(ellipse at center, black 50%, transparent 68%)", 
                  WebkitMaskImage: "radial-gradient(ellipse at center, black 50%, transparent 68%)" 
                }} 
              > 
                <Image 
                  src="/robo.png" 
                  alt="Amoeba AI Robot" 
                  fill 
                  className="object-cover relative z-10 mix-blend-screen" 
                /> 
              </div> 
            </motion.div> 
 
            {/* Cards Container relative to the 350x400 robot box */} 
            <div className="absolute inset-0 pointer-events-none z-30"> 
 
              <div className="absolute left-[175px] top-[200px] w-0 h-0 hidden md:block"> 
                <PathCard delay={0}> 
                  <GlassCard className="w-[160px] rounded-[20px] p-2.5" delay={0.2}> 
                    <div className="flex items-center gap-3"> 
                      <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center text-[#00d2ff] bg-black/40 flex-shrink-0"> 
                        <Compass className="w-4 h-4" /> 
                      </div> 
                      <div className="overflow-hidden"> 
                        <h4 className="text-white text-[13px] font-medium leading-tight">Navigate</h4> 
                        <p className="text-gray-400 text-[10px] mt-0.5">Open pending orders</p> 
                      </div> 
                    </div> 
                  </GlassCard> 
                </PathCard> 
 
                <PathCard delay={-8}> 
                  <GlassCard className="w-[160px] rounded-[20px] p-2.5" delay={0.4}> 
                    <div className="flex items-center gap-3"> 
                      <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center text-[#00d2ff] bg-black/40 flex-shrink-0"> 
                        <Search className="w-4 h-4" /> 
                      </div> 
                      <div className="overflow-hidden"> 
                        <h4 className="text-white text-[13px] font-medium leading-tight">Search</h4> 
                        <p className="text-gray-400 text-[10px] mt-0.5">Find unpaid invoices</p> 
                      </div> 
                    </div> 
                  </GlassCard> 
                </PathCard> 
 
                <PathCard delay={-16}> 
                  <GlassCard className="w-[160px] rounded-[20px] p-2.5" delay={0.3}> 
                    <div className="flex items-center gap-3"> 
                      <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center text-[#00d2ff] bg-black/40 flex-shrink-0"> 
                        <Zap className="w-4 h-4" /> 
                      </div> 
                      <div className="overflow-hidden"> 
                        <h4 className="text-white text-[13px] font-medium leading-tight">Analyze</h4> 
                        <p className="text-gray-400 text-[10px] mt-0.5">Why did sales increase?</p> 
                      </div> 
                    </div> 
                  </GlassCard> 
                </PathCard> 
 
                <PathCard delay={-24}> 
                  <GlassCard className="w-[170px] rounded-[20px] p-2.5" delay={0.5}> 
                    <div className="flex items-center gap-3"> 
                      <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center text-gray-300 bg-black/40 flex-shrink-0"> 
                        <FileText className="w-4 h-4" /> 
                      </div> 
                      <div className="overflow-hidden"> 
                        <h4 className="text-white text-[13px] font-medium leading-tight">Report</h4> 
                        <p className="text-gray-400 text-[10px] mt-0.5">Generate monthly sales report</p> 
                      </div> 
                    </div> 
                  </GlassCard> 
                </PathCard> 
 
                <PathCard delay={-32}> 
                  <GlassCard className="w-[150px] rounded-[20px] p-2.5" delay={0.6}> 
                    <div className="flex items-center gap-3"> 
                      <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center text-gray-300 bg-black/40 flex-shrink-0"> 
                        <Send className="w-4 h-4" /> 
                      </div> 
                      <div className="overflow-hidden"> 
                        <h4 className="text-white text-[13px] font-medium leading-tight">Act</h4> 
                        <p className="text-gray-400 text-[10px] mt-0.5">Notify finance team</p> 
                      </div> 
                    </div> 
                  </GlassCard> 
                </PathCard> 
              </div> 
 
              {/* Large Bottom Interactive Card - Moved down per request to avoid overlap */} 
              <div className="absolute z-40 pointer-events-auto left-[50%] lg:left-[90%] xl:left-[100%] 2xl:left-[129%] top-[400px] md:top-[445px] -translate-x-1/2"> 
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }} 
                  animate={{ opacity: 1, scale: 1 }} 
                  transition={{ duration: 0.8, delay: 0.8, type: "spring", stiffness: 100 }} 
                  whileHover={{ y: -2, scale: 1.02 }} 
                  className="w-[310px] rounded-[20px] p-4 bg-white/10 shadow-[0_15px_50px_rgba(0,0,0,0.6)] border border-white/15 backdrop-blur-xl flex flex-col justify-center" 
                > 
                  <div className="flex flex-col gap-3"> 
                    <div className="flex items-center justify-between pb-3 border-b border-white/10"> 
                      <span className="text-white text-[13px] font-medium">Show me this month's sales performance</span> 
                      <Send className="w-3.5 h-3.5 text-[#00d2ff]" /> 
                    </div> 
                    <div className="flex items-end justify-between pt-1"> 
                      <div> 
                        <p className="text-white text-[15px] font-medium"> 
                          Sales increased by <span className="text-[#00d2ff] ml-1">18.4% ↗</span> 
                        </p> 
                        <p className="text-gray-400 text-[11px] mt-1">compared with last month.</p> 
                      </div> 
                      <div className="flex items-end gap-1.5 h-9"> 
                        <motion.div initial={{ height: 0 }} animate={{ height: "30%" }} transition={{ delay: 1 }} className="w-2 bg-[#00d2ff]/30 rounded-sm" /> 
                        <motion.div initial={{ height: 0 }} animate={{ height: "50%" }} transition={{ delay: 1.1 }} className="w-2 bg-[#00d2ff]/50 rounded-sm" /> 
                        <motion.div initial={{ height: 0 }} animate={{ height: "70%" }} transition={{ delay: 1.2 }} className="w-2 bg-[#00d2ff]/80 rounded-sm" /> 
                        <motion.div initial={{ height: 0 }} animate={{ height: "100%" }} transition={{ delay: 1.3 }} className="w-2 bg-[#00d2ff] rounded-sm shadow-[0_0_10px_#00d2ff]" /> 
                      </div> 
                    </div> 
                  </div> 
                </motion.div> 
              </div> 
            </div> 
          </div> 
        </div> 
      </div> 
    </> 
  ); 
} 
