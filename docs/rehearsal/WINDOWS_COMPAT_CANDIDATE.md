# Native Windows compatibility candidate

This is a project-local patch to upstream System Atlas 0.5.0, based on project
commit `edf9d83f755c4bf00a2dd9fc75ccca2ef8ef5896`. It is not an upstream release.
The original installation manifest is intentionally preserved: `authority.mjs`
and `package.json` differ from their upstream hashes, and one regression test
file is added. The original preflight still rejects native
Windows; that historical gate must not be presented as a test of this candidate.

The rehearsal leader explicitly authorized a Windows compatibility experiment.
An individually authorized Windows participant may run this isolated candidate's
tests and team CLI directly. Keep original working copies and failed state for
inspection; never put private identities inside any worktree.

`atomicWrite` retains a same-directory temporary file, file-content `fsync`, and
rename/replacement. On native Windows it does not try to open and flush the parent
directory, which is the known failing operation. Other platforms still flush it.
No catch-all exception handler is added: file write/flush and replacement errors
still fail. Signatures, grants, field versions, checksummed history and recovery
are unchanged.

**Durability limit:** Windows does not receive the POSIX parent-directory-flush
guarantee. This candidate does not claim that the latest renamed directory entry
survives sudden power loss. Process recovery tests are not power-loss tests.

Targeted commands from the project root:

```sh
npm ci --ignore-scripts --prefix .agents/skills/system-atlas
npm run test:windows-compat --prefix .agents/skills/system-atlas
python scripts/rehearsal_smoke.py
```

Record actual OS, Node version, exact candidate SHA, test counts and failures.
Then use the existing run invitation and independently held member identity with
`team init-member` / `team serve`, without suppressing errors. HTTP access,
browser inspection, a signed initial snapshot and a subsequent leader update
must each be checked. A macOS pass does not establish native Windows support.

## Candidate validation before Windows handoff

On macOS with Node.js 22.22.3, `test:windows-compat` passed 30/30 tests
(no skips), and `python3 scripts/rehearsal_smoke.py` passed the local CLI/bare
Git rehearsal. An initial test invocation from the project root failed three
CLI path lookups because upstream tests expect the Skill working directory;
the npm script above supplies the correct directory. This was a test invocation
error, retained in local evidence, not a Windows result. Native Windows tests,
real member serve, HTTP/browser access and subsequent leader-update readback
remain pending.
