#coding=utf-8
import threading
import socket
import sqlite3
import sys
import re

user_info = {}
user_email = {}

# database init
db = sqlite3.connect('server.db', check_same_thread = False)
print('Opened database successfully')
c = db.cursor()

def database_init():
    c.execute('''CREATE TABLE IF NOT EXISTS user_info(
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL,
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
    c.execute('''CREATE TABLE IF NOT EXISTS post_comment(
                    post_id INTEGER NOT NULL,
                    comment TEXT,
                    username TEXT NOT NULL);''')
    db.commit()

def board_find(board):
    c.execute("SELECT * FROM bbs_board WHERE name = ? ", (board, ))
    board_list = c.fetchall()
    if board_list == []:
        return False
    else:
        return True


def client_connect(client, client_num):
    client_info = {'login': False, 'username': None}
    message = '********************************\n** Welcome to the BBS server. **\n********************************\n% '
    client.sendall(message.encode())
    while True:
        data = client.recv(1024)
        if len(data) == 0:
            client.close()
            print("Client %d close" % client_num)
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
                        c.execute("INSERT INTO user_info VALUES(?, ?, ?)", (command[1], command[2], command[3]))
                        db.commit()
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
                print("Client %d close" % client_num)
                break
            
            elif command[0] == 'create-board':
                if len(command) != 2:
                    message = 'Usage: create-board <name>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else: 
                        if board_check(command[1]) == True:
                            message = 'Board already exist.\n% '
                        else:
                            c.execute("INSERT INTO bbs_board VALUES(?, ?)", (command[2], cclient_info['username']))
                            db.commit()
                            message = 'Create board successfully.\n% '
            elif command[0] == 'create-post':
                e= 1
            elif command[0] == 'list-board':
                c.execute("SELECT * FROM bbs_board")
                board_list = c.fetchall()
                if len(command) == 1:
                    message = 'Index\tName\tModerator\n'
                    idx = 0
                    for board in board_list:
                        idx += 1
                        message += str(idx) + '\t' + board[0] + '\t' + board[1] + '\n'
                    message += '% '
                elif if len(command) == 2:
                    key_word = command[1][2:]
                    print('list_board_key_word %s' % key_word)
                    message = 'Index\tName\tModerator\n'
                    idx = 0
                    for board in board_list:
                        if re.search(key_word, board[0]) != None:
                            idx += 1
                            message += str(idx) + '\t' + board[0] + '\t' + board[1] + '\n'
                    message += '% '
                else:
                    message = 'Usage: list-board ##<key>\n% '
            elif command[0] == 'list-post':
                e= 1
            elif command[0] == 'read':
                if len(command) != 2:
                    message = 'Usage: read <post-id>\n% '
                else:
                    c.execute("SELECT * FROM bbs_post WHERE BID = ?", (int(command[1]), ))
                    post_info = c.fetchone()
                    if post_info == None:
                        message = 'Post does not exist.\n% '
                    else:
                        message = 'Author\t:' + post_info[2] + '\n'
                        message += 'Title\t:' + post_info[1] + '\n'
                        message += 'Date\t:' + post_info[3] + '\n'
                        message += '--\n'
                        post_content = str(post_info[5]).replace('<br>', '\n')
                        message += post_content + '\n--\n'
                        c.execute("SELECT * FROM post_comment WHERE post_id = ?", (int(command[1]), ))
                        comment_info = c.fetchall()
                        if comment_info != []:
                            for comment in comment_info:
                                message += comment[2] + ':'
                                remove_br = str(comment[1]).replace('<br>', '\n')
                                msssage += remove_br + '\n'
            elif command[0] == 'delete-post':
                if len(command) != 2:
                    message = 'Usage: delete-post <post-id>\n% '
                else:
                    if client_info['login'] == False:
                        message = 'Please login first.\n% '
                    else:
                        c.execute("SELECT * FROM bbs_post WHERE BID = ?", (int(command[1]), ))
                        post_info = c.fetchone()
                        if post_info == None:
                            message = 'Post does not exist.\n% '
                        else:
                            if client_info['username'] != post_info[2]:
                                message = 'Not the post owner.\n% '
                            else:
                                c.execute("DELETE FROM bbs_post WHERE BID = ?", (int(command[1]), ))
                                c.execute("DELETE FROM post_comment WHERE post_id = ?", (int(command[1]), ))
                                db.commit()
                                message = 'Delete successfully.\n% '
            elif command[0] == 'update-post':
                e= 1
            elif command[0] == 'comment':
                e= 1
            else:
                message = '% '
                print('ERROR: Error command. %s' % command[0])
            client.sendall(message.encode())

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
    while True:
        client, addr = server.accept()
        client_thread = threading.Thread(target=client_connect, args=(client, client_num))
        client_thread.setDaemon(True)
        client_thread.start()
        print("New connection.")
        print("Client %d create" % client_num)
        client_num = client_num + 1

if __name__ == '__main__':
    main()