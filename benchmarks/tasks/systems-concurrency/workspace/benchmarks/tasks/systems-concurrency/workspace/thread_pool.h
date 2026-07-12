#ifndef THREAD_POOL_H
#define THREAD_POOL_H

typedef void (*task_func_t)(void *arg);
typedef struct thread_pool_t thread_pool_t;

thread_pool_t *pool_create(int num_workers);
int pool_submit(thread_pool_t *pool, task_func_t func, void *arg);
int pool_start(thread_pool_t *pool);
int pool_shutdown(thread_pool_t *pool);
int pool_get_count(thread_pool_t *pool);

#endif
