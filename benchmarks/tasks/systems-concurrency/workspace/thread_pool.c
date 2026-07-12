#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <stdbool.h>

#define MAX_QUEUE_SIZE 100
#define MAX_WORKERS 8

typedef void (*task_func_t)(void *arg);
typedef struct { task_func_t func; void *arg; } task_t;

typedef struct {
    task_t queue[MAX_QUEUE_SIZE];
    int head, tail, count;
    bool shutdown;
    pthread_t workers[MAX_WORKERS];
    int num_workers;
} thread_pool_t;

thread_pool_t *pool_create(int n) {
    if (n <= 0 || n > MAX_WORKERS) return NULL;
    thread_pool_t *p = calloc(1, sizeof(thread_pool_t));
    if (!p) return NULL;
    p->num_workers = n;
    return p;
}

void *worker(void *arg) {
    thread_pool_t *p = arg;
    while (!p->shutdown || p->count > 0) {
        if (p->count > 0) {
            task_t t = p->queue[p->head];
            p->head = (p->head + 1) % MAX_QUEUE_SIZE;
            p->count--;
            t.func(t.arg);
        }
    }
    return NULL;
}

int pool_submit(thread_pool_t *p, task_func_t f, void *a) {
    if (!p || !f) return -1;
    if (p->count >= MAX_QUEUE_SIZE) return -1;
    p->queue[p->tail] = (task_t){f, a};
    p->tail = (p->tail + 1) % MAX_QUEUE_SIZE;
    p->count++;
    return 0;
}

int pool_start(thread_pool_t *p) {
    if (!p) return -1;
    for (int i = 0; i < p->num_workers; i++)
        pthread_create(&p->workers[i], NULL, worker, p);
    return 0;
}

int pool_shutdown(thread_pool_t *p) {
    if (!p) return -1;
    p->shutdown = true;
    for (int i = 0; i < p->num_workers; i++)
        pthread_join(p->workers[i], NULL);
    free(p);
    return 0;
}

int pool_get_count(thread_pool_t *p) {
    if (!p) return -1;
    return p->count;
}
