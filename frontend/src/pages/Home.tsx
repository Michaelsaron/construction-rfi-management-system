import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { token } from '../lib/api';
import { BrandMark, SiteScene } from '../components/Brand';
import Icon from '../components/Icon';
import { installApp, isStandalone } from '../lib/pwa';
import './home.css';

const FEATURES = [
  { icon: 'layers', t: 'RFI Summaries & Register', d: 'Group individual RFIs under a summary, lock on submission, and search the full register by number, chainage, side or work item.' },
  { icon: 'hardhat', t: 'Technical Review', d: 'Assign the right reviewers per work type. Each reviewer gets a personal inspection queue and records a recommendation with comments.' },
  { icon: 'shield', t: 'RE / ARE Decisions', d: 'Approve, reject, keep on progress or record for information, with revision history kept for every resubmission.' },
  { icon: 'progress', t: 'Daily Progress', d: 'Log daily site quantities and statuses against the project work list using dependent dropdowns that match how the site works.' },
  { icon: 'clip', t: 'Attachments & Evidence', d: 'Attach test results, drawings and site photos directly to each RFI so the evidence travels with the decision.' },
  { icon: 'chart', t: 'Reports & Excel Export', d: 'Export the RFI register and progress reports to Excel for monthly reports, claims and client meetings.' },
  { icon: 'bell', t: 'Notifications & Overdue Alerts', d: 'Everyone is notified when action is needed, and RFIs that pass the overdue target are flagged.' },
  { icon: 'wifiOff', t: 'Works Offline on Site', d: 'Install on Android or iOS. Entries made without signal are queued and synced automatically when you are back online.' },
  { icon: 'history', t: 'Full Audit Trail', d: 'Every submission, assignment and decision is logged with user and timestamp for complete accountability.' },
];

const STEPS = [
  { t: 'Create Summary', d: 'Contractor drafts the RFI Summary and adds individual RFIs.' },
  { t: 'Submit & Lock', d: 'Summary is submitted to the Resident Engineer and locked.' },
  { t: 'Activate & Assign', d: 'RE/ARE activates each RFI and assigns technical reviewers.' },
  { t: 'Inspect & Recommend', d: 'Reviewers inspect on site and submit their recommendations.' },
  { t: 'Decide & Record', d: 'RE/ARE issues the final decision, which is saved to the register.' },
];

const ROLES = [
  { icon: 'ruler', t: 'Contractor / Site Engineer', d: 'Raise RFI summaries, attach evidence, track decisions and log daily progress.' },
  { icon: 'hardhat', t: 'Technical Reviewer', d: 'Work through My Inspections, record test results and recommendations.' },
  { icon: 'shield', t: 'Resident Engineer / ARE', d: 'Activate RFIs, assign reviewers and issue final decisions.' },
  { icon: 'users', t: 'Administrator', d: 'Manage projects, users, reference data, reviewer rules and the audit log.' },
];

const TECH = [
  ['React · TypeScript · Vite', 'Fast, typed user interface'],
  ['Python FastAPI', 'REST APIs & approval workflows'],
  ['MySQL', 'RFIs, inspections, users & records'],
  ['Docker Compose', 'Consistent dev & deployment'],
  ['Progressive Web App', 'Installable on Android & iOS'],
  ['Nginx · HTTPS · Linux', 'Secure cloud deployment'],
];

