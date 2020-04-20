#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <map>
#include <string>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>
#include <sqlite3.h>

#define client_MAX 32
#define MAXLINE 1024

// store Username && password
std::map<std::string, std::string> user_info;

// sqlite3 info
sqlite3 *db;
char *zErrMsg = 0;
int  rc, sql_cnt = 0;
char *sql;

// sqlite3 callback function
static int callback(void *NotUsed, int argc, char **argv, char **azColName) {
    std::string usr, pwd;
    usr.assign(argv[0]);
    pwd.assign(argv[1]);
    user_info[usr] = pwd;
    sql_cnt++;
    return 0;
}

void sqlite3_cmd(char *sql) {
    /* Execute SQL statement */
    rc = sqlite3_exec(db, sql, callback, 0, &zErrMsg);
    if(rc != SQLITE_OK) {
        fprintf(stderr, "SQL error: %s\n", zErrMsg);
        sqlite3_free(zErrMsg);
    } else {
        fprintf(stdout, "Successfully\n");
    }
}

void get_old_info() {
    char select_cmd[1000];
    sprintf(select_cmd, "SELECT Username, Password FROM USERS;");
    // sprintf(select_cmd, "SELECT Password FROM USERS WHERE Username LIKE '%s';", usr.c_str()); // select only one
    sqlite3_cmd(select_cmd);
}

