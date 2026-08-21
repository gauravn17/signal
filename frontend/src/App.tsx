import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import JobDescriptionsPage from "./pages/JobDescriptionsPage";
import JobDetailPage from "./pages/JobDetailPage";
import CandidateDetailPage from "./pages/CandidateDetailPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<JobDescriptionsPage />} />
          <Route path="/jobs/:jdId" element={<JobDetailPage />} />
          <Route path="/candidates/:candidateId" element={<CandidateDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
