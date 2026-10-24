# Publish and showcase

## 1. Publish this project to GitHub

This folder is a standalone repository. Publish only this project folder, not the parent Documents directory or the older combined dashboard.

If using GitHub's website, create a repository named `retail-lens-ai`, then upload the project contents. Exclude `.venv`, `.env`, `.streamlit/secrets.toml`, `data/raw`, caches, and local databases. The `.gitignore` already excludes them for Git workflows.

If using Git locally and the GitHub CLI, authenticate to your own account and run:

```bash
git init -b main
git add .
git commit -m "Build Retail Lens AI dashboard"
gh repo create retail-lens-ai --public --source=. --remote=origin --push
```

Choose the visibility you want. A public repository allows recruiters to inspect the code. The CLI commands are instructions, not a claim that a repository has been created. Replace the clone placeholder in README after obtaining your actual repository URL.

## 2. Deploy the Python dashboard

Use a host that runs Streamlit/Python. A static HTML host cannot run this app.

For Streamlit Community Cloud, sign in, select the GitHub repository, choose branch `main`, and set the entrypoint to `app.py`. Use Python 3.12. The included `requirements.txt` installs dependencies; `data/processed/retail.parquet` avoids a startup download.

The app works in guided mode without secrets. For a public portfolio demo, visitors can provide their own key through the sidebar. Before adding an owner-funded API key to a public app, add authentication and request quotas. The current app has neither. For private use, configure `GROQ_API_KEY` for Groq, `GEMINI_API_KEY` for Gemini, or `OPENAI_API_KEY` and optionally `OPENAI_MODEL` for OpenAI through the host's secret settings; never commit secrets.

Verify the deployed date/country filters, product ranking, uploads, and guided questions, then test AI using your own key. Add the resulting URL to README and GitHub About.

## 3. Local preview

```bash
source .venv/bin/activate
streamlit run app.py --server.port 8503
```

This serves a local preview, not a public shareable link. Other people cannot use your localhost URL. To stop it, press Ctrl+C in the terminal running Streamlit.
