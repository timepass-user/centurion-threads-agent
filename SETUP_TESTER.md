# Fix Error 4476002 — Wrong App ID

Meta gives you **two different App IDs** for the same app:

| ID | Where shown | Use for OAuth? |
|----|-------------|----------------|
| **Meta App ID** | Top of dashboard (`878423321331831`) | ❌ NO |
| **Threads App ID** | Threads API → Settings page | ✅ YES |

Using the Meta App ID in OAuth gives:
```json
{"error_message":"Authorization Failed: No app ID was sent with the request.","error_code":4476002}
```

## Find the correct IDs

1. Open **Centurion** app in Meta Developer Console
2. **Use cases** → **Access the Threads API** → **Customize** → **Settings**
3. Copy from that page:
   - **Threads App ID** → use as `client_id` in OAuth
   - **Threads App Secret** → use in token exchange (NOT the parent App Secret)

## OAuth URL template

Replace `THREADS_APP_ID` with the ID from step 3:

```
https://threads.net/oauth/authorize?client_id=THREADS_APP_ID&redirect_uri=https%3A%2F%2Flocalhost%2Fcallback&scope=threads_basic%2Cthreads_content_publish%2Cthreads_read_replies%2Cthreads_manage_replies%2Cthreads_manage_insights%2Cthreads_keyword_search&response_type=code
```

## Exchange code

```bash
python scripts/exchange_code.py THREADS_APP_ID THREADS_APP_SECRET "PASTE_CODE"
```


You're seeing this because the Threads account authorizing OAuth (`@influencer.bot`) has not accepted the app's tester invite.

**OAuth will not work until both steps below are done.**

---

## Step 1: Add tester in Meta (developer side)

1. Go to: https://developers.facebook.com/apps/1526251002514059/roles/roles/
2. Scroll to **Threads Testers** (NOT "Testers" under Facebook — specifically **Threads Testers**)
3. Click **Add Threads Testers**
4. Type exactly: `influencer.bot` (no `@`, no email)
5. Select from dropdown → **Add**
6. Status should show **Pending** (wait 1–2 minutes)

**Common mistakes:**
- Adding to Facebook "Testers" instead of "Threads Testers"
- Using email instead of Threads username
- Using `influencer.bot@threads.net` instead of `influencer.bot`

---

## Step 2: Accept invite on Threads (account side)

The invite does NOT appear in Facebook notifications. It only appears inside Threads.

### On phone (most reliable):
1. Open **Threads app**
2. Profile → **Settings** (gear icon)
3. **Account** → **Website permissions**
4. Tap **Invites** tab (next to Active / Expired)
5. Find **Centurion** → tap **Accept**

### On web:
1. Go to: https://www.threads.net/settings/website_permissions
2. Log in as **@influencer.bot** (must be this account, not your personal one)
3. Click **Invites** tab
4. Accept the Centurion invite

**If Invites tab is empty:**
- Wait 2–5 minutes after Step 1, then refresh
- Re-add tester in Meta (remove + add again)
- Try on mobile app instead of web
- Confirm you're logged into the correct Threads account

---

## Step 3: Verify invite was accepted

After accepting, go back to Meta:
https://developers.facebook.com/apps/1526251002514059/roles/roles/

Under **Threads Testers**, status should change from **Pending** → **Active** (or show accepted).

---

## Step 4: Retry OAuth

Only after Steps 1–3 succeed, open:

```
https://threads.net/oauth/authorize?client_id=1526251002514059&redirect_uri=https%3A%2F%2Flocalhost%2Fcallback&scope=threads_basic%2Cthreads_content_publish%2Cthreads_read_replies%2Cthreads_manage_replies%2Cthreads_manage_insights%2Cthreads_keyword_search&response_type=code
```

1. Log in as **@influencer.bot**
2. Click **Allow**
3. Copy `code=` from redirect URL: `https://localhost/callback?code=...`
4. Run:
   ```bash
   cd threads-agent && source .venv/bin/activate
   python scripts/exchange_code.py 1526251002514059 YOUR_APP_SECRET "PASTE_CODE"
   python -m agent.main post
   ```

---

## Alternative: Graph API Explorer (Threads-specific button)

If invite is accepted, you can also try:

1. https://developers.facebook.com/tools/explorer/
2. Change API dropdown from `graph.facebook.com` → **`threads.net` v1.0**
3. Click **Generate Threads Access Token** (NOT "Generate Access Token")
4. Select @influencer.bot → Allow
5. Copy token → `python scripts/import_token.py APP_SECRET "TOKEN"`

---

## Still stuck?

| Check | Question |
|-------|----------|
| Right account? | Are you logging into OAuth as @influencer.bot, not your personal Threads? |
| Right tester type? | Is user under **Threads Testers**, not Facebook Testers? |
| Invite accepted? | Does Threads → Website permissions → Invites show Centurion as Active? |
| Data checkup? | Any red banner on developers.facebook.com/apps requiring Data Use Checkup? |

Paste a screenshot of:
- Meta → App roles → Threads Testers section
- Threads → Website permissions → Invites tab

...and we can diagnose further.
