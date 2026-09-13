"use client";
import { HeroContent } from "./HeroContent";
import { HeroGraphics } from "./HeroGraphics";

export function HeroSection() {
  return (
    <div className="relative z-20">
      <section 
        className="relative w-full h-auto min-h-[900px] md:min-h-[1100px] lg:h-[820px] lg:min-h-0 flex flex-col items-center justify-start pt-[60px] pb-32 md:pb-48 lg:pb-0 z-10"
      >
        {/* The Clipped Dark Background */}
        <div 
          className="absolute inset-0 w-full h-full bg-[#070b14] bg-[length:100%_100%] bg-center bg-no-repeat"
          style={{ 
            clipPath: "url(#hero-wave)",
            backgroundImage: "url('/Background.png')"
          }}
        >
          {/* Subtle animated grid pattern overlay */}
          <div 
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage: 'linear-gradient(rgba(255, 255, 255, 0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.5) 1px, transparent 1px)',
              backgroundSize: '40px 40px',
            }}
          />

          {/* Glowing Nebulas (Removed per user request) */}
          
          {/* Vignette effect */}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,#070b14_100%)] opacity-70 pointer-events-none" />
        </div>

        {/* SVG ClipPath for the precise wave */}
        <svg className="absolute w-0 h-0">
          <defs>
            <clipPath id="hero-wave" clipPathUnits="objectBoundingBox">
              <path d="M0,0 L1,0 L1,0.90 C0.65,1.0 0.35,0.85 0,0.95 Z" />
            </clipPath>
          </defs>
        </svg>

        {/* Content Container */}
        <div className="max-w-[1400px] mx-auto w-full px-8 grid grid-cols-1 lg:grid-cols-12 gap-8 items-start relative z-10">
          <div className="lg:col-span-5 pt-8">
            <HeroContent />
          </div>
          <div className="lg:col-span-7 relative">
            <HeroGraphics />
          </div>
        </div>
      </section>
    </div>
  );
}
