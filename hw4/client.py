#coding=utf-8
import socket
import boto3
import sys
import os
import re
import time
import threading
from datetime import date
from kafka import KafkaConsumer, KafkaProducer

board_subscribe = {}
author_subscribe = {}
subscribe_list = []

def kafka_consumer(consumer):
    while True:
        msg_pack = consumer.poll(timeout_ms=500)
        for tp, messages in msg_pack.items():
            for message in messages:
                subscribe_topic = tp.topic
                key = message.key.decode()
                value = message.value.decode()
                notify_message = '*['
                if subscribe_topic in board_subscribe:
                    for keyword in board_subscribe[subscribe_topic]:
                        if keyword in value:
                            notify_message += subscribe_topic + '] ' + value + ' - by ' + key + '*\n% '
                            print(notify_message, end='')
                            break
                elif subscribe_topic in author_subscribe:
                    for keyword in author_subscribe[subscribe_topic]:
                        if keyword in value:
                            notify_message += key + '] ' + value + ' - by ' + subscribe_topic + '*\n% '
                            print(notify_message, end='')
                            break

def upload_txt(bucket_name, txt_name, content):
    txt = open(txt_name, 'a+', encoding='utf-8')
    txt.write(content)
    txt.close()
    s3 = boto3.resource('s3')
    target_bucket = s3.Bucket(bucket_name) 
    target_bucket.upload_file(txt_name, txt_name)
    os.remove(str(os.getcwd() + '/' + txt_name))

