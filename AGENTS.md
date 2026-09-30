# Guidance for AI coding agents

Read `README.md` for what this project is and `docs/progress.md` for what is verified.

- Never commit photos, passwords or IP addresses of home networks. Photos live in `private/`, which is git-ignored.
- The N900 runs BusyBox `ash`, not bash. Anything run on the phone must be plain POSIX `sh`.
- The N900 needs `-o HostKeyAlgorithms=+ssh-rsa` for SSH. Use legacy options only for the phone.
- Its clock is wrong (2009). Don't rely on photo dates from the N900.
- Keep verified and unverified results separate in `docs/progress.md`.
- End every commit you contribute to with a `Co-Authored-By:` trailer naming your model (see `ATTRIBUTION.md`).
