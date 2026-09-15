# M7 Security Checklist

Record the operator, date, environment, and evidence link for every item before pilot data is loaded.

- [ ] HTTPS terminates at a trusted reverse proxy; HTTP is redirected.
- [ ] `APP_ENV=production` and `AUTH_MODE=api_key` are active.
- [ ] Bootstrap key, API-key pepper, database password, and MinIO password are unique and secret.
- [ ] Named API keys expire, are delivered out of band, and are revoked when no longer needed.
- [ ] Viewer accounts cannot modify data; architect and admin roles match actual responsibilities.
- [ ] Two test organizations cannot read each other's projects, files, findings, feedback, or audit.
- [ ] Database, Redis, and MinIO ports are not public.
- [ ] Upload size, extension, media type, and file signatures are enforced.
- [ ] Evidence downloads use short-lived presigned URLs and are audit logged.
- [ ] Browser/API responses include no-store, frame-denial, MIME-sniffing, and referrer protections.
- [ ] Logs contain request IDs but no API keys, document content, or presigned URLs.
- [ ] Customer drawings and licensed standards are absent from Git and public issue attachments.
- [ ] PostgreSQL and MinIO backups are encrypted, access controlled, and restore-tested together.
- [ ] Dependency and container vulnerability review has no unaccepted critical finding.
- [ ] Incident owner, shutdown procedure, and credential rotation procedure are known.

M7 provides application controls, not a complete identity platform or perimeter. A production pilot
still requires host hardening, TLS, firewalling, secret management, encrypted backups, patching, and
an agreed retention/deletion policy.
