# Visitor analytics — setup (3 steps, ~10 minutes)

FORTUNA SIGNAL uses **Cloudflare Web Analytics**: free forever, privacy-friendly,
no cookie banner needed, and it doesn't slow the site down.

Until you complete these steps, the site renders **no analytics script at all**
(the beacon slot in the page template stays empty — verified in every build).

## Step 1 — Create your free Cloudflare account and add the site

1. Go to **https://dash.cloudflare.com/sign-up** and create a free account.
2. In the dashboard, open **Analytics & Logs → Web Analytics** and click **Add site**.
3. Enter the site hostname: `whitewizard888.github.io`
4. Cloudflare will show you a beacon snippet that looks like this:

```html
<script defer src='https://static.cloudflareinsights.com/beacon.min.js'
  data-cf-beacon='{"token": "PASTE_YOUR_TOKEN_HERE"}'></script>
```

## Step 2 — Copy your beacon token

From that snippet, copy **only the token value** — the long string between
`"token": "` and the closing `"` (in the example above, `PASTE_YOUR_TOKEN_HERE`).

## Step 3 — Paste it into the site config and redeploy

1. Open `build.py` in the site source and find this line (near the top):
   ```python
   CLOUDFLARE_BEACON_TOKEN = "YOUR_CLOUDFLARE_BEACON_TOKEN"
   ```
2. Replace `YOUR_CLOUDFLARE_BEACON_TOKEN` with your token (keep the quotes).
3. Rebuild and redeploy — or just send the token to LUNA and she'll do it in one pass.

That's it. Visits start appearing in your Cloudflare dashboard within a few minutes.
The token is a *measurement* token only: it can't change the site, and rotating it
is a one-line change any time.
