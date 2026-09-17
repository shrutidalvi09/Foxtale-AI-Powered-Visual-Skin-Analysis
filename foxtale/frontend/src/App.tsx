import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Scan from "./pages/Scan";
import Results from "./pages/Results";
import History from "./pages/History";
import About from "./pages/About";
import { ScanProvider } from "./context/ScanContext";

export default function App() {
  return (
    <ScanProvider>
      <div className="flex min-h-screen flex-col bg-white">
        <Navbar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/scan" element={<Scan />} />
            <Route path="/results" element={<Results />} />
            <Route path="/history" element={<History />} />
            <Route path="/about" element={<About />} />
          </Routes>
        </main>
        <footer className="border-t border-navy-900/5 py-6 text-center text-xs text-navy-400">
          🦊 Foxtale — AI-Powered Visual Skin Analysis. Not a medical diagnosis.
        </footer>
      </div>
    </ScanProvider>
  );
}
