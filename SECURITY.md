# Security policy

## Trust boundary

- FastAPI only accepts loopback Host values and binds to `127.0.0.1`.
- Extension pairing uses a short-lived, single-use token. The resulting session is bound to the exact Chromium extension Origin.
- Platform cookies remain in the signed-in browser tab and must never be included in an extension command or API payload.
- Resume artifacts can only be downloaded from loopback HTTP URLs, have a 10 MiB limit, and are verified against their recorded SHA-256 before attachment.
- JD text is untrusted prompt data. Model prompts explicitly forbid following instructions embedded in the JD.
- API keys are encrypted for the current Windows user with DPAPI.

## Automatic stop conditions

Captcha, security/risk pages, expired login, invalid artifact hashes, non-loopback artifact URLs, or explicit adapter stop events result in `risk_stopped`. Automatic retry is disabled until a manual reset.

## Reporting

Do not include real resumes, API keys, platform cookies, phone numbers, or recruiter messages in an issue. Create a minimal redacted reproduction and use a private security channel before public disclosure.

