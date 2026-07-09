/*
 * Public tests for the memory pool allocator.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mempool.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) do { printf("  TEST: %-45s ", name); } while(0)
#define PASS() do { printf("PASS\n"); tests_passed++; } while(0)
#define FAIL(msg) do { printf("FAIL: %s\n", msg); tests_failed++; } while(0)

void test_create_destroy(void) {
    TEST("create and destroy pool");
    MemPool *pool = mempool_create(4096);
    if (!pool) { FAIL("pool creation failed"); return; }
    mempool_destroy(pool);
    PASS();
}

void test_basic_alloc_free(void) {
    TEST("basic alloc and free");
    MemPool *pool = mempool_create(4096);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *p = mempool_alloc(pool, 128);
    if (!p) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    memset(p, 0xAB, 128);
    int ret = mempool_free(pool, p);
    if (ret != 0) { FAIL("free returned error"); }
    mempool_destroy(pool);
    PASS();
}

void test_multiple_allocs(void) {
    TEST("multiple allocations");
    MemPool *pool = mempool_create(8192);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *ptrs[10];
    for (int i = 0; i < 10; i++) {
        ptrs[i] = mempool_alloc(pool, 256);
        if (!ptrs[i]) { FAIL("alloc failed"); mempool_destroy(pool); return; }
        memset(ptrs[i], i, 256);
    }
    for (int i = 0; i < 10; i++) {
        unsigned char *p = (unsigned char *)ptrs[i];
        for (int j = 0; j < 256; j++) {
            if (p[j] != (unsigned char)i) { FAIL("data corruption"); mempool_destroy(pool); return; }
        }
    }
    for (int i = 0; i < 10; i++) mempool_free(pool, ptrs[i]);
    mempool_destroy(pool);
    PASS();
}

void test_alloc_reuse(void) {
    TEST("free block reuse");
    MemPool *pool = mempool_create(4096);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *p1 = mempool_alloc(pool, 1024);
    if (!p1) { FAIL("first alloc failed"); mempool_destroy(pool); return; }
    mempool_free(pool, p1);
    void *p2 = mempool_alloc(pool, 1024);
    if (!p2) { FAIL("second alloc failed"); mempool_destroy(pool); return; }
    mempool_free(pool, p2);
    mempool_destroy(pool);
    PASS();
}

void test_pool_stats(void) {
    TEST("pool statistics");
    MemPool *pool = mempool_create(4096);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *p = mempool_alloc(pool, 1024);
    if (!p) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    PoolStats stats;
    int ret = mempool_stats(pool, &stats);
    if (ret != 0) { FAIL("stats failed"); }
    if (stats.total_size != 4096) FAIL("wrong total_size");
    if (stats.num_allocations != 1) FAIL("wrong allocation count");
    mempool_free(pool, p);
    mempool_destroy(pool);
    PASS();
}

void test_pool_check(void) {
    TEST("pool integrity check");
    MemPool *pool = mempool_create(4096);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *p = mempool_alloc(pool, 256);
    if (!p) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    bool ok = mempool_check(pool);
    if (!ok) { FAIL("check failed on valid pool"); }
    mempool_free(pool, p);
    mempool_destroy(pool);
    PASS();
}

int main(void) {
    printf("Running mempool public tests:\n");
    test_create_destroy();
    test_basic_alloc_free();
    test_multiple_allocs();
    test_alloc_reuse();
    test_pool_stats();
    test_pool_check();
    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