export default function Home() {
  const authed = !!token();
  useEffect(() => { document.title = 'Construction RFI · Site Control System'; document.documentElement.setAttribute('data-theme', 'light'); }, []);
  const primary = authed
    ? <Link to="/" className="btn lg">Open Dashboard <Icon name="arrow" size={17} /></Link>
    : <Link to="/login" className="btn lg">Sign in to your project <Icon name="arrow" size={17} /></Link>;

  return (
    <div className="home">
      <header className="h-nav">
        <div className="h-wrap h-nav-in">
          <Link to="/home" className="brand"><BrandMark /><span><span className="bt">Construction RFI</span><span className="bs">Site Control System</span></span></Link>
          <nav className="h-links">
            <a href="#features">Features</a><a href="#workflow">Workflow</a><a href="#roles">Roles</a><a href="#technology">Technology</a>
          </nav>
          <div style={{ display: 'flex', gap: 10 }}>
            {!isStandalone() && <button className="btn ghost h-install" onClick={installApp}><Icon name="phone" size={16} />Install App</button>}
            {authed ? <Link to="/" className="btn">Dashboard</Link> : <Link to="/login" className="btn">Sign in</Link>}
          </div>
        </div>
      </header>

      <section className="h-hero">
        <div className="h-wrap h-hero-in">
          <div className="h-copy">
            <span className="eyebrow">Road &amp; bridge construction</span>
            <h1>Inspection control for <span className="hl">every chainage</span> on site.</h1>
            <p className="lead">Run Requests for Inspection from contractor submission through technical review to the Resident Engineer's decision, with a full audit trail.</p>
            <div className="h-cta">{primary}<a href="#workflow" className="btn ghost lg">See the workflow</a></div>
            <ul className="h-ticks">
              <li><Icon name="check" size={16} />Role-based access</li>
              <li><Icon name="check" size={16} />Works offline</li>
              <li><Icon name="check" size={16} />Excel exports</li>
            </ul>
          </div>
          <div className="h-visual">
            <SiteScene className="h-scene" />
            <div className="float f1"><span className="dot ok"><Icon name="check" size={14} stroke={3} /></span><div><div className="ft mono">RFI-0142 · Rev 1</div><div className="fs">Sub-base layer: Approved</div></div></div>
            <div className="float f2"><span className="dot wait"><Icon name="clock" size={14} stroke={2.6} /></span><div><div className="ft mono">KM 12+400 – 12+650 RHS</div><div className="fs">Awaiting RE decision</div></div></div>
            <div className="float f3"><span className="dot rev"><Icon name="hardhat" size={14} stroke={2.4} /></span><div><div className="ft">Material test</div><div className="fs">2 of 3 reviews complete</div></div></div>
          </div>
        </div>
      </section>
      <div className="hazard" />

      <section className="h-strip">
        <div className="h-wrap h-strip-in">
          {[['clipboard', 'Summaries → RFIs', 'Structured submissions'], ['hardhat', 'Multi-reviewer', 'Technical inspections'], ['file', 'Revisions', 'Full resubmission history'], ['phone', 'PWA', 'Android & iOS install']].map(([i, a, b]) => (
            <div key={a} className="h-stat"><span className="hs-ic"><Icon name={i} size={20} /></span><div><div className="hs-a">{a}</div><div className="hs-b">{b}</div></div></div>
          ))}
        </div>
      </section>

      <section id="features" className="h-sec">
        <div className="h-wrap">
          <div className="h-head"><span className="eyebrow">Features</span><h2>Built for the site office and the field</h2><p>Everything a road or bridge project needs to manage inspections, from the first summary to the final sign-off.</p></div>
          <div className="h-features">
            {FEATURES.map(f => (
              <article key={f.t} className="h-feature"><span className="hf-ic"><Icon name={f.icon} size={22} /></span><h3>{f.t}</h3><p>{f.d}</p></article>
            ))}
          </div>
        </div>
      </section>

      <section id="workflow" className="h-sec h-blueprint">
        <div className="h-wrap">
          <div className="h-head light"><span className="eyebrow">Workflow</span><h2>From request to sign-off in five steps</h2><p>Each step is controlled by role, so the right person acts at the right time.</p></div>
          <ol className="h-steps">
            {STEPS.map((s, i) => (
              <li key={s.t}><span className="hn">{String(i + 1).padStart(2, '0')}</span><h3>{s.t}</h3><p>{s.d}</p></li>
            ))}
          </ol>
        </div>
      </section>

      <section id="roles" className="h-sec">
        <div className="h-wrap">
          <div className="h-head"><span className="eyebrow">Roles</span><h2>One system, every stakeholder</h2><p>Each user sees exactly what their role needs.</p></div>
          <div className="h-roles">
            {ROLES.map(r => (
              <article key={r.t} className="h-role"><span className="hr-ic"><Icon name={r.icon} size={24} /></span><div><h3>{r.t}</h3><p>{r.d}</p></div></article>
            ))}
          </div>
        </div>
      </section>

      <section id="technology" className="h-sec h-tech">
        <div className="h-wrap">
          <div className="h-head"><span className="eyebrow">Technology</span><h2>Modern, secure and scalable</h2><p>A full-stack web application with authentication, role-based access control and audit logging.</p></div>
          <div className="h-techgrid">
            {TECH.map(([a, b]) => <div key={a} className="h-techcard"><div className="ta">{a}</div><div className="tb">{b}</div></div>)}
          </div>
        </div>
      </section>

      <section className="h-final">
        <div className="h-wrap h-final-in">
          <div><h2>Ready for today's inspections?</h2><p>Sign in with the account your project administrator created for you.</p></div>
          {primary}
        </div>
      </section>

      <footer className="h-foot">
        <div className="h-wrap h-foot-in">
          <span className="brand"><BrandMark size={30} /><span className="bt" style={{ fontSize: 16 }}>Construction RFI</span></span>
          <span>© {new Date().getFullYear()} Construction RFI Management System</span>
        </div>
      </footer>
    </div>
  );
}
