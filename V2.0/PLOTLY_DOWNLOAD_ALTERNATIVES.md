# 🌐 Plotly.js Download - Pi Cannot Reach CDN

## Problem
Your Pi cannot resolve `cdn.plotly.ly` (DNS failure). This means the Pi either:
- Has limited internet access
- DNS servers are blocked
- Firewall is blocking CDN access

## Solutions (Pick One)

---

### ✅ **Option 1: Download on Windows PC → Transfer via Git (RECOMMENDED)**

This is the **easiest** method since you're already using Git to sync code.

#### Step 1: Download on Your Windows PC

**Method A - Double-click the batch file:**
```
DOWNLOAD_PLOTLY_ON_PC.bat
```

**Method B - Run PowerShell script:**
```powershell
cd "C:\Users\willi\OneDrive - Stellenbosch University\2025\Skripsie\Coding\RaspPI\V2.0"
.\DOWNLOAD_PLOTLY_ON_PC.ps1
```

**Method C - Manual browser download:**
1. Open in browser: https://cdn.plotly.ly/plotly-2.27.0.min.js
2. Right-click → Save As...
3. Save to: `C:\Users\willi\OneDrive - Stellenbosch University\2025\Skripsie\Coding\RaspPI\V2.0\web\static\js\plotly-2.27.0.min.js`

#### Step 2: Commit and Push to GitHub

```bash
# On Windows PC (in Git Bash or PowerShell)
cd "C:\Users\willi\OneDrive - Stellenbosch University\2025\Skripsie\Coding\RaspPI\V2.0"

git add web/static/js/plotly-2.27.0.min.js
git commit -m "Add Plotly.js for local hosting (Pi cannot reach CDN)"
git push origin Test
```

#### Step 3: Pull on Raspberry Pi

```bash
# On the Pi
cd ~/Documents/RaspPI/V2.0
git pull origin Test
```

#### Step 4: Verify and Restart

```bash
# Verify file exists
ls -lh web/static/js/plotly-2.27.0.min.js
# Should show ~3.5 MB

# Restart web server
python3 run_web_interface.py
```

#### Step 5: Test in Browser
- Navigate to scans page
- Hard refresh: `Ctrl + Shift + R`
- Console should show: `Plotly status: LOADED ✅`

---

### 🔄 **Option 2: Download on PC → Transfer via SCP**

If you don't want to commit the large file to Git:

#### Step 1: Download on Windows PC
(Same as Option 1, Step 1)

#### Step 2: Transfer via SCP

**Using Windows PowerShell:**
```powershell
cd "C:\Users\willi\OneDrive - Stellenbosch University\2025\Skripsie\Coding\RaspPI\V2.0"

scp web/static/js/plotly-2.27.0.min.js user@3dscanner.local:~/Documents/RaspPI/V2.0/web/static/js/
```

**Or using WinSCP (GUI):**
1. Connect to Pi via WinSCP
2. Navigate to remote: `/home/user/Documents/RaspPI/V2.0/web/static/js/`
3. Drag `plotly-2.27.0.min.js` from local to remote

---

### 💾 **Option 3: Download on PC → Transfer via USB**

#### Step 1: Download on Windows PC
(Same as Option 1, Step 1)

#### Step 2: Copy to USB Drive
```
Copy: C:\Users\willi\...\RaspPI\V2.0\web\static\js\plotly-2.27.0.min.js
To: USB:\plotly-2.27.0.min.js
```

#### Step 3: On Raspberry Pi
```bash
# Insert USB drive
# Mount if not auto-mounted
sudo mkdir -p /mnt/usb
sudo mount /dev/sda1 /mnt/usb

# Create directory if needed
mkdir -p ~/Documents/RaspPI/V2.0/web/static/js

# Copy file
cp /mnt/usb/plotly-2.27.0.min.js ~/Documents/RaspPI/V2.0/web/static/js/

# Verify
ls -lh ~/Documents/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js
```

---

### 🌍 **Option 4: Try Alternative CDNs on Pi**

Sometimes different CDNs work when others don't.

**jsDelivr (often works when others fail):**
```bash
wget https://cdn.jsdelivr.net/npm/plotly.js@2.27.0/dist/plotly.min.js \
     -O web/static/js/plotly-2.27.0.min.js
```

**unpkg:**
```bash
wget https://unpkg.com/plotly.js@2.27.0/dist/plotly.min.js \
     -O web/static/js/plotly-2.27.0.min.js
```

**Google's CDN (sometimes faster):**
```bash
wget https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js \
     -O web/static/js/plotly-2.27.0.min.js
```

---

### 🔧 **Option 5: Fix Pi DNS (Advanced)**

If you want to fix the DNS issue:

```bash
# Check current DNS
cat /etc/resolv.conf

# Try Google's DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.4.4" | sudo tee -a /etc/resolv.conf

# Test
ping -c 3 cdn.plotly.ly

# If works, try wget again
wget https://cdn.plotly.ly/plotly-2.27.0.min.js \
     -O web/static/js/plotly-2.27.0.min.js
```

---

## Verification After Transfer

**Check file size:**
```bash
ls -lh web/static/js/plotly-2.27.0.min.js
```
Expected: ~3.5 MB (around 3,500,000 bytes)

**Check first line:**
```bash
head -n 1 web/static/js/plotly-2.27.0.min.js
```
Should show JavaScript code with "plotly" or "function"

**Test Flask serving:**
```bash
# While web server is running:
curl -I http://localhost:5000/static/js/plotly-2.27.0.min.js
```
Should show: `HTTP/1.1 200 OK`

---

## Updated base.html Should Work

Your `base.html` now has fallback logic:
```html
<script src="https://cdn.plotly.ly/plotly-2.27.0.min.js" 
        onerror="this.onerror=null; this.src='{{ url_for('static', filename='js/plotly-2.27.0.min.js') }}'">
</script>
```

This means:
1. Browser tries CDN first
2. If CDN fails → automatically loads local file
3. Works either way!

---

## My Recommendation

**Use Option 1** (Git transfer):
- ✅ Easiest (you're already using Git)
- ✅ Automatic sync
- ✅ Version controlled
- ✅ Works every time
- ⚠️ Large file in repo (~3.5 MB)

**Steps:**
1. Run `DOWNLOAD_PLOTLY_ON_PC.bat` (or .ps1)
2. `git add web/static/js/plotly-2.27.0.min.js`
3. `git commit -m "Add Plotly.js for local hosting"`
4. `git push`
5. On Pi: `git pull`
6. Restart web server
7. ✅ Done!

---

## Quick Status Check

After transfer, verify in browser console (F12):
```javascript
typeof Plotly
```

Expected: `"object"` ✅

Console should show:
```
📊 Initializing 3D visualizer...
   Plotly status: LOADED ✅
```

---

## If You Still See Errors

Make sure directory exists:
```bash
mkdir -p ~/Documents/RaspPI/V2.0/web/static/js
```

Check Flask configuration in `web/web_interface.py`:
```python
self.app = Flask(__name__, 
                 template_folder='templates',
                 static_folder='static')  # ← Must be present
```

Clear browser cache:
- `Ctrl + Shift + R` (hard refresh)
- Or `Ctrl + Shift + Delete` → Clear cache

---

## Summary

**Fastest solution:**
1. Download on PC: Double-click `DOWNLOAD_PLOTLY_ON_PC.bat`
2. Commit to Git: `git add web/static/js/plotly-2.27.0.min.js && git commit && git push`
3. Pull on Pi: `git pull`
4. Restart: `python3 run_web_interface.py`
5. Refresh browser: `Ctrl + Shift + R`

**Done! 🎉**
