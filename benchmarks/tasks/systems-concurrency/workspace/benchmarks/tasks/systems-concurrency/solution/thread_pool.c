/* Thread pool implementation - fixed version. */

#include <stdlib.h>
#include <stdio.h>
#include <pthread.h>
#include <stdbool.h>

#define MAX_QUEUE_SIZE 100
#define MAX_WORKERS 8

typedef void (*task_func_t)(void *arg);

typedef struct {
    task_func_t func;
    void *arg;
} task_t;

typedef struct {
    task_t queue[MAX_QUEUE_SIZE];
    int head;
    int tail;
    int count;
    bool shutdown;
    pthread_t workers[MAX_WORKERS];
    int num_workers;
    pthread_mutex_t mutex;
    pthread_cond_t not_empty;
    pthread_cond_t not_full;
} thread_pool_t;

thread_pool_t *pool_create(int num_workers) {
    if (num_workers <= 0 || num_workers > MAX_WORKERS) return NULL;
    thread_pool_t *pool = malloc(sizeof(thread_pool_t));
    if (!pool) return NULL;
    pool->head = 0;
    pool->tail = 0;
    pool->count = 0;
    pool->shutdown = false;
    pool->num_workers = num_workers;
    pthread_mutex_init(&pool->mutex, NULL);
    pthread_cond_init(&pool->not_empty, NULL);
    pthread_cond_init(&pool->not_full, NULL);
    return pool;
}

void *worker_thread(void *arg) {
    thread_pool_t *pool = (thread_pool_t *)arg;
    while (true) {
        pthread_mutex_lock(&pool->mutex);
        while (pool->count == 0 && !pool->shutdown) {
            pthread_cond_wait(&pool->not_empty, &pool->mutex);
        }
        if (pool->shutdown && pool->count == 0) {
            pthread_mutex_unlock(&pool->mutex);
            break;
        }
        task_t task = pool->queue[pool->head];
        pool->head = (pool->head + 1) % MAX_QUEUE_SIZE;
        pool->count--;
        pthread_cond_signal(&pool->not_full);
        pthread_mutex_unlock(&pool->mutex);
        task.func(task.arg);
    }
    return NULL;
}

int pool_submit(thread_pool_t *pool, task_func_t func, void *arg) {
    if (!pool || !func) return -1;
    pthread_mutex_lock(&pool->mutex);
    while (pool->count >= MAX_QUEUE_SIZE && !pool->shutdown) {
        pthread_cond_wait(&pool->not_full, &pool->mutex);
    }
    if (pool->shutdown) {
        pthread_mutex_unlock(&pool->mutex);
        return -1;
    }
    pool->queue[pool->tail] = (task_t){func, arg};
    pool->tail = (pool->tail + 1) % MAX_QUEUE_SIZE;
    pool->count++;
    pthread_cond_signal(&pool->not_empty);
    pthread_mutex_unlock(&pool->mutex);
    return 0;
}

int pool_start(thread_pool_t *pool) {
    if (!pool) return -1;
    for (int i = 0; i < pool->num_workers; i++) {
        if (pthread_create(&pool->workers[i], NULL, worker_thread, pool) != 0) {
            pool->shutdown = true;
            pthread_cond_broadcast(&pool->not_empty);
            for (int j = 0; j < i; j++) {
                pthread_join(pool->workers[j], NULL);
            }
            return -1;
        }
    }
    return 0;
}

int pool_shutdown(thread_pool_t *pool) {
    if (!pool) return -1;
    pthread_mutex_lock(&pool->mutex);
    pool->shutdown = true;
    pthread_cond_broadcast(&pool->not_empty);
    pthread_mutex_unlock(&pool->mutex);
    for (int i = 0; i < pool->num_workers; i++) {
        pthread_join(pool->workers[i], NULL);
    }
    pthread_mutex_destroy(&pool->mutex);
    pthread_cond_destroy(&pool->not_empty);
    pthread_cond_destroy(&pool->not_full);
    free(pool);
    return 0;
}

int pool_get_count(thread_pool_t *pool) {
    if (!pool) return -1;
    pthread_mutex_lock(&pool->mutex);
    int count = pool->count;
    pthread_mutex_unlock(&pool->mutex);
    return count;
}
