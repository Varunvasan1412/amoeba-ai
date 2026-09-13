"use client";

import Image from "next/image";

export function QuestionToActionSection() {
  return (
    <section
      className="relative w-full py-24 bg-[#03060f] overflow-hidden -mt-[55px] z-10"
      style={{ clipPath: "url(#q2a-clip)" }}
    >
      {/* SVG clip path */}
      <svg className="absolute w-0 h-0">
        <defs>
          <clipPath id="q2a-clip" clipPathUnits="objectBoundingBox">
            <path d="M0,0 L1,0 L1,0.90 C0.65,1.0 0.35,0.85 0,0.95 Z" />
          </clipPath>
        </defs>
      </svg>

      {/* Background ambient glow (Removed per user request) */}

      <div className="max-w-[1400px] mx-auto px-8 flex flex-col xl:flex-row items-center gap-12 relative z-10">

        {/* LEFT SIDE - KEEP EXISTING CONTENT */}
        <div className="xl:w-1/3 flex-shrink-0">
          <span className="text-[10px] font-bold tracking-[0.2em] text-[#00d2ff] uppercase mb-4 block">
            From Question to Action
          </span>

          <h2 className="text-4xl md:text-5xl font-bold text-white leading-tight mb-6">
            Ask. Understand. <br />
            <span className="text-[#f26522]">Act.</span>
          </h2>

          <p className="text-gray-400 text-lg leading-relaxed max-w-sm mb-2">
            A simple prompt is all it takes.
            <br />
            Amoeba handles the rest.
          </p>

          <span className="text-[#00d2ff] font-semibold text-lg block">
            Instantly.
          </span>
        </div>

        {/* RIGHT SIDE - IMAGE ONLY */}
        <div className="xl:w-2/3 w-full relative flex items-center justify-center">
          <div className="relative w-full max-w-[900px] overflow-hidden">
            <Image
              src="/Third section.png"
              alt="From Question to Action"
              width={1600}
              height={700}
              priority
              className="w-full h-auto object-contain"
            />
          </div>
        </div>

      </div>
    </section>
  );
}