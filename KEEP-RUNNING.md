# Keeping OS AI running 24/7

Only the **backend** needs to run around the clock — the bots trade inside
it. The frontend (the web UI) is just for viewing and can be closed.

## Step 1 — Stop your PC from sleeping (the #1 reason bots stop)

Run these in PowerShell (they keep it awake while plugged in):

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 0   # optional: also keep the screen on
```

## Step 2 — Launch the backend so it auto-restarts

Double-click **`backend\run-24-7.bat`**. It runs the backend and, if it
ever crashes, restarts it after 5 seconds. Leave that window open (or
minimize it). That's the simplest setup.

## Step 3 (recommended) — Start it automatically at login

So it comes back after a reboot / Windows update. Run once in PowerShell:

```powershell
schtasks /create /tn "OSAI-Backend" /sc onlogon /rl highest ^
  /tr "\"C:\Users\Tahfeez\OneDrive\Desktop\OS AI\OS AI\backend\run-24-7.bat\""
```

Now it launches every time you log in. To start it at **boot** (before
login) run the same command in an **Administrator** PowerShell with
`/sc onstart` instead of `/sc onlogon`.

Remove it later with:

```powershell
schtasks /delete /tn "OSAI-Backend" /f
```

## Reality check

- Your PC must stay **on and awake**. If it sleeps or shuts down, the
  bots stop until it's back (they resume automatically on restart).
- For *true* 24/7 that doesn't depend on your PC, run the backend on a
  small cloud server (a ~$5/month VPS). Ask and I'll walk you through it.
- The bots are **paper mode** — they trade continuously with virtual USD.
  Nothing here spends real money; that only happens through the Phantom
  wallet panel where you approve each trade.
