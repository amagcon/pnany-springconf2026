# PNA-NY Spring Conference 2026 App

This version is rebuilt using the structure of your previous Fall Conference Streamlit app.

## What matches the older app style
- single `app.py`
- `questions.json` driven post-test
- Google Sheets dynamic header appending
- local CSV backup
- certificate PDF generation
- secrets-based course and sheet settings

## Files
- `app.py`
- `questions.json`
- `requirements.txt`
- `.streamlit/secrets-template.toml`
- `assets/` folder for optional certificate background image
- reference docx files you uploaded

## Optional assets
- Add `logo.png` in the project root if you want a logo at the top
- Add `assets/cert_bg.png` if you want a certificate background image

## Deploy
1. Push these files to GitHub
2. Deploy in Streamlit Community Cloud
3. Add your secrets from the template
4. Share the target Google Sheet with the service account email as Editor
