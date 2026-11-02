# Security policy

## Immediate credential action required

Earlier FofaMap 2.0 source archives may contain FOFA and model credentials in `config/settings.yaml`. Assume every committed value is compromised:

1. Revoke and rotate it in the relevant provider console.
2. Check FOFA/model usage and access logs for unexpected activity.
3. Prefer environment variables, Keyring, or container secrets. For local CLI compatibility, the init wizard also permits an explicitly confirmed, gitignored YAML file; never commit or share it. macOS/Linux use `0600`; Windows relies on the current user directory ACL and displays an explicit warning.
4. Coordinate a repository backup and contributor freeze before rewriting history.

Removing a secret from the latest commit is not sufficient because earlier commits, tags, releases, forks and local clones may retain it. For a coordinated history cleanup, back up the repository, freeze contributor pushes, use a reviewed `git filter-repo` procedure, notify collaborators before any force-push, and invalidate affected clones and forks where possible. Secret scanning does not make an exposed credential safe again.

## Runtime boundaries

- FOFA operations are read-only.
- TLS verification is enabled.
- Private, loopback, link-local, reserved and cloud-metadata HTTP targets are denied unless an administrator explicitly opts in.
- Nuclei is disabled by default. Every execution requires a one-time HMAC approval bound to its targets, template scope, severity scope and expiry. The unfiltered `all` template/severity scope is accepted only when explicitly selected and is displayed as `ALL` with a high-risk warning before execution.
- Remote MCP requires OAuth/JWT protected-resource configuration or a bearer verifier. Unauthenticated mode is loopback-only.
- Coding/Token plan credentials are `interactive_only`; the self-hosted Agent rejects them.

Report vulnerabilities privately to the maintainers rather than opening a public issue containing credentials or exploit details.
