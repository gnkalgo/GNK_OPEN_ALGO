# GNK ALGO security boundary

This checkout is a development platform with paper execution. Live orders are unavailable. Report suspected defects privately through the repository owner's verified contact channel; no dedicated security mailbox is configured here. Never post credentials, account identifiers, customer records or production logs in a public issue.

Server authority covers session validity, CSRF/origin checks, roles, ownership, paper balance and account risk policy. Client controls and demo route guards are not security boundaries. New routes must derive account ownership from `current_user`, reject extra input fields and use Decimal for financial comparisons. Policy updates and order mutations acquire the same account lock before reading policy/turnover or changing funds.

Production must use HTTPS, secure HttpOnly cookies, unique secrets, restricted database/Redis networks and broker secrets kept out of VITE variables, logs and screenshots. Dhan token encryption requires a managed Fernet key; back up and test key rotation before retaining real credentials. Linking an account does not validate live execution rights.

Commercial release requires MFA/step-up, tenant and support-access review, credential lifecycle review, threat modeling, dependency/native-image scanning, audit export, monitoring and restore tests. Current audit records are database events, not a tamper-proof archive. The account halt blocks new paper orders; it does not cancel or close positions. See docs/PLATFORM-DESIGN.md and docs/RELEASE-APPROVAL.json for unresolved release work.
