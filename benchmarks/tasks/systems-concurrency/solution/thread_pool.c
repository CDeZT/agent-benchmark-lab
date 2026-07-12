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
    volatile bool shutdown;
    pthread_t workers[MAX_WORKERS];
    int num_workers;
    pthread_mutex_t mutex;
    pthread_cond_t cond;
} thread_pool_t;

thread_pool_t *pool_create(int n) {
    if (n <= 0 || n > MAX_WORKERS) return NULL;
    thread_pool_t *p = calloc(1, sizeof(thread_pool_t));
    if (!p) return NULL;
    p->num_workers = n;
    pthread_mutex_init(&p->mutex, NULL);
    pthread_cond_init(&p->cond, NULL);
    return p;
}

void *worker(void *arg) {
    thread_pool_t *p = arg;
    for (;;) {
        pthread_mutex_lock(&p->mutex);
        while (p->count == 0 && !p->shutdown)
            pthread_cond_wait(&p->cond, &p->mutex);
        if (p->shutdown && p->count == 0) {
            pthread_mutex_unlock(&p->mutex);
            break;
        }
        task_t t = p->queue[p->head];
        p->head = (p->head + 1) % MAX_QUEUE_SIZE;
        p->count--;
        pthread_cond_broadcast(&p->cond);  // wake submitter or other workers
        pthread_mutex_unlock(&p->mutex);
        t.func(t.arg);
    }
    return NULL;
}

int pool_submit(thread_pool_t *p, task_func_t f, void *a) {
    if (!p || !f) return -1;
    pthread_mutex_lock(&p->mutex);
    while (p->count >= MAX_QUEUE_SIZE && !p->shutdown)
        pthread_cond_wait(&p->cond, &p->mutex);
    if (p->shutdown) { pthread_mutex_unlock(&p->mutex); return -1; }
    p->queue[p->tail] = (task_t){f, a};
    p->tail = (p->tail + 1) % MAX_QUEUE_SIZE;
    p->count++;
    pthread_cond_broadcast(&p->cond);
    pthread_mutex_unlock(&p->mutex);
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
    pthread_mutex_lock(&p->mutex);
    p->shutdown = true;
    pthread_cond_broadcast(&p->cond);
    pthread_mutex_unlock(&p->mutex);
    for (int i = 0; i < p->num_workers; i++)
        pthread_join(p->workers[i], NULL);
    pthread_mutex_destroy(&p->mutex);
    pthread_cond_destroy(&p->cond);
    free(p);
    return 0;
}

int pool_get_count(thread_pool_t *p) {
    if (!p) return -1;
    pthread_mutex_lock(&p->mutex);
    int c = p->count;
    pthread_mutex_unlock(&p->mutex);
    return c;
}
