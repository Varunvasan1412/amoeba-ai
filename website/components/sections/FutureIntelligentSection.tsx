"use client";
import { motion } from "framer-motion";
import Image from "next/image";
import { Caveat } from "next/font/google";
import { Shield, FileText, Settings, BarChart2, LayoutDashboard, PenTool, CheckCircle2 } from "lucide-react";

// Load Google Font for the cursive text
const caveat = Caveat({ subsets: ['latin'], weight: '700' });

export function FutureIntelligentSection() {
  return (
    <section className="relative w-full pt-6 pb-6 md:pt-10 md:pb-8 bg-gradient-to-b from-[#fdfbff] to-[#f4f8ff] overflow-hidden">

      {/* Background Pastel Glows & Tech Grid */}
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: 'radial-gradient(circle at 1.5px 1.5px, #1e293b 1px, transparent 0)',
          backgroundSize: '36px 36px',
        }}
      />
      {/* Background Shades Removed Per User Request */}
      <div className="max-w-[1400px] mx-auto px-8 grid grid-cols-1 lg:grid-cols-2 gap-8 md:gap-12 items-center relative z-10 mb-8">

        {/* Left Side: Header */}
        <div className="flex flex-col items-center text-center lg:items-start lg:text-left">
          <span className="text-[10px] font-bold tracking-[0.2em] text-[#00d2ff] uppercase mb-3 block">
            The Future is Intelligent
          </span>
          <h2 className="text-4xl md:text-5xl font-bold text-[#1e293b] leading-tight mb-5">
            One AI layer. <br />
            <span className="text-[#00d2ff]">Limitless</span> <span className="text-[#f26522]">possibilities.</span>
          </h2>
          <p className="text-gray-600 text-[16px] leading-relaxed max-w-sm mb-6 mx-auto lg:mx-0">
            Amoeba is more than navigation and reports. It's the beginning of truly intelligent business operations.
          </p>

          <div className="space-y-3.5 max-w-[380px] w-full text-left flex flex-col items-center lg:items-start">
            <FeatureRow icon={<CheckCircle2 className="w-5 h-5 text-[#00d2ff]" />} text="Smarter workflows & automated actions" />
            <FeatureRow icon={<CheckCircle2 className="w-5 h-5 text-[#8b5cf6]" />} text="AI-driven instant business decisions" />
            <FeatureRow icon={<CheckCircle2 className="w-5 h-5 text-[#f26522]" />} text="Endless scalability for your ERP" />
          </div>
        </div>

        {/* Right Side Wrapper */}
        <div className="w-full flex flex-col items-center justify-center">
          {/* Right Side: Robot & Badges */}
          <div className="relative w-full h-[250px] sm:h-[350px] md:h-[450px] flex items-center justify-center">
            <div className="absolute w-[600px] lg:w-full h-full flex items-center justify-center scale-[0.6] sm:scale-75 md:scale-90 lg:scale-100 origin-center">

              {/* Central Robot with Wavy Blob Background */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[320px] h-[320px] z-20 flex items-center justify-center">

                {/* Colorful Blob Behind Robot */}
                <div className="absolute inset-0 m-auto w-[300px] h-[300px] rounded-[40%_60%_60%_40%/40%_40%_60%_60%] bg-gradient-to-tr from-[#00d2ff] via-[#8b5cf6] to-[#ffb75e] shadow-[0_0_40px_rgba(139,92,246,0.25)] animate-[spin_20s_linear_infinite]" />
                <div className="absolute inset-0 m-auto w-[290px] h-[290px] rounded-[50%_50%_40%_60%/60%_40%_60%_40%] bg-gradient-to-bl from-white/40 to-transparent backdrop-blur-sm animate-[spin_15s_linear_infinite_reverse]" />

                {/* Robot Image */}
                <div className="relative w-[240px] h-[240px] rounded-full overflow-hidden mix-blend-multiply z-10">
                  <Image src="/robo.png" alt="Amoeba Robot" fill className="object-cover" priority />
                </div>
              </div>

              {/* Floating Glass Badges */}
              <div className="hidden md:block">
                <Badge
                  title="AI Navigation"
                  icon={<Shield className="w-4 h-4 text-white" />}
                  color="bg-gradient-to-tr from-[#00d2ff] to-blue-400"
                  className="top-[8%] left-[5%] md:left-[0%] lg:left-[-2%]"
                  delay={0}
                />
                <Badge
                  title="AI Reports"
                  icon={<FileText className="w-4 h-4 text-white" />}
                  color="bg-gradient-to-tr from-[#8b5cf6] to-purple-400"
                  className="top-[45%] left-[-2%] md:left-[-5%] lg:left-[-12%]"
                  delay={1}
                />
                <Badge
                  title="AI Automation"
                  icon={<Settings className="w-4 h-4 text-white" />}
                  color="bg-gradient-to-tr from-[#10b981] to-emerald-400"
                  className="bottom-[8%] left-[10%] md:left-[5%] lg:left-[2%]"
                  delay={2}
                />
                <Badge
                  title="AI Analytics"
                  icon={<BarChart2 className="w-4 h-4 text-white" />}
                  color="bg-gradient-to-tr from-[#f59e0b] to-amber-400"
                  className="top-[5%] right-[5%] md:right-[0%] lg:right-[0%]"
                  delay={0.5}
                />
                <Badge
                  title="AI Dashboards"
                  icon={<LayoutDashboard className="w-4 h-4 text-white" />}
                  color="bg-gradient-to-tr from-[#f26522] to-orange-400"
                  className="top-[40%] right-[0%] md:right-[-5%] lg:right-[-2%]"
                  delay={1.5}
                />
                <Badge
                  title="AI Content"
                  icon={<PenTool className="w-4 h-4 text-white" />}
                  color="bg-gradient-to-tr from-[#ec4899] to-pink-400"
                  className="bottom-[15%] right-[5%] md:right-[0%] lg:right-[-2%]"
                  delay={2.5}
                />
              </div>
            </div>
          </div>

          {/* Cursive text moved below right side */}
          <div className="relative z-10 mt-4 md:mt-8 text-center">
            <h3 className={`${caveat.className} text-4xl md:text-5xl text-transparent bg-clip-text bg-gradient-to-r from-[#00d2ff] via-[#8b5cf6] to-[#f26522] drop-shadow-sm`}>
              Amoeba learns. Amoeba adapts. <br />
              Amoeba empowers.
            </h3>
          </div>
        </div>
      </div>
    </section>
  );
}