def main():
    # check argv
    if len(sys.argv) != 3:
        print("Usage: python3 client.py <address> <PORT>")
        return

    # create socket
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((sys.argv[1], int(sys.argv[2])))

    # kafka client
    timestamp = str(time.time())
    consumer = KafkaConsumer(group_id=timestamp, bootstrap_servers=['localhost:9092'], api_version =(0, 9))
    kafka_client = threading.Thread(target=kafka_consumer, args=(consumer, ))
    kafka_client.setDaemon(True)
    kafka_client.start()

    # init information
    bucket_name = ''
    client_command = ''
    client_info = {'login': False, 'username': None}
    s3 = boto3.resource('s3')
    global subscribe_list
    # print("Client connect to %s, use : %d port" % (sys.argv[1], int(sys.argv[2])))
    try:
        while True:
            server_respone = client.recv(1024)
            if len(server_respone) == 0:
                client.close()
                break;
            else:
                command_result = server_respone.decode()
                result_len = len(command_result)
                respone = command_result[:result_len - 3]
                if 'Register successfully.' in respone:
                    # register command
                    create_bucket_name = client.recv(1024).decode()
                    s3.create_bucket(Bucket=create_bucket_name)
                elif 'Welcome,' in respone:
                    # login command
                    bucket_name = client.recv(1024).decode()
                    user_name = re.search('Welcome, (.*).', respone).group(1)
                    client_info['login'] = True
                    client_info['username'] = user_name
                elif 'Create post successfully.' in respone:
                    # create-post command
                    receive_post_info = client.recv(1024).decode()
                    txt_name = receive_post_info + '.txt'
                    post_content = re.search('--content (.*)', client_command).group(1)
                    post_content = str(post_content).replace('<br>', '\n') + '\n--\n'
                    upload_txt(bucket_name, txt_name, post_content)
                elif 'readcommand' in respone:
                    # read command
                    print_len = len(respone)
                    print_respone = respone[:print_len - 11]
                    print(print_respone, end='')
                    receive_post_info = client.recv(1024).decode().strip()
                    info = []
                    for word in receive_post_info.split(' '):
                        info.append(word)
                    txt_name = info[1] + '.txt'
                    target_bucket = s3.Bucket(info[0])
                    target_object = target_bucket.Object(txt_name)
                    command_result = target_object.get()['Body'].read().decode() + '% '
                elif 'Delete successfully.' in respone:
                    # delete command
                    receive_post_info = client.recv(1024).decode()
                    txt_name = receive_post_info + '.txt'
                    target_bucket = s3.Bucket(bucket_name)
                    target_object = target_bucket.Object(txt_name) 
                    target_object.delete()
                elif 'Update successfully.' in respone:
                    # update command
                    receive_post_info = client.recv(1024).decode().strip()
                    info = []
                    for word in receive_post_info.split(' '):
                        info.append(word)
                    txt_name = info[1] + '.txt'
                    if info[0] == '--content':
                        target_bucket = s3.Bucket(bucket_name)
                        target_object = target_bucket.Object(txt_name)
                        object_content = target_object.get()['Body'].read().decode()
                        content = re.search('(.*)\n--\n(.*)', object_content).group(1)
                        comment = re.search('(.*)\n--\n(.*)', object_content).group(2)
                        new_content = re.search('--content (.*)', client_command).group(1)
                        new_content = str(new_content).replace('<br>', '\n')
                        new_post = new_content + '\n--\n' + comment
                        if comment != '':
                            new_post += '\n'
                        target_object.delete()
                        upload_txt(bucket_name, txt_name, new_post)
                elif 'Comment successfully.' in respone:
                    # comment command
                    receive_post_info = client.recv(1024).decode().strip()
                    info = []
                    for word in receive_post_info.split(' '):
                        info.append(word)
                    txt_name = info[1] + '.txt'
                    target_bucket = s3.Bucket(info[0])
                    target_object = target_bucket.Object(txt_name)
                    object_content = target_object.get()['Body'].read().decode()
                    postid_idx = client_command.find(info[1])
                    comment = client_command[postid_idx + len(info[1]) + 1: ]
                    new_post = object_content + client_info['username'] + ': ' + str(comment).replace('<br>', '\n') + '\n'
                    target_object.delete()
                    upload_txt(info[0], txt_name, new_post)
                elif 'Sent successfully.' in respone:
                    # mail-to command
                    receive_post_info = client.recv(1024).decode().strip()
                    info = []
                    for word in receive_post_info.split(' '):
                        info.append(word)
                    txt_name = info[1] + '-mail-to-you-' + info[2] + '.txt'
                    content = re.search('--content (.*)', client_command).group(1) + '\n'
                    content = str(content).replace('<br>', '\n')
                    upload_txt(info[0], txt_name, content)
                elif 'retrmailcommand' in respone:
                    # retr-mail command
                    print_len = len(respone)
                    print_respone = respone[:print_len - 15]
                    print(print_respone, end='')
                    receive_post_info = client.recv(1024).decode().strip()
                    info = []
                    for word in receive_post_info.split(' '):
                        info.append(word)
                    target_bucket = s3.Bucket(bucket_name)
                    txt_name = info[0] + '-mail-to-you-' + info[1] + '.txt'
                    target_object = target_bucket.Object(txt_name)
                    command_result = target_object.get()['Body'].read().decode() + '% '
                elif 'Mail deleted.' in respone:
                    # mail-delete command
                    receive_post_info = client.recv(1024).decode()
                    info = []
                    for word in receive_post_info.split(' '):
                        info.append(word)
                    txt_name = info[0] + '-mail-to-you-' + info[1] + '.txt'
                    target_bucket = s3.Bucket(bucket_name)
                    target_object = target_bucket.Object(txt_name) 
                    target_object.delete()
                elif 'Subscribe successfully' in respone:
                    command = []
                    for word in client_command.split(' '):
                        command.append(word)
                    if command[1] == '--board':
                        if command[2] in board_subscribe:
                            board_subscribe[command[2]].append(command[4])
                        else:
                            board_subscribe[command[2]] = []
                            board_subscribe[command[2]].append(command[4])
                    elif command[1] == '--author':
                        if command[2] in author_subscribe:
                            author_subscribe[command[2]].append(command[4])
                        else:
                            author_subscribe[command[2]] = []
                            author_subscribe[command[2]].append(command[4])
                    if command[2] not in subscribe_list:
                        subscribe_list.append(command[2])
                    consumer.subscribe(topics=subscribe_list)
                elif 'Unsubscribe successfully' in respone:
                    command = []
                    for word in client_command.split(' '):
                        command.append(word)
                    if command[1] == '--board':
                        del board_subscribe[command[2]] 
                    elif command[1] == '--author':
                        del author_subscribe[command[2]]
                    subscribe_list.remove(command[2])
                    consumer.subscribe(topics=subscribe_list)
                elif 'Bye,' in respone:
                    bucket_name = ''
                    client_info['username'] = None
                    client_info['login'] = False
                print(command_result, end='')
                client_command = input()
                if client_command == '':
                    client_command = 'empty'
                client.sendall(client_command.encode())
    except KeyboardInterrupt:
        print("\nClient close")

if __name__ == '__main__':
    main()