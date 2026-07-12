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
static pthread_cond_t all_done = PTHREAD_COND_INITIALIZER;
static int expected = 0;

void increment_task(void *arg) {
    (void)arg;
    pthread_mutex_lock(&counter_mutex);
    counter++;
    if (counter >= expected)
        pthread_cond_signal(&all_done);
    pthread_mutex_unlock(&counter_mutex);
}

void test_create_shutdown(void) {
    printf("Test: create and shutdown... ");
    thread_pool_t *p = pool_create(NUM_WORKERS);
    assert(p != NULL);
    assert(pool_shutdown(p) == 0);
    printf("PASS\n");
}

void test_submit_tasks(void) {
    printf("Test: submit tasks... ");
    thread_pool_t *p = pool_create(NUM_WORKERS);
    assert(p != NULL);
    for (int i = 0; i < 10; i++)
        assert(pool_submit(p, increment_task, NULL) == 0);
    assert(pool_shutdown(p) == 0);
    printf("PASS\n");
}

void test_concurrent_execution(void) {
    printf("Test: concurrent execution... ");
    counter = 0;
    expected = NUM_TASKS;
    thread_pool_t *p = pool_create(NUM_WORKERS);
    assert(p != NULL);
    assert(pool_start(p) == 0);

    pthread_mutex_lock(&counter_mutex);
    for (int i = 0; i < NUM_TASKS; i++)
        assert(pool_submit(p, increment_task, NULL) == 0);

    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_sec += 10;  // 10s timeout
    while (counter < NUM_TASKS) {
        int rc = pthread_cond_timedwait(&all_done, &counter_mutex, &ts);
        if (rc != 0) break;
    }
    int final_count = counter;
    pthread_mutex_unlock(&counter_mutex);

    assert(pool_shutdown(p) == 0);
    assert(final_count == NUM_TASKS);
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
    test_create_shutdown();
    test_submit_tasks();
    test_concurrent_execution();
    test_null_pool();
    printf("\nAll tests passed!\n");
    return 0;
}
