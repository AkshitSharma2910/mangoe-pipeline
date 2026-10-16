# Mangoe — Ahmedabad Opportunity Pipeline

Residential project data from GujRERA, mapped to Mangoe's sales funnel.

## View the dashboard

Open the live site: `https://<your-username>.github.io/<repo-name>/`

## Update the data

1. Run the scraper:
   ```
   python gujrera_scraper.py --district Ahmedabad --details
   ```

2. Replace `data.json` in this repo with the new `gujrera_opportunity_database.json`:
   ```
   copy gujrera_opportunity_database.json data.json
   ```

3. Push:
   ```
   git add data.json
   git commit -m "Update pipeline data"
   git push
   ```

The site updates within a minute.

## Files

- `index.html` — the dashboard (no server needed, runs entirely in the browser)
- `data.json` — the project data (replace this to update)
- `gujrera_scraper.py` — the scraper (optional, keep for re-scraping)
