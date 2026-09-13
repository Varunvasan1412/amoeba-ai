import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";

export default function PrivacyPolicy() {
  return (
    <main className="min-h-screen bg-background text-foreground relative flex flex-col">
      <div className="bg-black"><Navbar /></div>
      <div className="flex-grow max-w-4xl mx-auto px-8 py-32">
        <h1 className="text-4xl font-bold mb-8">Privacy Policy</h1>
        <p className="text-gray-400 mb-4 leading-relaxed">
          At Amoeba AI, we take your privacy seriously. This privacy policy describes how we collect, use, and protect your personal information and enterprise data.
        </p>
        <h2 className="text-2xl font-semibold mt-8 mb-4">1. Information We Collect</h2>
        <p className="text-gray-400 mb-4 leading-relaxed">
          We collect information that you provide directly to us, such as when you create an account, connect your ERP system, or communicate with our support team.
        </p>
        <h2 className="text-2xl font-semibold mt-8 mb-4">2. How We Use Information</h2>
        <p className="text-gray-400 mb-4 leading-relaxed">
          We use the information we collect to provide, maintain, and improve our services, as well as to develop new features and ensure the security of your data.
        </p>
        <h2 className="text-2xl font-semibold mt-8 mb-4">3. Data Security</h2>
        <p className="text-gray-400 mb-4 leading-relaxed">
          We implement industry-standard security measures to protect your data from unauthorized access, alteration, or disclosure.
        </p>
      </div>
      <Footer />
    </main>
  );
}
