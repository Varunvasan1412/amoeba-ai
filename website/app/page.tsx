import { Navbar } from "@/components/layout/Navbar";
import { HeroSection } from "@/components/hero/HeroSection";
import { AmoebaWaySection } from "@/components/sections/AmoebaWaySection";
import { QuestionToActionSection } from "@/components/sections/QuestionToActionSection";
import { FutureIntelligentSection } from "@/components/sections/FutureIntelligentSection";
import { Footer } from "@/components/layout/Footer";

export default function Home() {
  return (
    <main className="min-h-screen bg-background selection:bg-[#00d2ff]/30 text-foreground relative">
      <Navbar />
      <HeroSection />
      <AmoebaWaySection />
      <QuestionToActionSection />
      <FutureIntelligentSection />
      <Footer />
    </main>
  );
}
