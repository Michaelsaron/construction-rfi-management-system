// Browser workflow test for UI design v1 against an ISOLATED stack (never the live system).
//   node scripts/e2e/ui_e2e.mjs <frontend-url> <seed.json> <screenshot-dir> <results.json>
// Requires playwright-core and a local Google Chrome (channel "chrome"). Data comes from scripts/e2e/seed_e2e.py (synthetic).
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const [FE, SEED, SHOTS, OUT] = process.argv.slice(2);
const seed = JSON.parse(fs.readFileSync(SEED, 'utf8'));
fs.mkdirSync(SHOTS, { recursive: true });
const results = [];
const check = (name, ok, detail = '') => { results.push({ name, ok: !!ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`); };
const SIZES = { desktop: { width: 1440, height: 900 }, tablet: { width: 820, height: 1180 }, phone: { width: 390, height: 844 } };
const JPG = Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.alloc(4096)]);
const PDF = Buffer.from('%PDF-1.4\n% e2e\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n');

const browser = await chromium.launch({ channel: 'chrome', headless: true });

async function session(who, size = 'desktop', perms) {
  const ctx = await browser.newContext({ viewport: SIZES[size], acceptDownloads: true });
  if (perms) await ctx.grantPermissions(perms, { origin: FE });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', d => d.accept());
  const u = who === 'admin' ? { email: seed.admin.email, pw: seed.admin.password } : { email: seed.users[who].email, pw: seed.password };
  await page.goto(`${FE}/login`);
  await page.fill('#em', u.email); await page.fill('#pw', u.pw);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForSelector('.app-header', { timeout: 15000 });
  await page.waitForLoadState('networkidle');
  return { ctx, page, errors };
}
const shot = async (page, name) => { await page.waitForLoadState('networkidle'); await page.waitForTimeout(250); await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true }); };
const go = async (page, p) => { await page.goto(FE + p); await page.waitForLoadState('networkidle'); await page.waitForTimeout(200); };
const navLabels = page => page.$$eval('.sidebar a.nav', as => as.map(a => a.textContent.trim()));
const noHScroll = page => page.evaluate(() => document.scrollingElement.scrollWidth <= window.innerWidth + 1);
const R = seed.rfis;

try {
  // ------------------------------------------------------------------ Category 1 — admin
  {
    const { ctx, page, errors } = await session('admin');
    const nav = await navLabels(page);
    check('Admin navigation follows s.12', ['Dashboard', 'Projects', 'Users', 'Project Memberships', 'Roles', 'Audit Log', 'Configuration'].every(x => nav.includes(x)), nav.join(', '));
    const kpis = await page.$$eval('.kpi-card', ks => ks.map(k => k.textContent));
    check('Admin KPIs come from the database', kpis.some(k => k.includes('Active projects') && k.includes('01')) && kpis.some(k => k.includes('Inactive accounts') && k.includes('01')), kpis.join(' | '));
    check('Pending invitations are not fabricated', kpis.some(k => k.includes('Pending invitations') && k.includes('Not enabled')));
    check('Header shows category and role', (await page.textContent('.app-header')).includes('Category 1'));
    await shot(page, 'desktop_01_admin_dashboard');
    const dl = page.waitForEvent('download'); await page.getByRole('button', { name: 'Export access matrix' }).click();
    check('Access matrix export downloads', (await dl).suggestedFilename().endsWith('.xlsx'));
    await go(page, '/memberships'); check('Memberships page lists roles', (await page.textContent('main')).includes('Material Inspector')); await shot(page, 'desktop_02_admin_memberships');
    await go(page, '/roles'); check('Roles page loads', (await page.textContent('main')).includes('Category 2.2')); await shot(page, 'desktop_03_admin_roles');
    await go(page, '/configuration'); check('Configuration shows attachment policy', (await page.textContent('main')).includes('Maximum size per file')); await shot(page, 'desktop_04_admin_configuration');
    for (const [p, n] of [['/users', 'users'], ['/projects', 'projects'], ['/audit', 'audit'], ['/master-data', 'reference_data'], ['/reports', 'reports'], ['/daily-progress', 'daily_progress'], ['/notifications', 'notifications']]) {
      await go(page, p); check(`Admin ${p} renders`, (await page.textContent('main')).length > 40); await shot(page, `desktop_admin_${n}`);
    }
    check('Admin pages have no script errors', errors.length === 0, errors.join('; '));
    await ctx.close();
  }

  // ------------------------------------------------------------------ Category 2.1 — RE
  {
    const { ctx, page, errors } = await session('re');
    const nav = await navLabels(page);
    check('RE/DRE navigation follows s.12', ['Dashboard', 'DOC_01 Submissions', 'Inspector Assignment', 'Workflow Monitor', 'Final Decisions', 'DOC_02', 'Reports'].every(x => nav.includes(x)), nav.join(', '));
    const txt = await page.textContent('main');
    check('Management dashboard KPIs and batch table', txt.includes('New DOC_01 batches') && txt.includes('Awaiting final decision') && txt.includes('Daily Request for Inspection Summary Sheets') && txt.includes('Next action'));
    check('24-hour notice legend shown', txt.includes('24-hour notice warning'));
    await shot(page, 'desktop_05_re_dashboard');
    // DOC_01 review remark with evidence
    await page.getByRole('link', { name: /DOC01-.*-026/ }).first().click(); await page.waitForLoadState('networkidle');
    await page.fill('#mgmt-remark', 'Reviewed submitted list. Please ensure prior layer test results accompany the inspection.');
    await page.setInputFiles('.evidence input[type=file]:not([capture]):not([accept^=".jpg"])', { name: 'prior_layer_FDT.pdf', mimeType: 'application/pdf', buffer: PDF });
    await page.waitForSelector('text=prior_layer_FDT.pdf');
    await shot(page, 'desktop_06_re_doc01_review');
    await page.getByRole('button', { name: 'Record remark' }).click();
    await page.waitForSelector('text=Remark recorded.');
    check('DOC_01 review remark recorded with evidence', (await page.textContent('main')).includes('DOC_01 review'));
    // Assignment with remark + evidence
    await page.locator('main').getByRole('link', { name: 'Assign', exact: true }).first().click();
    await page.waitForURL(/\/assign$/); await page.waitForSelector('#add-insp option:nth-child(3)', { state: 'attached' });
    for (const label of ['Works Inspector', 'Material Inspector']) {
      const opt = await page.$$eval('#add-insp option', (os, l) => os.find(o => o.textContent.includes(l))?.value, label);
      await page.selectOption('#add-insp', opt);
    }
    await page.fill('#mn', 'Check tack coat application rate.');
    await page.setInputFiles('.evidence input[type=file][accept*="image"]:not([capture])', { name: 'site_photo.jpg', mimeType: 'image/jpeg', buffer: JPG });
    await page.waitForSelector('text=site_photo.jpg');
    await shot(page, 'desktop_07_re_assignment');
    await page.getByRole('button', { name: 'Save assignment' }).click();
    const dlgText = await page.textContent('[role=dialog]');
    check('Assignment confirmation lists sequence and evidence', dlgText.includes('Works Inspector') && dlgText.includes('1 file(s)'), dlgText.slice(0, 160));
    await page.getByRole('dialog').getByRole('button', { name: 'Save assignment' }).click();
    await page.waitForSelector('text=Assignment saved');
    check('Assignment saved', true);
    // Workflow timeline
    await go(page, `/rfis/${R.under_review}/workflow`);
    const tl = await page.textContent('.timeline');
    check('Timeline shows received, assignment, active and pending inspectors, locked decision', tl.includes('DOC_01 received') && tl.includes('Assignment saved') && tl.includes('Active') && tl.includes('Pending') && tl.includes('Locked until reviews complete'));
    await shot(page, 'desktop_08_re_workflow_timeline');
    await go(page, `/rfis/${R.completed}/workflow`);
    await page.getByRole('button', { name: /Works Inspector/ }).click();
    check('Completed stage shows evidence to RE', (await page.textContent('main')).includes('IMG_0910.jpg'));
    // Final disposition
    await go(page, `/rfis/${R.awaiting_decision}/decision`);
    await page.getByLabel('Approved: For further works for the executed section and RFI to be resubmitted for the remaining section').check();
    check('Partial approval requires the executed section', await page.getByRole('button', { name: 'Record disposition' }).isDisabled());
    await page.fill('#af', '156+300'); await page.fill('#at', '156+305');
    await page.fill('#fr', 'Proceed for executed section; resubmit remaining.');
    await page.setInputFiles('.evidence input[type=file]:not([capture]):not([accept^=".jpg"])', { name: 'remark_photo.pdf', mimeType: 'application/pdf', buffer: PDF });
    await page.waitForSelector('text=remark_photo.pdf');
    await shot(page, 'desktop_09_re_final_disposition');
    await page.getByRole('button', { name: 'Record disposition' }).click();
    const d2 = await page.textContent('[role=dialog]');
    check('Disposition confirmation shows disposition, remarks, evidence, decision-maker and sections',
      d2.includes('executed section') && d2.includes('Proceed for executed section') && d2.includes('1 file(s)') && d2.includes('R. Engineer') && d2.includes('156+300') && d2.includes('Remaining section'), d2.slice(0, 200));
    await page.keyboard.press('Escape');
    check('Escape closes the confirmation', (await page.$('[role=dialog]')) === null);
    await page.getByRole('button', { name: 'Record disposition' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Record disposition' }).click();
    await page.waitForURL(/\/completed\//); await page.waitForSelector('h1:has-text("Completed DOC_03")');
    check('Recording the disposition opens the completed DOC_03', (await page.textContent('main')).includes('Completed DOC_03'));
    check('RE pages have no script errors', errors.length === 0, errors.join('; '));
    await ctx.close();
  }

  // ------------------------------------------------------------------ Category 2.2 — inspectors
  {
    const { ctx, page, errors } = await session('wi', 'desktop', []);  // no camera permission granted
    const nav = await navLabels(page);
    check('Inspector navigation follows s.12', ['My Assigned RFIs', 'Active DOC_03', 'Review History', 'Attachments'].every(x => nav.includes(x)), nav.join(', '));
    await shot(page, 'desktop_10_inspector_assigned');
    await go(page, `/rfis/${R.under_review}/review`);
    check('Active turn badge', (await page.textContent('main')).includes('Your turn is active'));
    await page.fill('#rv-comment', 'Surface preparation checked. Levels and crossfall verified for the inspected section.');
    await page.getByRole('button', { name: 'Save draft' }).click();
    await page.waitForSelector('text=/Draft saved/');
    check('Draft comment saved', true);
    // camera fallback: clicking Camera opens a file chooser even without camera permission
    const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.getByRole('button', { name: /Camera/ }).click()]);
    await chooser.setFiles({ name: 'IMG_0910.jpg', mimeType: 'image/jpeg', buffer: JPG });
    await page.waitForSelector('.ev-item:has-text("IMG_0910.jpg") >> text=/Uploaded/');
    check('Camera without permission falls back to file selection; upload works', (await page.textContent('.evidence')).includes('Uploaded'));
    check('Camera fallback hint shown', (await page.textContent('.evidence')).includes('permission is denied'));
    // invalid file
    await page.setInputFiles('.evidence input[type=file]:not([capture]):not([accept^=".jpg"])', { name: 'tool.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('MZ') });
    await page.waitForSelector('text=/not allowed/');
    check('Unsupported file rejected with explanation; comment kept', (await page.inputValue('#rv-comment')).startsWith('Surface preparation'));
    await page.getByRole('button', { name: 'Dismiss' }).click();
    // interrupted upload then retry -> one file
    let blocked = true;
    await page.route('**/evidence/assignments/*/files', r => (blocked ? r.abort('connectionreset') : r.continue()));
    await page.setInputFiles('.evidence input[type=file]:not([capture]):not([accept^=".jpg"])', { name: 'Prior_Layer_FDT.pdf', mimeType: 'application/pdf', buffer: PDF });
    await page.waitForSelector('text=/Upload failed/');
    check('Network interruption shows failure and keeps the comment', (await page.inputValue('#rv-comment')).length > 10);
    check('Submit disabled? (no upload running after failure)', !(await page.getByRole('button', { name: 'Submit review' }).isDisabled()));
    blocked = false;
    await page.getByRole('button', { name: 'Retry' }).click();
    await page.waitForSelector('.ev-item:has-text("Prior_Layer_FDT.pdf") >> text=/Uploaded/');
    const count = await page.$$eval('.ev-item .nm', ns => ns.filter(n => n.textContent === 'Prior_Layer_FDT.pdf').length);
    check('Retry stores the file once', count === 1, `count=${count}`);
    await page.unroute('**/evidence/assignments/*/files');
    await shot(page, 'desktop_11_inspector_review');
    await page.getByRole('button', { name: 'Submit review' }).click();
    const dt = await page.textContent('[role=dialog]');
    check('Review confirmation shows RFI, role, sequence, comment, attachments, name, sign-off',
      dt.includes('EW-021') && dt.includes('Works Inspector') && dt.includes('1 of 3') && dt.includes('2 file(s)') && dt.includes('A. Inspector') && dt.includes('Sign-off'), dt.slice(0, 200));
    await page.getByRole('dialog').getByRole('button', { name: 'Submit review' }).click();
    await page.waitForSelector('text=/Review submitted and locked/'); await page.waitForSelector('text=Submitted · locked');
    check('Submitted review becomes read-only', (await page.$('#rv-comment')) === null && (await page.textContent('main')).includes('Submitted · locked'));
    await go(page, '/my-attachments'); check('Attachments menu lists own evidence as locked', (await page.textContent('main')).includes('Submitted · locked'));
    check('Inspector pages have no script errors', errors.length === 0, errors.join('; '));
    await ctx.close();
    // the next inspector is now active, and an out-of-turn inspector is read-only
    const s2 = await session('me', 'phone');
    await go(s2.page, `/rfis/${R.under_review}/review`);
    check('Pending inspector sees "Awaiting previous reviewer" and no upload controls', (await s2.page.textContent('main')).includes('Awaiting previous reviewer') && (await s2.page.$('.ev-pick')) === null);
    await shot(s2.page, 'phone_12_inspector_awaiting_turn');
    await s2.ctx.close();
    const s3 = await session('mi', 'phone');
    await go(s3.page, `/rfis/${R.under_review}/review`);
    check('Next inspector (mobile) has camera / gallery / files controls', (await s3.page.textContent('main')).includes('Your turn is active') && (await s3.page.$$('.ev-pick')).length === 3);
    const sticky = await s3.page.$eval('.sticky-actions', e => getComputedStyle(e).position);
    check('Mobile Save draft / Submit review bar is sticky', sticky === 'fixed', sticky);
    check('Mobile review page has no horizontal scroll', await noHScroll(s3.page));
    await shot(s3.page, 'phone_13_inspector_review');
    await s3.page.click('.menu-btn'); await s3.page.waitForTimeout(300); await s3.page.screenshot({ path: path.join(SHOTS, 'phone_14_navigation_open.png') });
    await s3.ctx.close();
  }

  // ------------------------------------------------------------------ Category 2.3 — office
  {
    const { ctx, page, errors } = await session('qs');
    const nav = await navLabels(page);
    check('Office navigation follows s.12', ['DOC_02 Register', 'Completed DOC_03', 'Search', 'Reports', 'Exports'].every(x => nav.includes(x)), nav.join(', '));
    check('Office lands on DOC_02 register', page.url().endsWith('/rfis'));
    await page.getByLabel(/Show source, destination and fill-layer/).check();
    await page.getByLabel(/Show Work_Status/).check();
    const heads = await page.$$eval('thead th', t => t.map(x => x.textContent));
    check('Advanced toggle shows hidden workbook fields I:M and S', heads.some(h => h.startsWith('Fill layer')) && heads.some(h => h.startsWith('Work status')), heads.join(','));
    check('Legacy drive paths are not shown', !(await page.textContent('main')).match(/[a-z]:\\\\/i));
    await page.evaluate(() => { window.prompt = () => 'Asphalt checks'; });
    await page.fill('#r-q', 'asphalt'); await page.getByRole('button', { name: 'Apply filters' }).click(); await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: 'Save view' }).click(); await page.waitForTimeout(500);
    check('Saved view created', (await page.$$eval('select[aria-label="Saved views"] option', o => o.map(x => x.textContent))).includes('Asphalt checks'));
    const dx = page.waitForEvent('download'); await page.getByRole('button', { name: /Export Excel/ }).click(); check('Register Excel export', (await dx).suggestedFilename().endsWith('.xlsx'));
    const dp = page.waitForEvent('download'); await page.getByRole('button', { name: /Export PDF/ }).click(); check('Register PDF export (visible columns)', (await dp).suggestedFilename().endsWith('.pdf'));
    await shot(page, 'desktop_15_office_register');
    await go(page, `/completed/${R.completed}`);
    const c = await page.textContent('main');
    check('Completed DOC_03 shows sections, disposition and attachment index', c.includes('DOC_03 record sections') && c.includes('Approved: For further works') && c.includes('Attachment index') && c.includes('site_note.pdf'));
    const db = page.waitForEvent('download'); await page.getByRole('button', { name: 'Download evidence bundle' }).click();
    const bundle = await db; check('Evidence bundle downloads', bundle.suggestedFilename().endsWith('.zip'));
    const dpdf = page.waitForEvent('download'); await page.getByRole('button', { name: 'Open completed DOC_03 PDF' }).click(); check('Issued DOC_03 PDF downloads', (await dpdf).suggestedFilename().endsWith('.pdf'));
    check('Office record is read-only (no edit controls)', (await page.$('textarea')) === null);
    await shot(page, 'desktop_16_office_completed_doc03');
    await go(page, '/search'); await page.fill('#sq', 'EW-021'); await page.keyboard.press('Enter'); await page.waitForSelector('main table a:has-text("EW-021")', { timeout: 15000 });
    check('Search finds RFI', (await page.textContent('main')).includes('EW-021'));
    check('Office pages have no script errors', errors.length === 0, errors.join('; '));
    await ctx.close();
    const t = await session('qs', 'tablet'); await go(t.page, `/completed/${R.completed}`); await shot(t.page, 'tablet_17_completed_doc03'); await go(t.page, '/rfis'); await shot(t.page, 'tablet_18_register'); await t.ctx.close();
    const ph = await session('qs', 'phone'); check('Phone register uses record cards', await ph.page.$eval('.rec-cards', e => getComputedStyle(e).display !== 'none')); check('Phone register has no horizontal scroll', await noHScroll(ph.page)); await shot(ph.page, 'phone_19_register_cards'); await ph.ctx.close();
  }

  // ------------------------------------------------------------------ Category 3 — contractor
  {
    const { ctx, page, errors } = await session('enc');
    const nav = await navLabels(page);
    check('Contractor navigation follows s.12', ['New DOC_01', 'Draft Submissions', 'Submitted Batches', 'My RFI Records'].every(x => nav.includes(x)), nav.join(', '));
    await go(page, '/doc01/new'); check('New DOC_01 shows project and contract', (await page.textContent('main')).includes('Contract II')); await shot(page, 'desktop_20_contractor_new_doc01');
    await go(page, `/summaries/${seed.draft_summary}`);
    await shot(page, 'desktop_21_contractor_doc01_rows');
    await page.getByRole('button', { name: 'Submit DOC_01' }).click();
    const d = await page.textContent('[role=dialog]');
    check('DOC_01 confirmation shows project, batch, row count and inspection times', d.includes('Sample Road Upgrading Project') && d.includes('-027') && d.includes('RFI rows') && d.includes('CC-513'), d.slice(0, 200));
    await page.getByRole('dialog').getByRole('button', { name: 'Submit DOC_01' }).click();
    await page.waitForSelector('text=/DOC_01 submitted/');
    check('DOC_01 submitted and locked', (await page.$('text=+ Add RFI row')) === null);
    await go(page, `/evidence/files/1/download`).catch(() => {});
    await go(page, `/rfis/${R.completed}`);
    check('Contractor RFI view has no inspector-evidence download panel', !(await page.textContent('main')).includes('IMG_0910.jpg'));
    check('Contractor pages have no script errors', errors.length === 0, errors.join('; '));
    await ctx.close();
    const ph = await session('enc', 'phone'); await go(ph.page, `/summaries/${seed.draft_summary}`); check('Phone DOC_01 has no horizontal scroll', await noHScroll(ph.page)); await shot(ph.page, 'phone_22_contractor_doc01'); await ph.ctx.close();
  }

  // ------------------------------------------------------------------ keyboard / accessibility basics
  {
    const { ctx, page } = await session('re');
    await page.keyboard.press('Tab');
    check('First Tab reaches the skip link', (await page.evaluate(() => document.activeElement?.textContent)) === 'Skip to content');
    await page.keyboard.press('Enter');
    check('Skip link moves to main content', (await page.evaluate(() => location.hash)) === '#main');
    await go(page, '/rfis');
    const th = page.locator('th.sortable').first(); await th.focus(); await page.keyboard.press('Enter'); await page.waitForLoadState('networkidle');
    check('Register columns sort by keyboard', (await th.getAttribute('aria-sort')) !== null);
    const unlabeled = await page.$$eval('input:not([type=hidden]):not(.sr-only), select, textarea', els => els.filter(e => !(e.labels && e.labels.length) && !e.getAttribute('aria-label')).map(e => e.outerHTML.slice(0, 60)));
    check('Register form controls are labelled', unlabeled.length === 0, unlabeled.join(' | '));
    await page.emulateMedia({ colorScheme: 'dark' });
    await go(page, '/'); await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark')); await shot(page, 'desktop_23_dark_theme');
    await ctx.close();
  }
} catch (e) {
  check('Unexpected error', false, String(e?.stack || e).slice(0, 800));
} finally {
  await browser.close();
  fs.writeFileSync(OUT, JSON.stringify({ when: new Date().toISOString(), passed: results.filter(r => r.ok).length, failed: results.filter(r => !r.ok).length, results }, null, 2));
  console.log(`\n${results.filter(r => r.ok).length} passed, ${results.filter(r => !r.ok).length} failed`);
}
