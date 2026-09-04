# Release checklist

## Automated

- [ ] Python tests, Ruff, TypeScript tests, type checks, and production builds pass from a clean checkout.
- [ ] Alembic upgrades a new SQLite database to head.
- [ ] DOCX/PDF Chinese text can be read back and contains no unapproved claim.
- [ ] Extension ZIP contains only the manifest, built scripts, source maps if intended, and popup.
- [ ] Diagnostic and sample data contain no resume, cookie, token, phone, or API key.

## Windows acceptance

- [ ] Windows 10 + Chrome: install, launch tray, open dashboard, pair extension, backup database.
- [ ] Windows 11 + Edge: install, launch tray, open dashboard, pair extension, backup database.
- [ ] Uninstall leaves user data only when the user chooses to retain it.

## Limited real-site smoke (personal test account only)

- [ ] Boss: collect one listing, open detail, prepare one conservative resume, manually confirm one submission.
- [ ] Liepin: collect/detail and preflight; submit only if current platform terms and UI permit it.
- [ ] Zhilian: collect/detail and preflight; submit only if current platform terms and UI permit it.
- [ ] Captcha or risk page immediately stops the adapter; no bypass or retry loop occurs.
- [ ] Missing attachment control shows the exact local artifact and waits for the user.
- [ ] A process interruption during `submitting` invokes `observeResult` after restart and does not submit twice.

