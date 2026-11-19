# Verification results

- `python -m pytest -q` passed 34 tests, including the six legacy verdict cases, all nine Web decision combinations, true parallel B/C entry, independent first-round inputs, optional cross-examination, run history, evidence gaps, document parsing and limits, timeout, failure, cancellation, local access checks and SDK usage mapping with a test double.
- `python3 -m unittest discover -s tests -q` passed the original six CLI policy tests independently. `python3 -m py_compile abc_agents.py policy.py web/*.py` passed.
- `npm --prefix frontend run build` passed TypeScript and Vite production compilation.
- `ABC_CHROMIUM=/usr/bin/chromium npm --prefix frontend run test:e2e` passed the full workflow in Chromium against the production frontend and a local Mock backend. It covered Markdown upload, both independent rounds, cross-examination, the ten sections, JSON export, print CSS, Chinese switching and a 390px layout.
- `docker compose config --quiet` passed. The cloud container build uses the existing TLS trust bundle as a BuildKit secret because direct builds in this environment encountered the proxy CA. Certificate verification stays enabled.
- No live OpenAI provider call was made. This environment has no OpenAI API key.
