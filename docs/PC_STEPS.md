# What you need to do on your Mac - short checklist

## A. Use this upgraded code with your current database
1. Stop the current app: `Ctrl+C` or `docker compose down`.
2. Keep your old project folder as a backup copy.
3. Copy the files from this upgraded `rfi_production_system` folder into your existing `rfi_production_system` folder.
4. Do **not** run `docker compose down -v`.
5. Rebuild: `docker compose build --no-cache backend frontend`.
6. Start: `docker compose up -d`.
7. Check backend: `docker compose logs backend --tail=100`.
8. Open `http://localhost:5173`.

## B. Load your client's real Excel information
Run exactly once after startup:
`docker compose exec backend python scripts/import_client_bundle.py`

Then refresh the browser. You should see the real project `DUBTI-LOT-II` and historical RFIs.

Client ARE local account:
- Email: `frew99@gmail.com`
- Temporary password: `ChangeMe_ARE_2026!`

Change the password immediately in production.

## C. Add the other real users
Go to **Users** and create one account per person. You still need their names, emails and roles. Do not invent shared accounts.

## D. Test the workflow
1. Login Admin.
2. Create/open a Summary.
3. Add an RFI.
4. Submit Summary.
5. Login as ARE and Activate RFI.
6. Assign an inspector.
7. Login inspector -> My Inspections -> review.
8. Login ARE -> final decision.
9. Download PDF and Excel.
10. Check Audit Log and Notifications.
11. Create Daily Progress and link it to one or more RFIs.

## E. Things only you/client can provide before public go-live
- Real names/emails for all users.
- VPS/server account.
- Public domain/subdomain or hostname.
- SMTP email credentials.
- TLS certificate/domain setup.
- Company logo and final approved paper-form artwork if pixel-perfect reproduction is required.
- Off-server backup destination.
- Client UAT/sign-off.
