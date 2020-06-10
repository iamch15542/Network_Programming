#coding=utf-8
import threading
import boto3
import socket
import sqlite3
import sys
import os
import re
import time
from datetime import date
from kafka import KafkaConsumer, KafkaProducer

user_info = {}
user_email = {}
user_bucket = {}
user_register_num = 0

# database init
db = sqlite3.connect('server.db', check_same_thread = False)
print('Opened database successfully')
c = db.cursor()

def database_init():
    c.execute('''CREATE TABLE IF NOT EXISTS user_info(
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL,
                    bucket_name TEXT NOT NULL,
                    primary key(name));''')
    c.execute('''CREATE TABLE IF NOT EXISTS bbs_board(
                    boardname TEXT NOT NULL,
                    moderator TEXT NOT NULL,
                    primary key(boardname));''')
    c.execute('''CREATE TABLE IF NOT EXISTS bbs_post(
                    bid INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    date TEXT NOT NULL,
                    board_name TEXT NOT NULL,
                    content TEXT);''')
    c.execute('''CREATE TABLE IF NOT EXISTS bbs_mail(
                    timecheck TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    author TEXT NOT NULL,
                    date TEXT NOT NULL,
                    receiver_name TEXT NOT NULL,
                    content TEXT);''')
    c.execute('''CREATE TABLE IF NOT EXISTS post_comment(
                    post_id INTEGER NOT NULL,
                    comment TEXT,
                    username TEXT NOT NULL);''')
    db.commit()

def board_find(board):
    c.execute("SELECT * FROM bbs_board WHERE boardname = ? ", (board, ))
    board_list = c.fetchall()
    return False if board_list == [] else True