int main(int argc, char *argv[]) {

    // server init information
    int serverPORT;
    int server_fd;
    char message[MAXLINE];                                                                  // message send to client
    std::map<int, std::string> client_info;                                                 // client login which user
    struct sockaddr_in srv_addr;

    // check args
    if(argc < 2) {
        fprintf(stderr, "Usage: %s <port>\n", argv[0]);
        exit(1);
    }

    /* Open database */
    rc = sqlite3_open("test.db", &db);
    if(rc) {
        fprintf(stderr, "Can't open database: %s\n", sqlite3_errmsg(db));
        exit(0);
    } else {
        fprintf(stdout, "Opened database successfully\n");
    }

    /* Create SQL statement */
    sql = "CREATE TABLE USERS(" \
          "UID INTEGER PRIMARY KEY AUTOINCREMENT," \
          "Username TEXT NOT NULL UNIQUE," \
          "Email TEXT NOT NULL," \
          "Password TEXT NOT NULL);";

    /* Execute SQL statement */
    sqlite3_cmd(sql);
    get_old_info();
    
    // set server information
    serverPORT = atoi(argv[1]);
    server_fd = socket(AF_INET, SOCK_STREAM, 0);                                            // AF_INET -> IPv4, SOCK_STREAM -> TCP
    if(server_fd < 0) {
        fprintf(stderr, "ERROR, SOCKET created failed\n");
        exit(1);
    }
    bzero(&srv_addr, sizeof(srv_addr));
    srv_addr.sin_family = AF_INET;
    srv_addr.sin_port = htons(serverPORT);                                                  // sin_port -> unsigned short
    srv_addr.sin_addr.s_addr = htonl(INADDR_ANY);                                           // sin_addr -> unsigned long
    
    // bind server infomation
    if(bind(server_fd, (struct sockaddr *) &srv_addr, sizeof(srv_addr)) < 0) {
        fprintf(stderr, "ERROR, bind failed\n");
        exit(1);
    } 
   
    // How many client can connect to server -> client_MAX
    listen(server_fd, client_MAX);

    // initialize client record
    int maxfd = server_fd + 1, maxClient = -1, client[client_MAX];                          // current max fd is listen, client_num recorded, each client's sockfd
    bool client_login[client_MAX];                                                          // check whether client login or not
    fd_set afds, rfds;                                                                      // read && active file descriptor set
    memset(client, -1, sizeof(client));                                                     // clear client's fd record
    memset(client_login, false, sizeof(client_login));                                      // false: not login, true: login
    FD_ZERO(&afds);                                                                         // clear afds
    FD_SET(server_fd, &afds);                                                               // put listen socket in afds

    // run server
    while(1) {
        rfds = afds;                                                                        // copy active to read
        int numReady = select(maxfd, &rfds, NULL, NULL, NULL);

        // new connect
        if(FD_ISSET(server_fd, &rfds)) {                                                    // listen socket is readable = have client
            struct sockaddr_in client_addr;
            socklen_t clientlen = sizeof(client_addr);
            int clientfd = accept(server_fd, (struct sockaddr *)&client_addr, &clientlen);  // accept a new client and give it a new socket
            int client_idx = client_MAX;
            for(int i = 0; i < client_MAX; ++i) {
                if(client[i] < 0) {
                    client[i] = clientfd;
                    client_idx = i;
                    break;
                }
            }
            if(client_idx == client_MAX) {
                fprintf(stderr, "ERROR, client is too much\n");
                exit(1);
            }
            FD_SET(clientfd, &afds);
            if(clientfd >= maxfd) maxfd = clientfd + 1;
            if(clientfd > maxClient) maxClient = clientfd;

            // send message to new client
            memset(message, '\0', sizeof(message));
            snprintf(message, sizeof(message), "********************************\n** Welcome to the BBS server. **\n********************************\n%% ");
            write(clientfd, message, sizeof(message));
            numReady--;
            if(numReady <= 0) continue;
        }
        for(int i = 0; i <= maxClient; ++i) {
            if(client[i] < 0) continue;
            if(FD_ISSET(client[i], &rfds)) {
                char buf[MAXLINE];
                ssize_t n = read(client[i], buf, 1023);
                if(n == 0) {
                    fprintf(stdout, "client is close\n");
                    close(client[i]);
                    FD_CLR(client[i], &afds);
                    client[i] = -1;
                    client_login[i] = 0;
                    client_info.erase(i);
                } else {
                    buf[n] = '\0';
                    char *pch = strtok(buf, " \n\r");
                    printf("Cmd received is %s\n", pch);
                    if(!strcmp(pch, "register")) {
                        fprintf(stdout, "command: register\n");
                        bool format = true, unique = true;
                        std::string usr, pwd;
                        pch = strtok(NULL, " \n\r");
                        memset(message, '\0', sizeof(message));
                        if(pch) {
                            // check not the same
                            usr.assign(pch);
                            if(user_info.find(usr) != user_info.end()) {
                                unique = false;
                            }
                            pch = strtok(NULL, " \n\r");
                            if(pch) {
                                std::string usr_email;
                                usr_email.assign(pch);
                                pch = strtok(NULL, " \n\r");
                                if(pch) {
                                    pwd.assign(pch);
                                    if(unique) {
                                        user_info[usr] = pwd;
                                        char sql2[1000];
                                        sprintf(sql2, "INSERT INTO USERS (UID, Username, Email, Password)" \
                                            "VALUES (%d, '%s', '%s', '%s');", sql_cnt++, usr.c_str(), usr_email.c_str(), pwd.c_str());
                                        sqlite3_cmd(sql2);
                                    }
                                } else { 
                                    format = false; 
                                    user_info.erase(usr);
                                }
                            } else { format = false; }
                        } else { format = false; }
                        if(!format) {
                            snprintf(message, 1023, "Usage: register <username> <email> <password>\n%% ");
                            write(client[i], message, sizeof(message));
                        } else if(!unique) {
                            snprintf(message, 1023, "Username is already used.\n%% ");
                            write(client[i], message, sizeof(message));
                        } else {
                            snprintf(message, 1023, "Register successfully.\n%% ");
                            write(client[i], message, sizeof(message));
                        }
                    } else if(!strcmp(pch, "login")) {
                        fprintf(stdout, "command: login\n");
                        pch = strtok(NULL, " \n\r");
                        std::string usr, pswd;
                        bool format = true, pwd = true, already = false;
                        memset(message, '\0', sizeof(message));
                        if(pch) {                                                           // check have name
                            usr.assign(pch);
                            if(user_info.find(usr) == user_info.end()) {
                                pwd = false;
                            }
                            pch = strtok(NULL, " \n\r");
                            if(pch) {                                                       // check the password
                                pswd.assign(pch);
                                if(!pwd) {
                                } else if(pswd != user_info[usr]) {
                                    pwd = false;
                                } else if(client_login[i]) {
                                    already = true;
                                } else {
                                    client_login[i] = true;
                                    client_info[i] = usr;
                                }
                            } else { format = false; }
                        } else { format = false; }
                        if(!format) {
                            snprintf(message, 1023, "Usage: login <username> <password>\n%% ");
                            write(client[i], message, sizeof(message));
                        } else if(!pwd) {
                            snprintf(message, 1023, "Login failed.\n%% ");
                            write(client[i], message, sizeof(message));
                        } else if(already) {
                            snprintf(message, 1023, "Please logout first.\n%% ");
                            write(client[i], message, sizeof(message));
                        } else {
                            snprintf(message, 1023, "Welcome, %s.\n%% ", usr.c_str());
                            write(client[i], message, sizeof(message));
                        }
                    } else if(!strcmp(pch, "logout")) {
                        fprintf(stdout, "command: logout\n");
                        memset(message, '\0', sizeof(message));
                        if(client_login[i]) {
                            client_login[i] = false;
                            snprintf(message, 1023, "Bye, %s.\n%% ", client_info[i].c_str());
                            write(client[i], message, sizeof(message));
                            client_info.erase(i);
                        } else {
                            snprintf(message, 1023, "Please login first.\n%% ");
                            write(client[i], message, sizeof(message));
                        }
                    } else if(!strcmp(pch, "whoami")) {
                        fprintf(stdout, "command: whoami\n");
                        memset(message, '\0', sizeof(message));
                        if(client_login[i]) {
                            snprintf(message, 1023, "%s\n%% ", client_info[i].c_str());
                            write(client[i], message, sizeof(message));
                        } else {
                            snprintf(message, 1023, "Please login first.\n%% ");
                            write(client[i], message, sizeof(message));
                        }
                    } else if(!strcmp(pch, "exit")) {
                        fprintf(stdout, "client %d is close\n", i);
                        memset(message, '\0', sizeof(message));
                        close(client[i]);
                        FD_CLR(client[i], &afds);
                        client[i] = -1;
                        client_login[i] = false;
                        client_info.erase(i);
                    } else {
                        memset(message, '\0', sizeof(message));
                        snprintf(message, 1023, "%% ");
                        write(client[i], message, sizeof(message));
                        fprintf(stdout, "ERROR: Error command. %s\n", pch);
                    }    
                }
                numReady--;
                if(numReady <= 0) break;
            }
        }
    }
    sqlite3_close(db);
    return 0;
}