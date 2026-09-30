# Guidance for AI coding agents

Read `README.md` for what this project is and `docs/progress.md` for what is verified.

- Never commit photos, passwords or IP addresses of home networks. Photos live in `private/`, which is git-ignored.
- The N900 runs BusyBox `ash`, not bash. Anything run on the phone must be plain POSIX `sh`.
- The N900 needs `-o HostKeyAlgorithms=+ssh-rsa` for SSH. Use legacy options only for the phone.
- Its clock was wrong (2009) during the first fresh capture and appears corrected after a later capture was named `20260929_001.jpg`. Earlier photo dates remain unreliable; do not rewrite original metadata or use it as verified chronology.
- Gemma 4 26B is installed, but its inference and image analysis are unverified. Only the short Qwen3.5 4B text inference test has passed; matching remains unverified.
- Keep verified and unverified results separate in `docs/progress.md`.
- End every commit you contribute to with a `Co-Authored-By:` trailer naming your model (see `ATTRIBUTION.md`).
