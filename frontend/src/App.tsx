import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { token } from './lib/api';
import Layout from './components/Layout';
import Login from './pages/Login';
import Home from './pages/Home';
import ResetPassword from './pages/ResetPassword';
import ChangePassword from './pages/ChangePassword';
import Dashboard from './pages/Dashboard';
import Summaries from './pages/Summaries';
import SummaryDetail from './pages/SummaryDetail';
import Rfis from './pages/Rfis';
import RfiDetail from './pages/RfiDetail';
import InspectorReview from './pages/InspectorReview';
import FinalDisposition from './pages/FinalDisposition';
import AssignInspectors from './pages/AssignInspectors';
import WorkflowTimeline from './pages/WorkflowTimeline';
import CompletedDoc03 from './pages/CompletedDoc03';
import { AssignmentQueue, WorkflowQueue, DecisionQueue, MyAssigned, ActiveReviews, ReviewHistory, MyAttachments, CompletedList, SearchPage, ExportsPage, MyRfis } from './pages/Queues';
import { Memberships, Roles, Configuration } from './pages/Admin';
import DailyProgress from './pages/DailyProgress';
import Reports from './pages/Reports';
import MasterData from './pages/MasterData';
import ReviewerRules from './pages/ReviewerRules';
import Projects from './pages/Projects';
import Users from './pages/Users';
import Notifications from './pages/Notifications';
import Audit from './pages/Audit';

export default function App() {
  return <BrowserRouter><Routes>
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/home" element={<Home />} />
    {token() ? <Route element={<Layout />}>
      <Route path="/" element={<Dashboard />} />
      {/* DOC_01 */}
      <Route path="/summaries" element={<Summaries />} />
      <Route path="/summaries/:id" element={<SummaryDetail />} />
      <Route path="/doc01/new" element={<Summaries mode="new" />} />
      <Route path="/doc01/drafts" element={<Summaries mode="drafts" />} />
      <Route path="/doc01/submitted" element={<Summaries mode="submitted" />} />
      <Route path="/my-rfis" element={<MyRfis />} />
      {/* DOC_02 / RFI record and focused workflow screens */}
      <Route path="/rfis" element={<Rfis />} />
      <Route path="/rfis/:id" element={<RfiDetail />} />
      <Route path="/rfis/:id/assign" element={<AssignInspectors />} />
      <Route path="/rfis/:id/review" element={<InspectorReview />} />
      <Route path="/rfis/:id/workflow" element={<WorkflowTimeline />} />
      <Route path="/rfis/:id/decision" element={<FinalDisposition />} />
      <Route path="/completed" element={<CompletedList />} />
      <Route path="/completed/:id" element={<CompletedDoc03 />} />
      {/* Category 2.1 */}
      <Route path="/assignment" element={<AssignmentQueue />} />
      <Route path="/workflow" element={<WorkflowQueue />} />
      <Route path="/decisions" element={<DecisionQueue />} />
      {/* Category 2.2 */}
      <Route path="/my-inspections" element={<MyAssigned />} />
      <Route path="/active-review" element={<ActiveReviews />} />
      <Route path="/review-history" element={<ReviewHistory />} />
      <Route path="/my-attachments" element={<MyAttachments />} />
      {/* Category 2.3 */}
      <Route path="/search" element={<SearchPage />} />
      <Route path="/exports" element={<ExportsPage />} />
      <Route path="/reports" element={<Reports />} />
      {/* Category 1 */}
      <Route path="/projects" element={<Projects />} />
      <Route path="/users" element={<Users />} />
      <Route path="/memberships" element={<Memberships />} />
      <Route path="/roles" element={<Roles />} />
      <Route path="/configuration" element={<Configuration />} />
      <Route path="/audit" element={<Audit />} />
      {/* shared */}
      <Route path="/daily-progress" element={<DailyProgress />} />
      <Route path="/master-data" element={<MasterData />} />
      <Route path="/reviewer-rules" element={<ReviewerRules />} />
      <Route path="/notifications" element={<Notifications />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/login" element={<Navigate to="/" />} />
      <Route path="*" element={<Navigate to="/" />} />
    </Route> : <>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Home />} />
      <Route path="*" element={<Navigate to="/login" />} />
    </>}
  </Routes></BrowserRouter>;
}
