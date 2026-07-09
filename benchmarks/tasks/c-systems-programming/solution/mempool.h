#ifndef MEMPOOL_H
#define MEMPOOL_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#define MEMPOOL_DEFAULT_ALIGNMENT 8
#define MEMPOOL_MAGIC 0xDEADBEEF
#define MEMPOOL_FREE_MAGIC 0xFEEDFACE

typedef struct BlockHeader {
    uint32_t magic;
    size_t   size;
    bool     is_free;
    struct BlockHeader *next;
    struct BlockHeader *prev;
} BlockHeader;

typedef struct PoolStats {
    size_t total_size;
    size_t used_size;
    size_t free_size;
    size_t num_allocations;
    size_t num_free_blocks;
    size_t largest_free;
    size_t fragmentation;
} PoolStats;

typedef struct MemPool {
    uint8_t     *memory;
    size_t       size;
    BlockHeader *head;
    size_t       alignment;
    bool         is_corrupt;
} MemPool;

MemPool *mempool_create(size_t size);
MemPool *mempool_create_aligned(size_t size, size_t alignment);
void mempool_destroy(MemPool *pool);
void *mempool_alloc(MemPool *pool, size_t size);
void *mempool_alloc_aligned(MemPool *pool, size_t size, size_t alignment);
int mempool_free(MemPool *pool, void *ptr);
void *mempool_realloc(MemPool *pool, void *ptr, size_t new_size);
int mempool_stats(const MemPool *pool, PoolStats *stats);
bool mempool_check(const MemPool *pool);
size_t mempool_usable_size(const MemPool *pool, const void *ptr);

#endif
