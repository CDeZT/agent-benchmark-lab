#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include "thread_pool.h"

static int counter = 0;
static pthread_mutex_t counter_mutex = PTHREAD_MUTEX_INITIALIZER;

void increment_task(void *arg) {
    (void)arg;
    pthread_mutex_lock(&counter_mutex);
    counter++;
    pthread_mutex_unlock(&counter_mutex);
}

int main(void) {
    printf("Creating pool with 4 workers...\n");
    thread_pool_t *pool = pool_create(4);
    if (!pool) {
        printf("Failed to create pool\n");
        return 1;
    }

    printf("Starting pool...\n");
    if (pool_start(pool) != 0) {
        printf("Failed to start pool\n");
        return 1;
    }

    printf("Submitting 10 tasks...\n");
    for (int i = 0; i < 10; i++) {
        if (pool_submit(pool, increment_task, NULL) != 0) {
            printf("Failed to submit task %d\n", i);
            return 1;
        }
    }

    printf("Waiting for tasks to complete...\n");
    while (pool_get_count(pool) > 0) {
        usleep(1000);
    }

    printf("Shutting down pool...\n");
    if (pool_shutdown(pool) != 0) {
        printf("Failed to shutdown pool\n");
        return 1;
    }

    printf("Counter: %d (expected 10)\n", counter);
    if (counter == 10) {
        printf("PASS\n");
        return 0;
    } else {
        printf("FAIL\n");
        return 1;
    }
}
