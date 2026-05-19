# PyPI Trusted Publishing Setup

This repo is configured to publish `bcode-audit` to PyPI through GitHub Actions
using Trusted Publishing.

## What is already done

- GitHub Actions workflow added at `.github/workflows/release.yml`
- release flow builds, tests, checks distributions, and publishes with
  `pypa/gh-action-pypi-publish@release/v1`
- publishing job uses GitHub OIDC with `id-token: write`
- publishing environment is `pypi`

## One-time PyPI setup

You still need to configure PyPI to trust this exact GitHub workflow.

If the PyPI project does not exist yet:

1. Sign in to PyPI.
2. Go to your account's publishing settings.
3. Create a pending Trusted Publisher for:
   - PyPI project name: `bcode-audit`
   - Owner: `Bharath-970`
   - Repository: `bcode`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

If the PyPI project already exists:

1. Open the `bcode-audit` project on PyPI.
2. Click `Manage`.
3. Open `Publishing`.
4. Add a Trusted Publisher with:
   - Owner: `Bharath-970`
   - Repository: `bcode`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

## Release flow

After PyPI is configured:

```bash
git tag v0.1.0
git push origin v0.1.0
```

That tag triggers the workflow, which will:

1. run tests
2. build the sdist and wheel
3. verify the distributions with `twine check`
4. publish to PyPI

## Notes

- No long-lived PyPI API token is required with this setup.
- The workflow only publishes on tag pushes matching `v*` or manual dispatch.
- If you change the workflow filename or environment name, PyPI must be updated
  to match exactly.
