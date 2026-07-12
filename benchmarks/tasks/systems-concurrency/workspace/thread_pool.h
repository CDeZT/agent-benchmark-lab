/* Thread pool API */
#ifndef THREAD_POOL_H
#define THREAD_POOL_H

#include <stdbool.h>

typedef void (*task_func_t)(void *arg);
typedef struct thread_pool_t thread_pool_t;

/* Create a thread pool with the given number of worker threads.
   Returns NULL on failure. */
thread_pool_t *pool_create(int num_workers);

/* Submit a task to the thread pool.
   Returns 0 on success, -1 on failure (queue full or pool shutdown). */
int pool_submit(thread_pool_t *pool, task_func_t func, void *arg);

/* Start the worker threads.
   Returns 0 on success, -1 on failure. */
int pool_start(thread_pool_t *pool);

/* Shutdown the thread pool and wait for all workers to finish.
   Returns 0 on success, -1 on failure. */
int pool_shutdown(thread_pool_t *pool);

/* Get the number of pending tasks in the queue.
   Returns -1 if pool is NULL. */
int pool_get_count(thread_pool_t *pool);

#endif /* THREAD_POOL_H */
