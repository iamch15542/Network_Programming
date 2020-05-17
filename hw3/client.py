#coding=utf-8
import socket
import boto3
import sys

def main():
    # check argv
    if len(sys.argv) != 3:
        print("Usage: python3 client.py <address> <PORT>")
        return

    # create socket
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((sys.argv[1], int(sys.argv[2])))
    print("Client connect to %s, use : %d port" % (sys.argv[1], int(sys.argv[2])))
    try:
        while True:
            server_respone = client.recv(1024)
            if len(server_respone) == 0:
                client.close()
                break;
            else:
                print(server_respone.decode(), end='')
                client_command = input()
                client.sendall(client_command.encode())
    except KeyboardInterrupt:
        print("\nClient close")

if __name__ == '__main__':
    main()