/* Narrow installer utility for ROMs whose Magisk --sqlite IPC crashes.
 * Run as root: root-policy --inspect, or root-policy <three launcher UIDs>.
 * The installer must verify each UID belongs to its signed launcher package.
 */
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct sqlite3 sqlite3;
static int (*sql_exec)(sqlite3 *, const char *, int (*)(void *,int,char **,char **), void *, char **);
static void (*sql_free)(void *);

static int print_row(void *unused, int count, char **values, char **names)
{
    (void)unused;
    for (int i = 0; i < count; i++)
        printf("%s=%s%s", names[i], values[i] ? values[i] : "NULL", i + 1 == count ? "\n" : "|");
    return 0;
}

static int query(sqlite3 *db, const char *sql)
{
    char *error = NULL;
    int result = sql_exec(db, sql, print_row, NULL, &error);
    if (result) fprintf(stderr, "SQLite: %s\n", error ? error : "failed");
    sql_free(error);
    return result;
}

int main(int argc, char **argv)
{
    if (getuid() != 0) return 1;
    int inspect = argc == 2 && !strcmp(argv[1], "--inspect");
    if (!inspect && argc != 4) return 2;
    long uids[3] = {0};
    if (!inspect) {
        for (int i = 0; i < 3; i++) {
            char *end;
            uids[i] = strtol(argv[i+1], &end, 10);
            if (*end || uids[i] < 10000 || uids[i] > 19999) return 2;
            for (int j = 0; j < i; j++) if (uids[i] == uids[j]) return 2;
        }
    }
    void *lib = dlopen("/system/lib64/libsqlite.so", RTLD_NOW);
    if (!lib) { fprintf(stderr, "%s\n", dlerror()); return 3; }
    int (*open_db)(const char *, sqlite3 **, int, const char *) = dlsym(lib, "sqlite3_open_v2");
    int (*close_db)(sqlite3 *) = dlsym(lib, "sqlite3_close");
    int (*timeout)(sqlite3 *, int) = dlsym(lib, "sqlite3_busy_timeout");
    sql_exec = dlsym(lib, "sqlite3_exec");
    sql_free = dlsym(lib, "sqlite3_free");
    if (!open_db || !close_db || !timeout || !sql_exec || !sql_free) return 3;
    sqlite3 *db = NULL;
    if (open_db("/data/adb/magisk.db", &db, inspect ? 1 : 2, NULL)) return 4;
    timeout(db, 5000);
    int result;
    if (inspect) result = query(db, "PRAGMA table_info(policies);");
    else {
        char sql[1024];
        snprintf(sql, sizeof(sql), "SELECT * FROM policies WHERE uid IN (%ld,%ld,%ld);", uids[0], uids[1], uids[2]);
        puts("BEFORE");
        result = query(db, sql);
        if (!result) result = query(db, "BEGIN IMMEDIATE;");
        for (int i = 0; !result && i < 3; i++) {
            snprintf(sql, sizeof(sql), "INSERT OR REPLACE INTO policies(uid,policy,until,logging,notification) VALUES(%ld,2,0,1,1);", uids[i]);
            result = query(db, sql);
        }
        if (result) query(db, "ROLLBACK;");
        else result = query(db, "COMMIT;");
        if (!result) {
            puts("AFTER");
            snprintf(sql, sizeof(sql), "SELECT * FROM policies WHERE uid IN (%ld,%ld,%ld);", uids[0], uids[1], uids[2]);
            result = query(db, sql);
        }
    }
    close_db(db);
    dlclose(lib);
    return result ? 5 : 0;
}
