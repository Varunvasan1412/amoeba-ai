import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";

export default function TermsAndConditions() {
  return (
    <main className="min-h-screen bg-background text-foreground relative flex flex-col">
      <div className="bg-black"><Navbar /></div>
      <div className="flex-grow max-w-4xl mx-auto px-8 py-32">
        <h1 className="text-4xl font-bold mb-8">Terms and Conditions</h1>
        <p className="text-gray-400 mb-4 leading-relaxed">
          Welcome to Amoeba AI. By accessing or using our services, you agree to be bound by these Terms and Conditions.
        </p>
        <h2 className="text-2xl font-semibold mt-8 mb-4">1. Use of Service</h2>
        <p className="text-gray-400 mb-4 leading-relaxed">
          Amoeba AI provides enterprise integration tools. You agree to use our services only for lawful purposes and in accordance with these Terms.
        </p>
        <h2 className="text-2xl font-semibold mt-8 mb-4">2. User Responsibilities</h2>
        <p className="text-gray-400 mb-4 leading-relaxed">
          You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.
        </p>
        <h2 className="text-2xl font-semibold mt-8 mb-4">3. Limitation of Liability</h2>
        <p className="text-gray-400 mb-4 leading-relaxed">
          Amoeba AI shall not be liable for any indirect, incidental, special, consequential, or punitive damages resulting from your use of or inability to use the service.
        </p>
      </div>
      <Footer />
    </main>
  );
}
