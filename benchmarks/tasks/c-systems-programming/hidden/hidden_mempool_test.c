/*
 * Hidden tests for the memory pool allocator.
 * Tests: double-free detection, realloc data preservation, linked list integrity,
 * fragmentation metric, usable_size accuracy, stress test.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mempool.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) do { printf("  TEST: %-50s ", name); } while(0)
#define PASS() do { printf("PASS\n"); tests_passed++; } while(0)
#define FAIL(msg) do { printf("FAIL: %s\n", msg); tests_failed++; } while(0)

void test_double_free_detection(void) {
    TEST("double free detection");
    MemPool *pool = mempool_create(4096);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *p = mempool_alloc(pool, 256);
    if (!p) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    int ret1 = mempool_free(pool, p);
    if (ret1 != 0) { FAIL("first free failed"); mempool_destroy(pool); return; }
    int ret2 = mempool_free(pool, p);
    if (ret2 == 0) FAIL("double free should return error but returned 0");
    mempool_destroy(pool);
    PASS();
}

void test_realloc_preserves_data(void) {
    TEST("realloc preserves old data");
    MemPool *pool = mempool_create(16384);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *p = mempool_alloc(pool, 256);
    if (!p) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    unsigned char pattern[256];
    for (int i = 0; i < 256; i++) pattern[i] = (unsigned char)(i * 3 + 7);
    memcpy(p, pattern, 256);
    void *p2 = mempool_realloc(pool, p, 512);
    if (!p2) { FAIL("realloc failed"); mempool_destroy(pool); return; }
    if (memcmp(p2, pattern, 256) != 0) FAIL("realloc did not preserve old data");
    mempool_free(pool, p2);
    mempool_destroy(pool);
    PASS();
}

void test_linked_list_integrity(void) {
    TEST("linked list prev pointer integrity");
    MemPool *pool = mempool_create(8192);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *ptrs[5];
    for (int i = 0; i < 5; i++) {
        ptrs[i] = mempool_alloc(pool, 512);
        if (!ptrs[i]) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    }
    mempool_free(pool, ptrs[1]);
    mempool_free(pool, ptrs[3]);
    bool ok = mempool_check(pool);
    if (!ok) FAIL("pool check failed after free - linked list may be corrupted");
    for (int i = 0; i < 5; i += 2) mempool_free(pool, ptrs[i]);
    mempool_destroy(pool);
    PASS();
}

void test_fragmentation_metric(void) {
    TEST("fragmentation metric is non-zero when fragmented");
    MemPool *pool = mempool_create(8192);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *ptrs[8];
    for (int i = 0; i < 8; i++) {
        ptrs[i] = mempool_alloc(pool, 512);
        if (!ptrs[i]) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    }
    for (int i = 0; i < 8; i += 2) mempool_free(pool, ptrs[i]);
    PoolStats stats;
    int ret = mempool_stats(pool, &stats);
    if (ret != 0) { FAIL("stats failed"); mempool_destroy(pool); return; }
    if (stats.fragmentation == 0) FAIL("fragmentation should be non-zero when pool has holes");
    if (stats.num_free_blocks < 2) FAIL("should have multiple free blocks after alternating free");
    for (int i = 1; i < 8; i += 2) mempool_free(pool, ptrs[i]);
    mempool_destroy(pool);
    PASS();
}

void test_usable_size_accuracy(void) {
    TEST("usable_size returns exact requested size");
    MemPool *pool = mempool_create(4096);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *p = mempool_alloc(pool, 100);
    if (!p) { FAIL("alloc failed"); mempool_destroy(pool); return; }
    size_t usable = mempool_usable_size(pool, p);
    if (usable < 100) FAIL("usable_size smaller than requested");
    if (usable > 256) FAIL("usable_size seems to include header overhead");
    mempool_free(pool, p);
    mempool_destroy(pool);
    PASS();
}

void test_stress_alloc_free(void) {
    TEST("stress test: 100 alloc/free cycles");
    MemPool *pool = mempool_create(65536);
    if (!pool) { FAIL("pool creation failed"); return; }
    void *ptrs[50];
    for (int cycle = 0; cycle < 100; cycle++) {
        for (int i = 0; i < 50; i++) {
            ptrs[i] = mempool_alloc(pool, 128 + (i * 16) % 512);
            if (ptrs[i]) memset(ptrs[i], cycle & 0xFF, 128);
        }
        for (int i = 0; i < 50; i++) {
            if (ptrs[i]) { mempool_free(pool, ptrs[i]); ptrs[i] = NULL; }
        }
    }
    bool ok = mempool_check(pool);
    if (!ok) FAIL("pool corrupted after stress test");
    mempool_destroy(pool);
    PASS();
}

int main(void) {
    printf("Running mempool hidden tests:\n");
    test_double_free_detection();
    test_realloc_preserves_data();
    test_linked_list_integrity();
    test_fragmentation_metric();
    test_usable_size_accuracy();
    test_stress_alloc_free();
    printf("\nResults: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
