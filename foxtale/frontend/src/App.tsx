import { useEffect } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import Layout from "./components/Layout";
import { AppProvider, useApp } from "./context/AppContext";
import About from "./pages/About";
import Analysis from "./pages/Analysis";
import Compare from "./pages/Compare";
import Dashboard from "./pages/Dashboard";
import Diary from "./pages/Diary";
import History from "./pages/History";
import Ingredients from "./pages/Ingredients";
import { HowItWorks, NotFound, PrivacyPolicy, Terms } from "./pages/Legal";
import Privacy from "./pages/Privacy";
import Routine from "./pages/Routine";
import Scan from "./pages/Scan";
import Settings from "./pages/Settings";
import Shop from "./pages/Shop";
import Welcome from "./pages/Welcome";

/** First visit: send people to the welcome + questionnaire flow once. */
function OnboardingGate() {
  const { profile, backendOnline } = useApp();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    if (backendOnline && profile && !profile.onboarded && pathname !== "/welcome") navigate("/welcome", { replace: true });
  }, [profile, backendOnline, pathname, navigate]);
  return null;
}

export default function App() {
  return (
    <AppProvider>
      <OnboardingGate />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/welcome" element={<Welcome />} />
          <Route path="/scan" element={<Scan />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/analysis/:id" element={<Analysis />} />
          <Route path="/results" element={<Analysis />} />
          <Route path="/routine" element={<Routine />} />
          <Route path="/diary" element={<Diary />} />
          <Route path="/shop" element={<Shop />} />
          <Route path="/ingredients" element={<Ingredients />} />
          <Route path="/history" element={<History />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/how-it-works" element={<HowItWorks />} />
          <Route path="/privacy-policy" element={<PrivacyPolicy />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </AppProvider>
  );
}