function FeatureRow({ icon, text }: { icon: React.ReactNode, text: string }) {
  return (
    <motion.div
      whileHover={{ x: 5 }}
      className="flex items-center gap-3.5 bg-white/70 backdrop-blur-md p-3.5 px-4 rounded-2xl border border-white/80 shadow-[0_4px_20px_rgba(0,0,0,0.03)] hover:shadow-[0_4px_25px_rgba(0,210,255,0.12)] hover:border-[#00d2ff]/30 transition-all cursor-pointer"
    >
      <div className="flex-shrink-0 bg-white shadow-sm p-1.5 rounded-full border border-gray-100">
        {icon}
      </div>
      <span className="text-slate-700 text-[14px] font-semibold">{text}</span>
    </motion.div>
  );
}

function Badge({ title, icon, color, className, delay = 0 }: { title: string, icon: React.ReactNode, color: string, className?: string, delay?: number }) {
  return (
    <motion.div
      animate={{ y: [0, -12, 0] }}
      transition={{ duration: 4, repeat: Infinity, delay: delay, ease: "easeInOut" }}
      className={`absolute z-30 flex items-center gap-3 p-1.5 pr-4 rounded-full bg-white/90 backdrop-blur-md border border-white shadow-[0_8px_30px_rgba(0,0,0,0.06)] hover:scale-105 hover:shadow-[0_8px_30px_rgba(0,0,0,0.12)] transition-all cursor-pointer group ${className}`}
    >
      <div className={`w-9 h-9 rounded-full flex items-center justify-center shadow-inner ${color}`}>
        {icon}
      </div>
      <span className="text-gray-700 text-[13px] font-semibold group-hover:text-gray-900 transition-colors">{title}</span>
    </motion.div>
  );
}