def client_connect(client, client_num):
    client_info = {'login': False, 'username': None}
    message = '********************************\n** Welcome to the BBS server. **\n********************************\n% '
    client.sendall(message.encode())
    board_subscribe = {}
    author_subscribe = {}
    global user_register_num
    while True:
        data = client.recv(1024)
        if len(data) == 0:
            client.close()
            break;
        else:
            remove_space = data.decode().strip()
            command = []
            post_info_send_to_client = ''
            # print("Receive command: %s" % remove_space)
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
                        bucket_name = command[1].lower() + '-' + str(user_register_num) + '-' + '0616091'
                        user_bucket[command[1]] = bucket_name
                        c.execute('INSERT INTO user_info VALUES(?, ?, ?, ?)', (command[1], command[2], command[3], bucket_name))
                        db.commit()
                        user_register_num += 1
                        post_info_send_to_client = bucket_name
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
                                post_info_send_to_client = user_bucket[command[1]]
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
                    message = 'Usage: logout\n% '
                elif client_info['login'] == False:
                    message = 'Please login first.\n% '
                else:
                    message = 'Bye, ' + client_info['username'] + '.\n% '
                    client_info['username'] = None
                    client_info['login'] = False
            elif command[0] == 'whoami':
                if len(command) != 1:
                    message = 'Usage: whoami\n% '
                elif client_info['login'] == False:
                    message = 'Please login first.\n% '
                else:
                    message = client_info['username'] + '\n% '
            elif command[0] == 'exit':
                client.close()
                break
            elif command[0] == 'create-board':
                if len(command) != 2:
                    message = 'Usage: create-board <name>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        if board_find(command[1]) == True:
                            message = 'Board already exist.\n% '
                        else:
                            c.execute('INSERT INTO bbs_board VALUES(?, ?)', (command[1], client_info['username']))
                            db.commit()
                            message = 'Create board successfully.\n% '
            elif command[0] == 'create-post':
                if client_info['login'] == False:
                    message = 'Please login first.\n% '
                else:
                    if len(command) > 2 and command[2] == '--title' and '--content' in command:
                        if board_find(command[1]) == False:
                            message = 'Board does not exist.\n% '
                        else:
                            title = re.search('--title (.*) --content', remove_space).group(1)
                            content = re.search('--content (.*)', remove_space).group(1)
                            c.execute('INSERT INTO bbs_post(title, author, date, board_name, content) VALUES(?, ?, ?, ?, ?)', (title, client_info['username'], str(date.today()), command[1], content))
                            db.commit()
                            message = 'Create post successfully.\n% '
                            post_info_send_to_client = str(c.lastrowid)
                            producer = KafkaProducer(bootstrap_servers=['localhost:9092'], api_version = (0, 9))
                            result = producer.send(command[1], key=client_info['username'].encode(), value=title.encode(), partition=0)
                            result = producer.send(client_info['username'], key=command[1].encode(), value=title.encode(), partition=0)
                    else:
                        message = 'Usage: create-post <board-name> --title <title> --content <content>\n% '
            elif command[0] == 'list-board':
                c.execute("SELECT * FROM bbs_board")
                board_list = c.fetchall()
                board_len = 4
                for board in board_list:
                    board_len = len(board[0]) if len(board[0]) > board_len else board_len
                if len(command) == 1:
                    message = 'Index\t' + 'Name'.ljust(board_len + 3) + 'Moderator\n'
                    idx = 0
                    for board in board_list:
                        idx += 1
                        message += str(idx) + '\t' + board[0].ljust(board_len + 3) + board[1] + '\n'
                    message += '% '
                elif len(command) == 2:
                    key_word = command[1][2:]
                    # print('list_board_key_word: %s' % key_word)
                    message = 'Index\t' + 'Name'.ljust(board_len + 3) + 'Moderator\n'
                    idx = 0
                    for board in board_list:
                        if re.search(key_word, board[0]) != None:
                            idx += 1
                            message += str(idx) + '\t' + board[0].ljust(board_len + 3) + board[1] + '\n'
                    message += '% '
                else:
                    message = 'Usage: list-board ##<key>\n% '
            elif command[0] == 'list-post':
                if len(command) == 2:
                    if board_find(command[1]) == False:
                        message = 'Board does not exist.\n% '
                    else:
                        c.execute('SELECT * FROM bbs_post WHERE board_name = ?', (command[1], ))
                        post_list = c.fetchall()
                        text_len = [5, 6]
                        for post in post_list:
                            text_len[0] = len(post[1]) if len(post[1]) > text_len[0] else text_len[0]
                            text_len[1] = len(post[2]) if len(post[2]) > text_len[1] else text_len[1]
                        message = 'ID\t' + 'Title'.ljust(text_len[0] + 3) + 'Author'.ljust(text_len[1] + 3) + 'Date\n'
                        for post in post_list:
                            month = re.search('(.*)-(.*)-(.*)', post[3]).group(2)
                            day = re.search('(.*)-(.*)-(.*)', post[3]).group(3)
                            message += str(post[0]) + '\t' + post[1].ljust(text_len[0] + 3) + post[2].ljust(text_len[1] + 3) + month + '/' + day + '\n'
                        message += '% '
                elif len(command) == 3:
                    if board_find(command[1]) == False:
                        message = 'Board does not exist.\n% '
                    else:
                        c.execute('SELECT * FROM bbs_post WHERE board_name = ?', (command[1], ))
                        post_list = c.fetchall()
                        text_len = [5, 6]
                        for post in post_list:
                            text_len[0] = len(post[1]) if len(post[1]) > text_len[0] else text_len[0]
                            text_len[1] = len(post[2]) if len(post[2]) > text_len[1] else text_len[1]
                        message = 'ID\t' + 'Title'.ljust(text_len[0] + 3) + 'Author'.ljust(text_len[1] + 3) + 'Date\n'
                        key_word = command[2][2:]
                        # print('list_post_key_word:  %s' % key_word)
                        for post in post_list:
                            if re.search(key_word, post[1]) != None:
                                month = re.search('(.*)-(.*)-(.*)', post[3]).group(2)
                                day = re.search('(.*)-(.*)-(.*)', post[3]).group(3)
                                message += str(post[0]) + '\t' + post[1].ljust(text_len[0] + 3) + post[2].ljust(text_len[1] + 3) + month + '/' + day + '\n'
                        message += '% '
                else:
                    message = 'Usage: list-post <board-name> ##<key>\n% '
            elif command[0] == 'read':
                if len(command) != 2:
                    message = 'Usage: read <post-id>\n% '
                else:
                    c.execute('SELECT * FROM bbs_post WHERE bid = ?', (int(command[1]), ))
                    post_info = c.fetchone()
                    if post_info == None:
                        message = 'Post does not exist.\n% '
                    else:
                        message = 'Author\t:' + post_info[2] + '\n'
                        message += 'Title\t:' + post_info[1] + '\n'
                        message += 'Date\t:' + post_info[3] + '\n'
                        message += '--\n'
                        # post_content = str(post_info[5]).replace('<br>', '\n')
                        # message += post_content + '\n--\n'
                        # c.execute('SELECT * FROM post_comment WHERE post_id = ?', (int(command[1]), ))
                        # comment_info = c.fetchall()
                        # if comment_info != []:
                        #     for comment in comment_info:
                        #         message += comment[2] + ': '
                        #         remove_br = str(comment[1]).replace('<br>', '\n')
                        #         message += remove_br + '\n'
                        message += 'readcommand\n% '
                        get_bucket = user_bucket[post_info[2]]
                        post_info_send_to_client = get_bucket + ' ' + command[1]
            elif command[0] == 'delete-post':
                if len(command) != 2:
                    message = 'Usage: delete-post <post-id>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        c.execute('SELECT * FROM bbs_post WHERE bid = ?', (int(command[1]), ))
                        post_info = c.fetchone()
                        if post_info == None:
                            message = 'Post does not exist.\n% '
                        else:
                            if client_info['username'] != post_info[2]:
                                message = 'Not the post owner.\n% '
                            else:
                                c.execute('DELETE FROM bbs_post WHERE bid = ?', (int(command[1]), ))
                                c.execute('DELETE FROM post_comment WHERE post_id = ?', (int(command[1]), ))
                                db.commit()
                                message = 'Delete successfully.\n% '
                                post_info_send_to_client = command[1]
            elif command[0] == 'update-post':
                if client_info['login'] == False:
                    message = 'Please login first.\n% '
                else:
                    if len(command) < 3:
                        message = 'Usage: update-post <post-id> --title/content <new>\n'
                    else:
                        c.execute('SELECT * FROM bbs_post WHERE bid = ?', (int(command[1]), ))
                        post_info = c.fetchone()
                        if post_info == None:
                            message = 'Post does not exist.\n% '
                        else:
                            if client_info['username'] != post_info[2]:
                                message = 'Not the post owner.\n% '
                            else:
                                if command[2] == '--title':
                                    title = re.search('--title (.*)', remove_space).group(1)
                                    c.execute('UPDATE bbs_post SET title = ? WHERE bid = ?', (title, int(command[1])))
                                    db.commit()
                                elif command[2] == '--content': 
                                    content = re.search('--content (.*)', remove_space).group(1)
                                    c.execute('UPDATE bbs_post SET content = ? WHERE bid = ?', (content, int(command[1])))
                                    db.commit()
                                message = 'Update successfully.\n% '
                                post_info_send_to_client = command[2] + ' ' + command[1]
            elif command[0] == 'comment':
                if len(command) < 3:
                    message = 'Usage: comment <post-id> <comment>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        c.execute('SELECT * FROM bbs_post WHERE bid = ?', (int(command[1]), ))
                        post_info = c.fetchone()
                        if post_info == None:
                            message = 'Post does not exist.\n% '
                        else:
                            postid_idx = remove_space.find(command[1])
                            comment = remove_space[postid_idx + len(command[1]) + 1: ]
                            c.execute('INSERT INTO post_comment VALUES(?, ?, ?)', (int(command[1]), comment, client_info['username']))
                            db.commit()
                            message = 'Comment successfully.\n% '
                            post_bucket = user_bucket[post_info[2]]
                            post_info_send_to_client = post_bucket + ' ' + command[1] + ' ' + post_info[2]
            elif command[0] == 'mail-to':
                if client_info['login'] == False:
                    message = 'Please login first.\n% '
                else:
                    if len(command) > 2 and command[2] == '--subject' and '--content' in command:
                        if user_info.get(command[1]) == None:
                            message = command[1] + ' does not exist.\n% '
                        else:
                            subject = re.search('--subject (.*) --content', remove_space).group(1)
                            content = re.search('--content (.*)', remove_space).group(1)
                            timestamp = str(time.time())
                            c.execute('INSERT INTO bbs_mail(timecheck, subject, author, date, receiver_name, content) VALUES(?, ?, ?, ?, ?, ?)', (timestamp, subject, client_info['username'], str(date.today()), command[1], content))
                            db.commit()
                            message = 'Sent successfully.\n% '
                            post_bucket = user_bucket[command[1]]
                            post_info_send_to_client = post_bucket + ' ' + client_info['username'] + ' ' + timestamp
                    else:
                        message = 'Usage: mail-to <username> --subject <subject> --content <content>\n% '
            elif command[0] == 'list-mail':
                if len(command) == 1:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        c.execute('SELECT * FROM bbs_mail WHERE receiver_name = ?', (client_info['username'], ))
                        mail_list = c.fetchall()
                        text_len = [7, 4]
                        for mail in mail_list:
                            text_len[0] = len(mail[1]) if len(mail[1]) > text_len[0] else text_len[0]
                            text_len[1] = len(mail[2]) if len(mail[2]) > text_len[1] else text_len[1]
                        message = 'ID\t' + 'Subject'.ljust(text_len[0] + 3) + 'From'.ljust(text_len[1] + 3) + 'Date\n'
                        idx = 1
                        for mail in mail_list:
                            month = re.search('(.*)-(.*)-(.*)', mail[3]).group(2)
                            day = re.search('(.*)-(.*)-(.*)', mail[3]).group(3)
                            message += str(idx) + '\t' + mail[1].ljust(text_len[0] + 3) + mail[2].ljust(text_len[1] + 3) + month + '/' + day + '\n'
                            idx += 1
                        message += '% '
                else:
                    message = 'Usage: list-mail\n% '
            elif command[0] == 'retr-mail':
                if len(command) != 2:
                    message = 'Usage: retr-mail <mail#>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        c.execute('SELECT * FROM bbs_mail WHERE receiver_name = ?', (client_info['username'], ))
                        mail_list = c.fetchall()
                        if mail_list == None:
                            message = 'No such mail.\n% '
                        else:
                            idx = 1
                            mail_find = False
                            for mail in mail_list:
                                if int(command[1]) == idx:
                                    message = 'Subject\t:' + mail[1] + '\n'
                                    message += 'From\t:' + mail[2] + '\n'
                                    message += 'Date\t:' + mail[3] + '\n'
                                    message += '--\n'
                                    message += 'retrmailcommand\n% '
                                    post_info_send_to_client = mail[2] + ' ' + mail[0]
                                    mail_find = True
                                idx += 1
                            if mail_find == False:
                                message = 'No such mail.\n% '
            elif command[0] == 'delete-mail':
                if len(command) != 2:
                    message = 'Usage: delete-mail <mail#>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        c.execute('SELECT * FROM bbs_mail WHERE receiver_name = ?', (client_info['username'], ))
                        mail_list = c.fetchall()
                        if mail_list == None:
                            message = 'No such mail.\n% '
                        else:
                            idx = 1
                            mail_find = False
                            for mail in mail_list:
                                if int(command[1]) == idx:
                                    message = 'Mail deleted.\n% '
                                    post_info_send_to_client = mail[2] + ' ' + mail[0]
                                    c.execute('DELETE FROM bbs_mail WHERE timecheck = ?', (mail[0], ))
                                    db.commit()
                                    mail_find = True
                                idx += 1
                            if mail_find == False:
                                message = 'No such mail.\n% '
            elif command[0] == 'subscribe':
                if len(command) != 5:
                    if command[1] == '--board':
                        message = 'usage: subscribe --board <board-name> --keyword <keyword>\n% '
                    elif command[1] == '--author':
                        message = 'usage: subscribe --author <author-name> --keyword <keyword>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        if command[1] == '--board':
                            if command[3] != '--keyword':
                                message = 'usage: subscribe --board <board-name> --keyword <keyword>\n% '
                            elif command[2] in board_subscribe:
                                if command[4] in board_subscribe[command[2]]:
                                    message = 'Already subscribed\n% '
                                else:
                                    board_subscribe[command[2]].append(command[4])
                                    message = 'Subscribe successfully\n% '
                            else:
                                board_subscribe[command[2]] = []
                                board_subscribe[command[2]].append(command[4])
                                message = 'Subscribe successfully\n% '
                        elif command[1] == '--author':
                            if command[3] != '--keyword':
                                message = 'usage: subscribe --author <author-name> --keyword <keyword>\n% '
                            elif command[2] in author_subscribe:
                                if command[4] in author_subscribe[command[2]]:
                                    message = 'Already subscribed\n% '
                                else:
                                    author_subscribe[command[2]].append(command[4])
                                    message = 'Subscribe successfully\n% '
                            else:
                                author_subscribe[command[2]] = []
                                author_subscribe[command[2]].append(command[4])
                                message = 'Subscribe successfully\n% '
            elif command[0] == 'unsubscribe':
                if len(command) != 3:
                    if command[1] == '--board':
                        message = 'usage: unsubscribe --board <board-name>\n% '
                    elif command[1] == '--author':
                        message = 'usage: unsubscribe --author <author-name>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        if command[1] == '--board':
                            if command[2] in board_subscribe:
                                del board_subscribe[command[2]]  
                                message = 'Unsubscribe successfully\n% '
                            else:
                                message = "You haven't subscribed " + command[2] + '\n% '
                        elif command[1] == '--author':
                            if command[2] in author_subscribe:
                                del author_subscribe[command[2]]  
                                message = 'Unsubscribe successfully\n% '
                            else:
                                message = "You haven't subscribed " + command[2] + '\n% '
            elif command[0] == 'list-sub':
                if len(command) != 1:
                    message = 'Usage: list-sub\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        message = ''
                        if len(board_subscribe) > 0:
                            message = 'Board: '
                            for board in board_subscribe:
                                message += board + ':'
                                for subscribe in board_subscribe[board]:
                                    message += ' ' + subscribe
                                message += '; '
                            message += '\n'
                        if len(author_subscribe) > 0:
                            message += 'Author: '
                            for author in author_subscribe:
                                message += author + ':'
                                for subscribe in author_subscribe[author]:
                                    message += ' ' + subscribe
                                message += '; '
                        message += '\n% '
            else:
                message = '% '
                # print('ERROR: Error command. %s' % command[0])
            client.sendall(message.encode())
            if post_info_send_to_client != '':
                # print(post_info_send_to_client)
                time.sleep(0.2)
                client.sendall(post_info_send_to_client.encode())
                post_info_send_to_client = ''

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 server.py <PORT>")
        return
    database_init()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', int(sys.argv[1])))
    server.listen(32)
    print("Server use : %d port" % int(sys.argv[1]))
    client_num = 0;
    try:
        while True:
            client, addr = server.accept()
            client_thread = threading.Thread(target=client_connect, args=(client, client_num))
            client_thread.setDaemon(True)
            client_thread.start()
            print("New connection.")
            client_num = client_num + 1
    except KeyboardInterrupt:
        print('\nServer close')
        db.close()
        os.remove(str(os.getcwd() + '/server.db'))
        s3 = boto3.resource('s3')
        for key, value in user_bucket.items():
            target_bucket = s3.Bucket(value)
            for target_bucket_object in target_bucket.objects.all():
                target_object = target_bucket.Object(target_bucket_object.key)
                target_object.delete()
            target_bucket.delete()
        print('Clean S3 bucket!')

if __name__ == '__main__':
    main()