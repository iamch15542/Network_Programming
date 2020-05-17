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
                command_result = server_respone.decode()
                print(command_result, end='')
                result_len = len(command_result)
                respone = command_result[:result_len - 3]
                # print('\n------------')
                # print(respone)
                # print('-----------')
                if 'Register successfully.' in respone:
                    # print('ffff')
                    create_bucket_name = client.recv(1024).decode()
                    # print(create_bucket_name)
                    s3 = boto3.resource('s3')
                    s3.create_bucket(Bucket=create_bucket_name)
                    # print('Bucket name: %s' % create_bucket_name)
                elif 'Welcome,' in respone:
                    # print('welcome')
                    receive_bucket_name = client.recv(1024).decode()
                    bucket_name = receive_bucket_name
                    # print(receive_bucket_name)
                client_command = input()
                client.sendall(client_command.encode())
    except KeyboardInterrupt:
        print("\nClient close")

if __name__ == '__main__':
    main()