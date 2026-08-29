import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import HomePage from "./pages/HomePage";
import CreateJobDescriptionPage from "./pages/CreateJobDescriptionPage";
import JobDetailPage from "./pages/JobDetailPage";
import CandidateDetailPage from "./pages/CandidateDetailPage";
import NotFoundPage from "./pages/NotFoundPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/jobs/new" element={<CreateJobDescriptionPage />} />
          <Route path="/jobs/:jdId" element={<JobDetailPage />} />
          <Route path="/candidates/:candidateId" element={<CandidateDetailPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
