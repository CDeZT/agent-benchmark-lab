#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <pthread.h>
#include <unistd.h>
#include "thread_pool.h"

#define NUM_TASKS 100
#define NUM_WORKERS 4

static int counter = 0;
static pthread_mutex_t counter_mutex = PTHREAD_MUTEX_INITIALIZER;

void increment_task(void *arg) {
    (void)arg;
    pthread_mutex_lock(&counter_mutex);
    counter++;
    pthread_mutex_unlock(&counter_mutex);
}

void test_create_and_shutdown(void) {
    printf("Test: create and shutdown... ");
    thread_pool_t *pool = pool_create(NUM_WORKERS);
    assert(pool != NULL);
    assert(pool_shutdown(pool) == 0);
    printf("PASS\n");
}

void test_submit_tasks(void) {
    printf("Test: submit tasks... ");
    thread_pool_t *pool = pool_create(NUM_WORKERS);
    assert(pool != NULL);
    for (int i = 0; i < 10; i++) {
        assert(pool_submit(pool, increment_task, NULL) == 0);
    }
    assert(pool_shutdown(pool) == 0);
    printf("PASS\n");
}

void test_concurrent_execution(void) {
    printf("Test: concurrent execution... ");
    counter = 0;
    thread_pool_t *pool = pool_create(NUM_WORKERS);
    assert(pool != NULL);
    assert(pool_start(pool) == 0);
    for (int i = 0; i < NUM_TASKS; i++) {
        assert(pool_submit(pool, increment_task, NULL) == 0);
    }
    while (pool_get_count(pool) > 0) usleep(1000);
    assert(pool_shutdown(pool) == 0);
    assert(counter == NUM_TASKS);
    printf("PASS\n");
}

void test_null_pool(void) {
    printf("Test: null pool... ");
    assert(pool_submit(NULL, increment_task, NULL) == -1);
    assert(pool_shutdown(NULL) == -1);
    assert(pool_get_count(NULL) == -1);
    printf("PASS\n");
}

int main(void) {
    printf("=== Thread Pool Tests ===\n");
    test_create_and_shutdown();
    test_submit_tasks();
    test_concurrent_execution();
    test_null_pool();
    printf("\nAll tests passed!\n");
    return 0;
}
