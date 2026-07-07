# Deploying OS AI to a VPS (24/7)

This puts the whole app — backend bots, agents, frontend — on a cloud
server so it runs around the clock, independent of your PC. Follow the
steps in order. Commands run **on the server** unless it says "on your PC".

**What you get:** `https://osai.yourdomain.com`, password-protected, with
the frontend and API behind one HTTPS address, auto-renewing certificates,
auto-restart on reboot, and one-click deploys from GitHub.

> Security first: the backend has **no login of its own**. This stack hides
> the entire app behind an HTTPS password wall (Nginx Basic Auth). Never
> expose port 8000 to the internet directly. Never put a wallet seed phrase
> on the server — real trades still happen only through your local Phantom.

---

## 0. Prerequisites

- A domain in **Namecheap** (e.g. `yourdomain.com`).
- A VPS with **Ubuntu 24.04**, 1 vCPU / 2 GB RAM is plenty
  (Hetzner ~€4/mo, DigitalOcean/Vultr ~$6/mo). Note its **public IP**.
- Your code pushed to **GitHub** (see step 8 if you haven't yet).

---

## 1. Point your domain at the server (Namecheap)

1. Namecheap → **Domain List** → **Manage** next to your domain →
   **Advanced DNS**.
2. Under **Host Records**, delete any parking/`CNAME` records that conflict,
   then **Add New Record**:
   - **Type:** `A Record` · **Host:** `osai` (this makes
     `osai.yourdomain.com`; use `@` for the root domain instead) ·
     **Value:** your VPS **public IP** · **TTL:** Automatic.
3. Save. DNS takes 5–30 min to propagate. Check from your PC:
   `nslookup osai.yourdomain.com` should return your VPS IP.

---

## 2. First login + a non-root user

SSH in as root (from your PC), then create a normal user with sudo:

```bash
ssh root@YOUR_VPS_IP

adduser deploy                     # set a password when prompted
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy   # copy your SSH key
```

Log out and back in as `deploy`: `ssh deploy@YOUR_VPS_IP`.

---

## 3. Secure Ubuntu

```bash
sudo apt update && sudo apt -y upgrade

# Firewall: allow only SSH + web.
sudo apt -y install ufw
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Harden SSH: no root login, keys only (make sure key login works first!).
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# Brute-force protection + automatic security updates.
sudo apt -y install fail2ban unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades   # choose "Yes"
```

---

## 4. Install Docker + Compose

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
newgrp docker                      # apply the group now
docker compose version             # should print v2.x
```

---

## 5. Get the code

```bash
sudo mkdir -p /opt/os-ai && sudo chown deploy:deploy /opt/os-ai
git clone https://github.com/YOUR_USER/YOUR_REPO.git /opt/os-ai
cd /opt/os-ai
```

---

## 6. Configure secrets + the password wall

```bash
# App secrets (domain + API keys). Fill in your real keys.
cp .env.prod.example .env
nano .env                          # set DOMAIN=osai.yourdomain.com, HELIUS_API_KEY, etc.

# The login you'll use in the browser. Pick a username + strong password.
sudo apt -y install apache2-utils
htpasswd -bc deploy/htpasswd admin 'CHOOSE-A-STRONG-PASSWORD'
```

`.env` and `deploy/htpasswd` are gitignored — they stay on the server only.

---

## 7. Launch with HTTPS (one command)

```bash
chmod +x deploy/init-letsencrypt.sh
./deploy/init-letsencrypt.sh you@youremail.com
```

This builds the images, starts everything, and fetches a real Let's Encrypt
certificate. When it finishes, open **https://osai.yourdomain.com**, log in
with the username/password from step 6 — you're live.

Useful checks:

```bash
docker compose -f docker-compose.prod.yml ps          # all "Up"
docker compose -f docker-compose.prod.yml logs -f backend   # bot activity
```

Certificates renew automatically (the `certbot` container checks twice a
day). The whole stack restarts automatically after a reboot
(`restart: unless-stopped`).

---

## 8. Auto-deploy from GitHub (optional but recommended)

Now every `git push` to `main` redeploys the server.

**On the server**, create a deploy SSH key and authorize it:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/deploy_key            # copy this PRIVATE key
```

**On GitHub**, repo → **Settings → Secrets and variables → Actions → New
repository secret**, add four:

| Secret        | Value                                   |
|---------------|-----------------------------------------|
| `VPS_HOST`    | your VPS IP                             |
| `VPS_USER`    | `deploy`                                |
| `VPS_SSH_KEY` | the private key you copied above        |
| `VPS_APP_DIR` | `/opt/os-ai`                            |

The workflow in `.github/workflows/deploy.yml` does the rest. Test it:
push any change, watch the **Actions** tab, then refresh your site.

> If you haven't pushed to GitHub yet: create an empty repo there, then on
> your PC run `git remote add origin <url>` and `git push -u origin main`.

---

## Day-to-day

```bash
cd /opt/os-ai
docker compose -f docker-compose.prod.yml logs -f            # watch
docker compose -f docker-compose.prod.yml restart backend    # restart one
docker compose -f docker-compose.prod.yml down               # stop all
git pull && docker compose -f docker-compose.prod.yml up -d --build   # manual deploy
```

Your ledgers and tuning live on the `botdata` Docker volume — they survive
redeploys and reboots. Nothing here spends real money: the bots are paper,
and live trades still require your Phantom approval from the wallet panel.

---

## Notes

- **Postgres/Redis** aren't in this minimal stack — the app runs fine
  without them (in-memory cache; `/market/history` charts stay empty). To
  add them later, port the two services from `backend/docker-compose.yml`
  into `docker-compose.prod.yml` and set `DATABASE_URL` / `REDIS_URL`.
- **Cost of going live:** keep `EXECUTION_ARMED=false` until the paper
  scorecard is genuinely green. Being on a VPS doesn't change the gate.
