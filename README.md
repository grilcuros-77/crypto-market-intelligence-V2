# Crypto Market Intelligence (public dashboard)

A public, read-only dashboard. The GitHub repository remains private.

## Architecture
- Next.js dashboard hosted on Vercel
- GitHub Actions runs the daily Python pipeline
- Daily reports are stored as JSON in `web/public/reports/`
- Binance public market data only (no account access, trading, or withdrawals)
- OpenAI API generates a narrative from indicators calculated by Python

No Supabase, database, or login is required.

## Setup
1. Keep the GitHub repository private.
2. Replace the existing repository contents with this project's contents.
3. In Vercel, import the private GitHub repository and set the Root Directory to `web`.
4. Deploy with no environment variables required for the website.
5. In GitHub repository Settings → Secrets and variables → Actions, add:
   - `OPENAI_API_KEY`
   - Optional variable `OPENAI_MODEL` (default: `gpt-4.1-mini`)
6. Run the workflow once manually from Actions → Daily market report → Run workflow.

The workflow commits `latest.json` and dated report files back to the repository. Vercel will redeploy after each commit.

## Notes
- The website is public. Do not add personal holdings, wallet addresses, API keys, or private financial information to report files.
- The pipeline uses Binance public endpoints and does not need Binance credentials.
- GitHub scheduled workflows can start later than the scheduled time.
- The cron schedule is 06:15 UTC (07:15 Slovenia in winter, 08:15 in summer).
- OpenAI API usage is billed separately from a ChatGPT subscription.
