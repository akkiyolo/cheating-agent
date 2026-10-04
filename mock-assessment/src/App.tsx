import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./store";
import Login from "./pages/Login";
import Instructions from "./pages/Instructions";
import AssessmentPage from "./pages/Assessment";
import Review from "./pages/Review";
import Submitted from "./pages/Submitted";
import ResultsPage from "./pages/Results";

function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.accessToken);
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/instructions"
        element={
          <RequireAuth>
            <Instructions />
          </RequireAuth>
        }
      />
      <Route
        path="/assessment"
        element={
          <RequireAuth>
            <AssessmentPage />
          </RequireAuth>
        }
      />
      <Route
        path="/review"
        element={
          <RequireAuth>
            <Review />
          </RequireAuth>
        }
      />
      <Route
        path="/submitted"
        element={
          <RequireAuth>
            <Submitted />
          </RequireAuth>
        }
      />
      <Route
        path="/results"
        element={
          <RequireAuth>
            <ResultsPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
