### 1. System Reconnaissance
```bash
# See what user the victim is running as
Shell#: whoami

# Get the computer's hostname
Shell#: hostname

# See all environment variables
Shell#: env

# Check what OS and version
Shell#: uname -a

# See system uptime
Shell#: uptime

# Check disk usage
Shell#: df -h
```

### 2. Process Exploration
```bash
# See all running processes
Shell#: ps aux

# Find specific processes (like browsers)
Shell#: ps aux | grep -i chrome

# Count how many processes are running
Shell#: ps aux | wc -l

# Show process tree
Shell#: pstree  # Linux
Shell#: ps -ef  # macOS alternative
```

### 3. Network Snooping
```bash
# See all network connections
Shell#: netstat -an

# Show active internet connections
Shell#: netstat -an | grep ESTABLISHED

# Display routing table
Shell#: netstat -rn

# Show listening ports
Shell#: netstat -an | grep LISTEN

# Get all network interfaces and IPs
Shell#: ifconfig
```

### 4. File System Fun
```bash
# Create a secret file
Shell#: echo "I was here!" > .hidden_file.txt

# List all files including hidden ones
Shell#: ls -la

# Create a directory
Shell#: mkdir botnet_was_here

# Create a file with current date
Shell#: date > timestamp.txt
Shell#: cat timestamp.txt

# Find all .txt files in current directory
Shell#: find . -name "*.txt"

# Show file contents backwards!
Shell#: rev timestamp.txt  # Linux
Shell#: tail -r timestamp.txt  # macOS
```

### 5. Creative Text Manipulation
```bash
# Create ASCII art file
Shell#: echo "  ___  " > robot.txt
Shell#: echo " |o o| " >> robot.txt
Shell#: echo " |\_/| " >> robot.txt
Shell#: echo " ----- " >> robot.txt
Shell#: cat robot.txt

# Create a simple "ransom note"
Shell#: echo "Your files have been... borrowed!" > note.txt
Shell#: cat note.txt

# Count words in a file
Shell#: wc -w /etc/hosts

# Display file with line numbers
Shell#: cat -n /etc/hosts
```

### 6. System Information Hunt
```bash
# See current date and time
Shell#: date

# Show calendar
Shell#: cal

# Check battery status (macOS)
Shell#: pmset -g batt

# See logged in users
Shell#: who

# Show last login times
Shell#: last | head -10

# Display system info (macOS)
Shell#: system_profiler SPHardwareDataType
```

### 7. Fun with Output
```bash
# Create a countdown
Shell#: for i in 5 4 3 2 1; do echo $i; sleep 1; done; echo "Botnet activated!"

# Display a message repeatedly
Shell#: yes "Hacked!" | head -5

# Generate random numbers
Shell#: echo $RANDOM

# Show ASCII values
Shell#: echo "Hello" | od -A n -t d1

# Print colored text (if terminal supports it)
Shell#: echo -e "\033[31mRed Text\033[0m"
```

### 8. File Download/Upload Practice
```bash
# Download the hosts file
Shell#: download /etc/hosts

# Create and download a custom file
Shell#: echo "Student assignment complete!" > assignment.txt
Shell#: download assignment.txt

# Upload a file (prepare test.txt on host first)
Shell#: upload test.txt
Shell#: cat test.txt
```

### 9. Search and Discovery
```bash
# Find files modified in last 24 hours
Shell#: find . -mtime -1

# Search for a word in a file
Shell#: grep -i "localhost" /etc/hosts

# Count lines in a file
Shell#: wc -l /etc/hosts

# Show first 5 lines of a file
Shell#: head -5 /etc/hosts

# Show last 5 lines of a file
Shell#: tail -5 /etc/hosts
```

### 10. Combining Commands (Advanced)
```bash
# Chain multiple commands
Shell#: whoami && hostname && date

# Create a detailed system report
Shell#: echo "=== System Report ===" > report.txt
Shell#: echo "User: $(whoami)" >> report.txt
Shell#: echo "Host: $(hostname)" >> report.txt
Shell#: echo "Date: $(date)" >> report.txt
Shell#: cat report.txt

# Find and count specific file types
Shell#: find . -name "*.py" | wc -l
```