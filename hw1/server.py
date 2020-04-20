#coding=utf-8
import threading
import socket
import select
import sqlite3
import sys

user_info = {}
user_email = {}

def client_connect(client):
    client_info = {'login': False, 'username': None}
    message = '********************************\n** Welcome to the BBS server. **\n********************************\n% '
    client.sendall(message.encode())
    while True:
        data = client.recv(1024)
        if len(data) == 0:
            client.close()
            break;
        else:
            remove_space = data.decode().strip()
            command = []
            print("Receive command: %s" % remove_space)
            for word in remove_space.split(' '):
                command.append(word)
            if command[0] == 'register':
                cmd_format = True
                unique = True
                if len(command) != 4:
                    cmd_format = False
                else:
                    if user_info.get(command[1]) != None:
                        unique = False
                    else:
                        user_info[command[1]] = command[3]
                        user_email[command[1]] = command[2]
                if cmd_format == False:
                    message = 'Usage: register <username> <email> <password>\n% '
                elif unique == False:
                    message = 'Username is already used.\n% '
                else:
                    message = 'Register successfully.\n% '
            elif command[0] == 'login':
                cmd_format = True
                pwd = True
                already = False
                if len(command) != 3:
                    cmd_format = False
                else:
                    if client_info['login'] == True:
                        already = True
                    else: 
                        if user_info.get(command[1]) != None:
                            if command[2] == user_info[command[1]]:
                                client_info['login'] = True
                                client_info['username'] = command[1]
                            else:
                                pwd = False
                        else:
                            pwd = False
                if cmd_format == False:
                    message = 'Usage: login <username> <password>\n% '
                elif pwd == False:
                    message = 'Login failed.\n% '
                elif already == True:
                    message = 'Please logout first.\n% '
                else:
                    message = 'Welcome, ' + command[1] + '.\n% '
            elif command[0] == 'logout':
                if len(command) != 1:
                    message = '% '
                elif client_info['login'] == False:
                    message = 'Please login first.\n% '
                else:
                    message = 'Bye, ' + client_info['username'] + '\n% '
                    client_info['username'] = None
                    client_info['login'] = False
            elif command[0] == 'whoami':
                if len(command) != 1:
                    message = '% '
                elif client_info['login'] == False:
                    message = 'Please login first.\n% '
                else:
                    message = client_info['username'] + '\n% '
            elif command[0] == 'exit':
                client.close()
                break
            else:
                message = '% '
                print('ERROR: Error command. %s' % command[0])
            client.sendall(message.encode())

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 server.py <PORT>")
        return
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', int(sys.argv[1])))
    server.listen(32)
    while True:
        client, addr = server.accept()
        print("New Client connection")
        client_thread = threading.Thread(target=client_connect, args=(client,))
        client_thread.setDaemon(True)
        client_thread.start()

if __name__ == '__main__':
    main()