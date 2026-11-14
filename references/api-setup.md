# Freesound API setup (original files)

Preview MP3s from `sfx.py` are fine for auditioning. To download the uploader's
original WAV/FLAC/AIFF, use the APIv2 OAuth2 flow.

## 1. Create an API credential

1. Sign in at https://freesound.org/.
2. Open https://freesound.org/apiv2/apply.
3. Create an application. Use a redirect URI you control, for example
   `http://localhost:8765/callback`.
4. Copy the **Client ID** and **Client secret / API key**.

Write them to `~/.config/freesound/credential.json`:

```json
{
  "client_id": "your-client-id",
  "client_secret": "your-client-secret",
  "redirect_uri": "http://localhost:8765/callback"
}
```

Keep this file private (`chmod 600`) and never commit it.

## 2. Authorize once

```bash
python3 .claude/skills/sound/scripts/fs_api.py auth --no-browser
```

Open the printed URL in a browser where you are logged in, then click
**Authorize**. The script listens on the redirect URI, exchanges the code, and
writes `~/.config/freesound/token.json` (24 h lifetime, refresh token included).

## 3. Search and download originals

```bash
python3 .claude/skills/sound/scripts/fs_api.py status
python3 .claude/skills/sound/scripts/fs_api.py search "child crying" -n 10
python3 .claude/skills/sound/scripts/fs_api.py hq ./sfx 479836 717167
```

`hq` prints id, license, author, bytes and path, and sleeps 2 s between files.
API limits: 30 downloads per minute and 500 per day.

## Notes

- An API key alone is enough for search, but **original-file downloads require
  OAuth2**.
- New applications must use PKCE (`S256`); the script handles it.
- `token.json` is refreshed automatically when it expires.
- If the redirect URI uses another host or port, change it in both the Freesound
  application settings and `credential.json`.
